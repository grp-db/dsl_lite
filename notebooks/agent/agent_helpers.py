# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC # DSL Lite Agent — Helper Functions
# MAGIC
# MAGIC Loaded via `%run ./agent_helpers` from `preset_agent`. Encapsulates the reusable
# MAGIC building blocks — skill loading, input introspection, sample packing, prompt
# MAGIC construction, model calls, and final-preset assembly — so the notebook itself
# MAGIC reads as a thin orchestration layer.

# COMMAND ----------

import os
import re
from datetime import datetime, timezone

from yaml import safe_load, YAMLError
from pyspark.sql import SparkSession

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

spark = SparkSession.getActiveSession()


# =============================================================================
# Constants
# =============================================================================

# Prompt budget. Use a conservative floor that works across the common Databricks FMAPI
# endpoints (Llama 3.3 70B = 128K tokens, Claude Sonnet 4 = 200K, etc.). 400K chars ≈
# 100K tokens leaves ~28K tokens of headroom on the smallest supported endpoint.
MODEL_INPUT_CHAR_BUDGET = 400_000
RESERVED_OUTPUT_CHARS   = 32_000   # matches max_tokens=8000 (~4 chars/token)
RESERVED_OVERHEAD_CHARS = 4_000    # scaffolding around the sample block

# 'auto' mode upper bound — actual count is throttled further by the prompt budget.
_AUTO_ROW_UPPER_BOUND = 200

# Blueprint requirements enforced on every generation. The skill references teach the
# details; these are the checks most worth hammering in the prompt itself because past
# runs have shown models hallucinate them when the skill context is long.

# Apply regardless of which layers we're emitting.
OUTPUT_FORMAT_REQUIREMENTS = [
    "Use `try_variant_get` (not `variant_get`) for any VARIANT/JSON payload access so missing keys yield NULL instead of runtime errors.",
    "YAML quoting: any scalar value whose body contains `: ` (colon + space), a leading `#`, a leading `-`, or a trailing `:` MUST be wrapped in double quotes. This is the #1 cause of parse failures in `expr:`, `filter:`, `postFilter:`, and `literal:` values that embed SQL string literals. Example — wrong: `expr: CONCAT('Authentication: ', 'Login')`; right: `expr: \"CONCAT('Authentication: ', 'Login')\"`.",
    "Output ONLY the YAML document. Do not wrap it in triple backticks, do not add prose before or after.",
]

# Apply only when a `gold:` section is being emitted.
GOLD_REQUIREMENTS = [
    "Include `metadata:` on every gold class — it is always required (version, product.name, product.vendor_name, log_provider, log_name, log_format, logged_time, processed_time).",
    "Include the class-appropriate objects per the skill's mapping reference: `src_endpoint`/`dst_endpoint` for Network (4xxx) and IAM/Authentication (3xxx); `device` for Process / File / Script activity. Never mix endpoint and device on the same class.",
    "Set `activity_id`, `category_uid`, `class_uid`, `type_uid`, and `severity_id` to values defined by the OCSF enum for each target class — do not invent values.",
    "Preserve the source event time in the `time` field as unix milliseconds; populate `metadata.logged_time` from the bronze ingestion timestamp.",
    "Use OCSF field names exactly (snake_case, dotted paths like `src_endpoint.ip`). Do not invent fields that are not in the OCSF schema for the target class.",
    "Include `raw_data` or `unmapped` reference back to the bronze record for traceability when the skill pattern calls for it.",
]

# Back-compat alias — full list with OCSF requirements included.
UNIVERSAL_REQUIREMENTS = OUTPUT_FORMAT_REQUIREMENTS + GOLD_REQUIREMENTS


# Valid target_layers values. `auto` defers to the input_layer default.
_VALID_TARGET_LAYERS = {"auto", "full", "bronze_silver", "gold"}


def resolve_target_layers(input_layer: str, target_layers: str) -> str:
    """
    Resolve `auto` against the input layer, and validate the combination.
    Returns one of {"full", "bronze_silver", "gold"}.
    """
    tl = (target_layers or "auto").strip().lower()
    if tl not in _VALID_TARGET_LAYERS:
        raise ValueError(
            f"target_layers must be one of {sorted(_VALID_TARGET_LAYERS)}, got {tl!r}"
        )
    if tl == "auto":
        tl = "gold" if input_layer == "silver" else "full"

    # Validate combinations.
    if tl == "gold" and input_layer != "silver":
        raise ValueError("target_layers='gold' requires input_layer='silver'")
    if tl in ("full", "bronze_silver") and input_layer != "raw":
        raise ValueError(
            f"target_layers='{tl}' requires input_layer='raw' — the bronze ingestion must be "
            f"designed from raw sample files, not inferred from an already-silver table."
        )
    return tl


# =============================================================================
# Skill loading
# =============================================================================

def _read(p: str) -> str:
    with open(p, "r") as f:
        return f.read()


def load_skill(skill_path: str) -> str:
    """Concatenate SKILL.md + references/*.md into a single system-prompt string."""
    skill_path = skill_path.rstrip("/")
    skill_main = f"{skill_path}/SKILL.md"
    refs_dir   = f"{skill_path}/references"

    parts = [f"# FILE: SKILL.md\n\n{_read(skill_main)}"]
    for fname in sorted(os.listdir(refs_dir)):
        if fname.endswith(".md"):
            parts.append(f"# FILE: references/{fname}\n\n{_read(f'{refs_dir}/{fname}')}")
    skill_context = "\n\n---\n\n".join(parts)
    print(f"Loaded {len(parts)} skill file(s), {len(skill_context):,} chars")
    return skill_context


# =============================================================================
# Input introspection
# =============================================================================

def resolve_sample_rows(sample_rows_raw: str) -> tuple:
    """
    Parse the `sample_rows` widget value → (n_sample, auto_sample).
    Accepts 'auto' (default, capped at _AUTO_ROW_UPPER_BOUND), 'all' (no cap — n_sample=None),
    or a positive integer.
    """
    raw = (sample_rows_raw or "auto").strip().lower()
    if raw == "auto":
        return _AUTO_ROW_UPPER_BOUND, True
    if raw == "all":
        return None, False
    return int(raw), False


def introspect_table(source_table: str, n_sample, where_clause: str = "") -> dict:
    """
    DESCRIBE + JSON-encoded sample rows from a UC table.

    n_sample=None disables LIMIT. where_clause (optional SQL WHERE body — no leading
    `WHERE`) filters rows before sampling; useful to skip rows where key columns are
    NULL so the model sees meaningful data (e.g. `dns_record IS NOT NULL`).
    """
    schema_rows = spark.sql(f"DESCRIBE TABLE EXTENDED {source_table}").collect()
    schema_text = "\n".join(
        f"{r['col_name']:40s} {r['data_type'] or '':30s} {r['comment'] or ''}"
        for r in schema_rows if r['col_name']
    )
    where_sql = f"WHERE {where_clause}" if (where_clause or "").strip() else ""
    if n_sample is None:
        print(f"  ⚠ sample_rows=all → collecting every row of {source_table}. "
              f"Safe only for small tables; the prompt packer trims to the budget either way.")
        limit_clause = ""
    else:
        limit_clause = f"LIMIT {n_sample}"
    if where_sql:
        print(f"  sample_filter applied: {where_clause}")
    sample_items = [r["_row"] for r in spark.sql(
        f"SELECT to_json(struct(*)) AS _row FROM {source_table} {where_sql} {limit_clause}"
    ).collect()]
    return {
        "schema_text":        schema_text,
        "sample_items":       sample_items,
        "sample_kind":        "table_rows",
        "sample_source_desc": f"Unity Catalog table: `{source_table}`",
    }


_DEFAULT_MAX_FILE_BYTES = 64 * 1024    # 64 KB per file — enough to infer schema
_CUMULATIVE_READ_CAP    = 4_000_000    # hard ceiling across all files (~1M tokens)


def introspect_raw_files(raw_sample_path: str, n_sample,
                         max_file_bytes: int = _DEFAULT_MAX_FILE_BYTES) -> dict:
    """
    Read up to `n_sample` files from a folder (or the single file).

    - n_sample=None → read all files in the folder (no count cap).
    - max_file_bytes=0 → read each file in full AND disable the cumulative safety cap
      (full opt-out; use with care on huge folders).
    - Otherwise, each file is truncated to max_file_bytes, and reading stops once
      cumulative bytes exceed `_CUMULATIVE_READ_CAP`.
    """
    if os.path.isdir(raw_sample_path):
        files = sorted(
            os.path.join(raw_sample_path, f)
            for f in os.listdir(raw_sample_path)
            if not f.startswith(".") and os.path.isfile(os.path.join(raw_sample_path, f))
        )
        if n_sample is not None:
            files = files[:n_sample]
    else:
        files = [raw_sample_path]

    # max_file_bytes=0 means "unlimited" — also disables the cumulative safety cap.
    enforce_cumulative = max_file_bytes > 0
    sample_items = []
    cumulative   = 0
    truncated    = 0
    skipped      = 0
    for fp in files:
        if enforce_cumulative and cumulative >= _CUMULATIVE_READ_CAP:
            skipped += 1
            continue
        try:
            file_size = os.path.getsize(fp)
        except OSError:
            file_size = -1
        with open(fp, "r", errors="replace") as fh:
            body = fh.read(max_file_bytes + 1) if max_file_bytes > 0 else fh.read()
        was_truncated = max_file_bytes > 0 and (
            len(body) > max_file_bytes or file_size > max_file_bytes
        )
        if max_file_bytes > 0:
            body = body[:max_file_bytes]
        if was_truncated:
            truncated += 1
            body += f"\n... [truncated at {max_file_bytes:,} bytes; file size {file_size:,} B]"
        sample_items.append(f"# FILE: {fp}\n{body}")
        cumulative += len(body)

    if truncated or skipped:
        print(f"  raw-file truncation: {truncated} file(s) hit max_file_bytes={max_file_bytes:,}; "
              f"{skipped} file(s) skipped after cumulative cap {_CUMULATIVE_READ_CAP:,} bytes")
    if not enforce_cumulative:
        print(f"  ⚠ max_file_bytes=0 → no per-file or cumulative cap. "
              f"Read {len(sample_items)} file(s), {cumulative:,} bytes total.")

    return {
        "schema_text":        "(no UC table — raw files; model must design bronze ingestion)",
        "sample_items":       sample_items,
        "sample_kind":        "raw_files",
        "sample_source_desc": f"Raw log files from volume path: `{raw_sample_path}`",
    }


def introspect_input(source_table: str, raw_sample_path: str, n_sample,
                     max_file_bytes: int = _DEFAULT_MAX_FILE_BYTES,
                     where_clause: str = "") -> dict:
    """Dispatch to table or raw-files introspection based on which input was set."""
    assert source_table or raw_sample_path, (
        "Provide either source_table (UC table) or raw_sample_path (volume path with raw log files)"
    )
    if source_table:
        return introspect_table(source_table, n_sample, where_clause)
    if where_clause:
        print("  (sample_filter ignored — raw-files mode has no WHERE clause)")
    return introspect_raw_files(raw_sample_path, n_sample, max_file_bytes)


def print_input_summary(intro: dict, packed_count: int, total_count: int, auto_sample: bool) -> None:
    """One-shot summary of what we pulled from the source."""
    print("── INPUT SOURCE ────────────────────────────────────────")
    print(intro["sample_source_desc"])
    print("\n── SCHEMA ──────────────────────────────────────────────")
    schema_text = intro["schema_text"]
    print(schema_text[:2000] + ("..." if len(schema_text) > 2000 else ""))
    print(f"\n── Pulled {total_count} sample item(s), "
          f"{sum(len(s) for s in intro['sample_items']):,} chars total "
          f"(mode={'auto' if auto_sample else 'fixed'})")


# =============================================================================
# Existing-preset loader + gold splitter
# =============================================================================

def _is_top_level_gold(line: str) -> bool:
    """True if `line` is a top-level `gold:` mapping key (col 0, no indent)."""
    if not line.startswith("gold:"):
        return False
    # accept: "gold:", "gold: ", "gold:\n", "gold:# comment" etc.
    return len(line) == 5 or line[5] in (" ", "\t", "\n", "\r", "#")


def split_at_gold(yaml_text: str) -> tuple:
    """Return (text before top-level `gold:`, text from `gold:` onward)."""
    lines = yaml_text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if _is_top_level_gold(line):
            return "".join(lines[:i]), "".join(lines[i:])
    return yaml_text, ""


def load_existing_preset(existing_preset_path: str) -> tuple:
    """
    Return (existing_preset_text, existing_bronze_silver). Both are None if
    `existing_preset_path` is empty.
    """
    if not existing_preset_path:
        print("No existing_preset_path — model will emit a fresh preset.")
        return None, None
    with open(existing_preset_path, "r") as f:
        text = f.read()
    # safe_load purely for validation — surfaces a clear error if the file is malformed
    # before we waste a model call on garbage context.
    parsed = safe_load(text)
    if not isinstance(parsed, dict):
        raise ValueError(f"{existing_preset_path} must be a YAML mapping at top level.")
    before_gold, _ = split_at_gold(text)
    bronze_silver = before_gold if before_gold.strip() else None
    print(f"Loaded existing preset from {existing_preset_path} "
          f"(top-level keys: {list(parsed.keys())})")
    return text, bronze_silver


# =============================================================================
# Sample packing + budget
# =============================================================================

def compute_sample_budget(skill_context: str, schema_text: str,
                          existing_bronze_silver) -> int:
    """Chars left for sample content after fixed parts of the prompt."""
    bs_len = len(existing_bronze_silver) if existing_bronze_silver else 0
    return max(
        0,
        MODEL_INPUT_CHAR_BUDGET
        - len(skill_context)
        - len(schema_text)
        - bs_len
        - RESERVED_OUTPUT_CHARS
        - RESERVED_OVERHEAD_CHARS,
    )


def pack_samples(sample_items: list, sample_kind: str, budget: int) -> dict:
    """Pack items until the remaining char budget would be exceeded."""
    packed  = []
    running = 2  # array brackets / file separators
    for s in sample_items:
        delta = len(s) + 4
        if running + delta > budget:
            break
        packed.append(s)
        running += delta
    truncated = len(packed) < len(sample_items)

    if sample_kind == "table_rows":
        block = (
            "[\n"
            + ",\n".join("  " + s for s in packed)
            + ("\n... [truncated]" if truncated else "")
            + "\n]"
        )
        fence = "json"
        label = "Sample rows (JSON)"
    else:
        block = (
            "\n\n---\n\n".join(packed)
            + ("\n\n... [truncated additional files]" if truncated else "")
        )
        fence = ""
        label = "Raw sample file contents"

    return {
        "block":        block,
        "fence":        fence,
        "label":        label,
        "packed_count": len(packed),
        "total_count":  len(sample_items),
        "truncated":    truncated,
        "budget":       budget,
    }


# =============================================================================
# Prompt summary (prompts themselves live in the notebook for easy tuning)
# =============================================================================

def print_prompt_summary(system_prompt: str, user_prompt: str) -> None:
    total = len(system_prompt) + len(user_prompt)
    print(f"system prompt: {len(system_prompt):,} chars")
    print(f"user prompt:   {len(user_prompt):,} chars")
    print(f"total:         {total:,} chars  (~{total // 4:,} tokens; "
          f"budget {MODEL_INPUT_CHAR_BUDGET:,} chars)")


# =============================================================================
# Model call + output sanitization
# =============================================================================

_FENCE_RE = re.compile(r"```(?:ya?ml)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def strip_fences(s: str) -> str:
    """Extract the first fenced block if present anywhere in the response.
    Models sometimes wrap YAML with a prose preamble ('Here is your preset:')
    that a naïve startswith check would miss."""
    m = _FENCE_RE.search(s)
    if m:
        return m.group(1).strip()
    return s.strip()


def yaml_error_context(yaml_text: str, err: YAMLError) -> str:
    """Build a ' at line N, col M: <offending line>' hint from a yaml error."""
    mark = getattr(err, "problem_mark", None)
    if mark is None:
        return ""
    lines = yaml_text.splitlines()
    lineno = mark.line + 1
    snippet = lines[mark.line] if 0 <= mark.line < len(lines) else ""
    return f" at line {lineno}, col {mark.column + 1}: {snippet!r}"


def query_model(w: WorkspaceClient, endpoint: str, messages: list) -> str:
    """Call a serving endpoint, handling Claude/Llama temperature quirks."""
    kwargs = dict(name=endpoint, messages=messages, max_tokens=8000)
    # Claude extended-thinking endpoints reject non-1.0 temperature; other Claude
    # variants accept 0 for determinism; Llama/others take the usual range.
    if "claude-opus" in endpoint or "thinking" in endpoint:
        pass
    elif "claude" in endpoint:
        kwargs["temperature"] = 0.0
    else:
        kwargs["temperature"] = 0.1
    return w.serving_endpoints.query(**kwargs).choices[0].message.content.strip()


# =============================================================================
# Final assembly + validation
# =============================================================================

def build_provenance(*, model_endpoint: str, skill_path: str, source_table: str,
                     raw_sample_path: str, input_layer: str, target_layers: str,
                     ocsf_classes: list, refined: bool = False) -> str:
    """Produce the all-comment provenance header injected above generated content."""
    ts = datetime.now(timezone.utc).isoformat(timespec='seconds')
    ts_line = f"# Generated:  {ts}" + (" (refined)" if refined else "")
    return "\n".join([
        "# ── Generated by preset_agent ────────────────────────────────────────────",
        ts_line,
        f"# Model:      {model_endpoint}",
        f"# Skill:      {skill_path}",
        f"# Source:     {source_table or raw_sample_path or '(unspecified)'}",
        f"# Input:      input_layer={input_layer}, target_layers={target_layers}, "
        f"ocsf_classes={ocsf_classes or '(inferred)'}",
        "# ─────────────────────────────────────────────────────────────────────────",
    ]) + "\n"


def splice_gold(base_text: str, generated_yaml_text: str, provenance: str = "") -> str:
    """
    Concat `base_text` (bytes before its top-level `gold:`) with the model's gold block.

    Text-level only: we do NOT parse `generated_yaml_text` here, so a YAML syntax
    error inside the model's gold block still produces an assembled `final_yaml` the
    caller can inspect. The single source of parse truth is `validate_final_yaml`,
    which runs on the spliced result and reports errors with line/col in that file.
    """
    # The first non-comment, non-blank top-level line in the model output must be `gold:`.
    first_real = None
    for line in generated_yaml_text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        first_real = line
        break
    if first_real is None or not _is_top_level_gold(first_real):
        raise ValueError(
            f"Model response in gold-target splice mode must start with a top-level `gold:` "
            f"key (first non-comment line was: {first_real!r}). Inspect the `preset_yaml` "
            f"print from section 6, or re-run section 9 with corrective feedback."
        )
    before_gold, _ = split_at_gold(base_text)
    before = before_gold.rstrip() + "\n\n" if before_gold.strip() else ""
    after  = generated_yaml_text.lstrip()
    if not after.endswith("\n"):
        after += "\n"
    return before + provenance + after


def assemble_final(*, preset_yaml: str, existing_preset_text, target_layers: str,
                   provenance: str) -> str:
    """
    For target_layers='gold' with an existing preset, splice the new gold block into
    the existing bronze/silver bytes. Otherwise, prepend provenance to the model output.
    """
    if target_layers == "gold" and existing_preset_text is not None:
        return splice_gold(existing_preset_text, preset_yaml, provenance=provenance)
    return provenance + preset_yaml


def validate_final_yaml(final_yaml: str, target_layers: str,
                        existing_preset_text) -> dict:
    """Parse + check required top-level keys based on target_layers. Returns the parsed dict."""
    try:
        parsed = safe_load(final_yaml)
    except YAMLError as e:
        raise RuntimeError(
            f"Generated preset is not valid YAML — refuse to save"
            f"{yaml_error_context(final_yaml, e)}. Parser error: {e}"
        ) from e
    if not isinstance(parsed, dict):
        raise RuntimeError(
            f"Generated preset did not parse to a YAML mapping. Got: {type(parsed).__name__}"
        )
    # Standalone gold-only output (no splicing) expects {gold}; a spliced gold output
    # is expected to carry the original bronze/silver keys alongside the new gold.
    if target_layers == "gold":
        expected_keys = {"gold"} if existing_preset_text is None else {"bronze", "silver", "gold"}
    elif target_layers == "bronze_silver":
        expected_keys = {"bronze", "silver"}
    elif target_layers == "full":
        expected_keys = {"bronze", "silver", "gold"}
    else:
        expected_keys = None
    if expected_keys and not expected_keys.issubset(parsed.keys()):
        missing = expected_keys - set(parsed.keys())
        raise RuntimeError(
            f"Generated preset is missing required top-level keys: {sorted(missing)}. "
            f"Got: {sorted(parsed.keys())}"
        )
    print(f"✓ YAML validated via SafeLoader (top-level keys: {sorted(parsed.keys())})")
    return parsed


def write_preset(output_path: str, final_yaml: str, overwrite: bool) -> None:
    """Persist to a /Workspace/ or /Volumes/ path, with overwrite protection."""
    if not (output_path.startswith("/Workspace/") or output_path.startswith("/Volumes/")):
        raise ValueError("output_path must start with /Workspace/ or /Volumes/")
    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(
            f"{output_path} already exists and overwrite=false. "
            f"Set the overwrite widget to 'true' to replace it, or pick a new output_path."
        )
    if os.path.exists(output_path) and overwrite:
        print(f"⚠ Overwriting existing file at {output_path}")
    with open(output_path, "w") as f:
        f.write(final_yaml)
    print(f"Wrote {len(final_yaml):,} chars → {output_path}")


print("✓ DSL Lite agent helpers loaded")
