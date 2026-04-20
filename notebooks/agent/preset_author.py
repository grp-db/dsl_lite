# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC # DSL Lite — Preset Author Agent
# MAGIC
# MAGIC Generate a `preset.yaml` from either a Unity Catalog table or raw log files on a
# MAGIC volume, using the **Databricks Foundation Model API**. Runs entirely inside your
# MAGIC workspace — schema and samples never leave your environment.
# MAGIC
# MAGIC **How it works**
# MAGIC 1. Load the preset-authoring skill (`SKILL.md` + `references/`) from a workspace path or
# MAGIC    Unity Catalog volume.
# MAGIC 2. Introspect the input — a UC table (`DESCRIBE` + sample rows) or a volume path of
# MAGIC    raw log files (read file contents directly).
# MAGIC 3. If the input is an already-built silver table and you point at an existing
# MAGIC    `preset.yaml`, load its `bronze:` + `silver:` sections as read-only context.
# MAGIC 4. Build a single system + user prompt. In `silver` mode, ask the model for ONLY the
# MAGIC    `gold:` section. In `raw` mode, ask for a full bronze/silver/gold preset.
# MAGIC 5. Call a Databricks-hosted foundation model via the serving endpoint.
# MAGIC 6. In silver mode, splice the generated `gold:` into the existing preset via a
# MAGIC    text-level concat — your bronze/silver bytes, key order, and comments stay intact.
# MAGIC 7. Review the final `preset.yaml` and (optionally) save it into the repo tree.
# MAGIC
# MAGIC **When to use**
# MAGIC - The customer cannot share sample data externally, and no local IDE-based agent is
# MAGIC   available in their environment.
# MAGIC - You want a first-draft preset grounded in the real schema of a live UC table, which
# MAGIC   you then refine in `notebooks/explorer/preset_explorer.py`.
# MAGIC
# MAGIC **Prerequisites**
# MAGIC - Foundation Model API access enabled on the workspace (a pay-per-token serving
# MAGIC   endpoint such as `databricks-meta-llama-3-3-70b-instruct`).
# MAGIC - The skill bundle uploaded to a workspace folder or UC volume — typically a copy of
# MAGIC   `.agents/skills/dsl-lite-preset-dev/` from this repo.
# MAGIC - One of: `SELECT` on the source UC table, or `READ VOLUME` on the raw-sample volume.

# COMMAND ----------

dbutils.widgets.text(    "source_table",          "",                                    "(Optional if raw_sample_path set) Source UC Table (catalog.schema.table) — used for silver input or raw landing table")
dbutils.widgets.text(    "raw_sample_path",       "",                                    "(Raw mode, no table yet) volume path to a file or folder of raw log samples")
dbutils.widgets.text(    "source_name",           "",                                    "Preset source (e.g. cisco)")
dbutils.widgets.text(    "source_type",           "",                                    "Preset source_type (e.g. ios)")
dbutils.widgets.text(    "ocsf_classes",          "",                                    "(Optional) target OCSF class(es), comma-separated — leave blank to let the model infer")
dbutils.widgets.dropdown("input_layer",           "silver", ["silver", "raw"],           "Input layer (silver → gold-only; raw → full preset)")
dbutils.widgets.text(    "existing_preset_path",  "",                                    "(Optional) existing preset.yaml — silver mode splices new gold in")
dbutils.widgets.text(    "skill_path",            "/Workspace/Shared/dsl_lite/skills/dsl-lite-preset-dev", "Skill folder (SKILL.md + references/)")
dbutils.widgets.text(    "model_endpoint",        "databricks-meta-llama-3-3-70b-instruct", "Serving endpoint name")
dbutils.widgets.text(    "sample_rows",           "auto",                                "Rows to sample — integer or 'auto' to pack as many as fit the prompt budget")
dbutils.widgets.text(    "output_path",           "",                                    "(Optional) full path to write preset.yaml")
dbutils.widgets.dropdown("overwrite",             "false", ["false", "true"],           "Allow overwrite if output_path already exists")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Load the preset-authoring skill
# MAGIC
# MAGIC The skill is a bundle of markdown files that teach the model DSL Lite's preset
# MAGIC conventions: bronze/silver/gold layer patterns, OCSF field mapping, lookup joins, etc.
# MAGIC We concatenate them into a single system-prompt string.

# COMMAND ----------

import os

skill_path    = dbutils.widgets.get("skill_path").rstrip("/")
skill_main    = f"{skill_path}/SKILL.md"
refs_dir      = f"{skill_path}/references"

def _read(p: str) -> str:
    with open(p, "r") as f:
        return f.read()

skill_parts = [f"# FILE: SKILL.md\n\n{_read(skill_main)}"]
for fname in sorted(os.listdir(refs_dir)):
    if fname.endswith(".md"):
        skill_parts.append(f"# FILE: references/{fname}\n\n{_read(f'{refs_dir}/{fname}')}")

skill_context = "\n\n---\n\n".join(skill_parts)
print(f"Loaded {len(skill_parts)} skill file(s), {len(skill_context):,} chars")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Introspect the input
# MAGIC
# MAGIC Two supported inputs:
# MAGIC - **`source_table`** (UC table) — we pull schema + JSON-encoded sample rows. Works for
# MAGIC   silver tables, or raw-landing tables with a single variant column.
# MAGIC - **`raw_sample_path`** (volume path) — used when there's no UC table yet. We read a
# MAGIC   handful of files from the folder (or the single file) verbatim and ship their
# MAGIC   contents as the "sample" block. Intended for `input_layer=raw` bootstrapping.
# MAGIC
# MAGIC Data stays in the workspace — only schema/samples reach the serving endpoint.

# COMMAND ----------

source_table     = dbutils.widgets.get("source_table").strip()
raw_sample_path  = dbutils.widgets.get("raw_sample_path").strip()
sample_rows_raw  = (dbutils.widgets.get("sample_rows") or "auto").strip().lower()

assert source_table or raw_sample_path, (
    "Provide either source_table (UC table) or raw_sample_path (volume path with raw log files)"
)

# In 'auto' mode we fetch an upper-bound number of items, then the prompt-builder
# packs as many as fit the remaining context budget.
_AUTO_ROW_UPPER_BOUND = 200
if sample_rows_raw == "auto":
    n_sample    = _AUTO_ROW_UPPER_BOUND
    auto_sample = True
else:
    n_sample    = int(sample_rows_raw)
    auto_sample = False

# Fill: schema_text, sample_items (list of strings to pack), sample_kind, sample_source_desc.
if source_table:
    schema_rows  = spark.sql(f"DESCRIBE TABLE EXTENDED {source_table}").collect()
    schema_text  = "\n".join(
        f"{r['col_name']:40s} {r['data_type'] or '':30s} {r['comment'] or ''}"
        for r in schema_rows if r['col_name']
    )
    sample_items = [r["_row"] for r in spark.sql(
        f"SELECT to_json(struct(*)) AS _row FROM {source_table} LIMIT {n_sample}"
    ).collect()]
    sample_kind        = "table_rows"
    sample_source_desc = f"Unity Catalog table: `{source_table}`"
else:
    # Raw volume path: read 1 file directly or list a folder and take up to n_sample files.
    if os.path.isdir(raw_sample_path):
        files = sorted(
            os.path.join(raw_sample_path, f)
            for f in os.listdir(raw_sample_path)
            if not f.startswith(".") and os.path.isfile(os.path.join(raw_sample_path, f))
        )[:n_sample]
    else:
        files = [raw_sample_path]
    sample_items = []
    for fp in files:
        with open(fp, "r", errors="replace") as fh:
            sample_items.append(f"# FILE: {fp}\n{fh.read()}")
    schema_text        = "(no UC table — raw files; model must design bronze ingestion)"
    sample_kind        = "raw_files"
    sample_source_desc = f"Raw log files from volume path: `{raw_sample_path}`"

print("── INPUT SOURCE ────────────────────────────────────────")
print(sample_source_desc)
print("\n── SCHEMA ──────────────────────────────────────────────")
print(schema_text[:2000] + ("..." if len(schema_text) > 2000 else ""))
print(f"\n── Pulled {len(sample_items)} sample item(s), "
      f"{sum(len(s) for s in sample_items):,} chars total (mode={'auto' if auto_sample else 'fixed'})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Load existing preset (optional, silver mode only)
# MAGIC
# MAGIC When `input_layer=silver` and `existing_preset_path` is set, we keep the existing
# MAGIC `bronze:` + `silver:` sections verbatim and only ask the model to (re)generate the
# MAGIC `gold:` section. The existing bronze/silver YAML is passed to the model as context so
# MAGIC it can reference real silver column names when authoring the OCSF mappings.
# MAGIC
# MAGIC Uses PyYAML's `safe_load` (preinstalled on Databricks serverless — no `%pip install`
# MAGIC needed) for parsing, and text-level splicing so your existing bronze/silver bytes,
# MAGIC comments, and key order are preserved byte-for-byte.

# COMMAND ----------

import yaml

input_layer          = dbutils.widgets.get("input_layer").strip()
existing_preset_path = dbutils.widgets.get("existing_preset_path").strip()

def _is_top_level_gold(line: str) -> bool:
    """True if `line` is a top-level `gold:` mapping key (col 0, no indent)."""
    if not line.startswith("gold:"):
        return False
    # accept: "gold:", "gold: ", "gold:\n", "gold:# comment" etc.
    return len(line) == 5 or line[5] in (" ", "\t", "\n", "\r", "#")

def _split_at_gold(yaml_text: str) -> tuple[str, str]:
    """Return (text before top-level `gold:`, text from `gold:` onward).
    If no top-level `gold:` is found, returns (full_text, '')."""
    lines = yaml_text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if _is_top_level_gold(line):
            return "".join(lines[:i]), "".join(lines[i:])
    return yaml_text, ""

existing_preset_text   = None   # raw bytes of the existing preset, used for splicing
existing_bronze_silver = None   # everything in the existing preset before `gold:` — prompt context

if existing_preset_path:
    with open(existing_preset_path, "r") as f:
        existing_preset_text = f.read()
    # safe_load purely for validation — surfaces a clear error if the file is malformed
    # before we waste a model call on garbage context.
    parsed = yaml.safe_load(existing_preset_text)
    if not isinstance(parsed, dict):
        raise ValueError(f"{existing_preset_path} must be a YAML mapping at top level.")
    before_gold, _ = _split_at_gold(existing_preset_text)
    existing_bronze_silver = before_gold if before_gold.strip() else None
    print(f"Loaded existing preset from {existing_preset_path} "
          f"(top-level keys: {list(parsed.keys())})")
else:
    print("No existing_preset_path — model will emit a fresh preset.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Build the prompt
# MAGIC
# MAGIC System prompt holds the skill bundle. User prompt varies by mode:
# MAGIC - **silver**: ask for only the `gold:` section (and show existing bronze/silver if available).
# MAGIC - **raw**: ask for the full bronze/silver/gold preset (original behavior).

# COMMAND ----------

source_name   = dbutils.widgets.get("source_name").strip()
source_type   = dbutils.widgets.get("source_type").strip()
ocsf_classes  = [c.strip() for c in dbutils.widgets.get("ocsf_classes").split(",") if c.strip()]

assert source_name and source_type, "source_name and source_type widgets are required"

# Prompt budget. Use a conservative floor that works across the common Databricks FMAPI
# endpoints (Llama 3.3 70B = 128K tokens, Claude Sonnet 4 = 200K, etc.). 400K chars ≈
# 100K tokens leaves ~28K tokens of headroom on the smallest supported endpoint.
MODEL_INPUT_CHAR_BUDGET = 400_000
RESERVED_OUTPUT_CHARS   = 32_000   # matches max_tokens=8000 (~4 chars/token)
RESERVED_OVERHEAD_CHARS = 4_000    # scaffolding around the sample block

bs_len            = len(existing_bronze_silver) if existing_bronze_silver else 0
budget_for_sample = max(
    0,
    MODEL_INPUT_CHAR_BUDGET
    - len(skill_context)
    - len(schema_text)
    - bs_len
    - RESERVED_OUTPUT_CHARS
    - RESERVED_OVERHEAD_CHARS,
)

# Pack items one at a time until we'd blow the budget. Works for both table rows
# (each item is a JSON string) and raw files (each item is a whole file body).
_packed  = []
_running = 2  # array brackets / file separators
for _s in sample_items:
    _delta = len(_s) + 4
    if _running + _delta > budget_for_sample:
        break
    _packed.append(_s)
    _running += _delta

_truncated = len(_packed) < len(sample_items)
if sample_kind == "table_rows":
    sample_block = "[\n" + ",\n".join("  " + s for s in _packed) + ("\n... [truncated]" if _truncated else "") + "\n]"
    sample_fence = "json"
    sample_label = "Sample rows (JSON)"
else:
    sample_block = "\n\n---\n\n".join(_packed) + ("\n\n... [truncated additional files]" if _truncated else "")
    sample_fence = ""
    sample_label = "Raw sample file contents"

print(f"packed {len(_packed)}/{len(sample_items)} sample item(s) → {len(sample_block):,} chars "
      f"(budget {budget_for_sample:,} chars)")
print(f"\n── {sample_label.upper()} (preview) ────────────────────")
print(sample_block[:2000] + ("..." if len(sample_block) > 2000 else ""))

# OCSF classes: user-provided list, else delegate selection to the model.
if ocsf_classes:
    ocsf_line  = ", ".join(ocsf_classes)
    ocsf_note  = "Map fields to the listed OCSF classes using the skill's gold-table rules."
else:
    ocsf_line  = "(not specified — infer 1–3 appropriate classes from the schema + sample)"
    ocsf_note  = (
        "No OCSF classes were specified. Pick 1–3 appropriate OCSF gold classes from the "
        "skill's class catalog based on the schema and sample rows, emit a gold section for "
        "each, and include a top-of-file YAML comment listing the classes you selected and why."
    )

# Silver mode is only coherent if we have a real silver TABLE to map against —
# raw files alone don't define a silver schema.
if input_layer == "silver" and sample_kind == "raw_files":
    raise ValueError(
        "input_layer=silver requires a UC source_table. For raw files, switch input_layer=raw."
    )

sample_fenced = f"```{sample_fence}\n{sample_block}\n```" if sample_fence else sample_block

# Universal blueprint requirements enforced on every generation. The skill references
# teach the details; these are the checks most worth hammering in the prompt itself
# because past runs have shown models hallucinate them when the skill context is long.
UNIVERSAL_REQUIREMENTS = [
    "Include `metadata:` on every gold class — it is always required (version, product.name, product.vendor_name, log_provider, log_name, log_format, logged_time, processed_time).",
    "Include the class-appropriate objects per the skill's mapping reference: `src_endpoint`/`dst_endpoint` for Network (4xxx) and IAM/Authentication (3xxx); `device` for Process / File / Script activity. Never mix endpoint and device on the same class.",
    "Set `activity_id`, `category_uid`, `class_uid`, `type_uid`, and `severity_id` to values defined by the OCSF enum for each target class — do not invent values.",
    "Preserve the source event time in the `time` field as unix milliseconds; populate `metadata.logged_time` from the bronze ingestion timestamp.",
    "Use `try_variant_get` (not `variant_get`) for any VARIANT/JSON payload access so missing keys yield NULL instead of runtime errors.",
    "Use OCSF field names exactly (snake_case, dotted paths like `src_endpoint.ip`). Do not invent fields that are not in the OCSF schema for the target class.",
    "Include `raw_data` or `unmapped` reference back to the bronze record for traceability when the skill pattern calls for it.",
    "Output ONLY the YAML document. Do not wrap it in triple backticks, do not add prose before or after.",
]
_UNIV_BULLETS = "\n".join(f"- {r}" for r in UNIVERSAL_REQUIREMENTS)

if input_layer == "silver":
    system_prompt = (
        "You are a DSL Lite preset author. You produce ONLY a valid YAML document — "
        "no prose, no code fences, no commentary outside the YAML. The input UC table is "
        "ALREADY the silver layer (parsed, typed, normalized). You MUST emit ONLY a top-level "
        "`gold:` key mapping silver columns to OCSF classes. DO NOT emit `bronze:` or `silver:` "
        "keys — those layers already exist and must not be altered. "
        "Follow every convention in the skill reference below exactly.\n\n"
        + skill_context
    )
    existing_bs_block = (
        f"\n\nExisting bronze/silver sections (read-only reference — DO NOT re-emit):\n"
        f"```yaml\n{existing_bronze_silver}```\n"
    ) if existing_bronze_silver else ""
    user_prompt = f"""Author ONLY the `gold:` section of `preset.yaml` for this data source.

Source identifiers:
- source:      {source_name}
- source_type: {source_type}
- target path: pipelines/{source_name}/{source_type}/preset.yaml

Target OCSF gold classes: {ocsf_line}

The input table below is the SILVER layer (already parsed). Map its columns to the
OCSF gold classes per the skill's gold-table rules.

Input: {sample_source_desc}

Silver table schema (col_name / data_type / comment):
```
{schema_text}
```

{sample_label}:
{sample_fenced}
{existing_bs_block}
Mode-specific requirements (silver → gold-only):
- Output a YAML document whose ONLY top-level key is `gold:`.
- Do NOT include `bronze:` or `silver:` keys under any circumstance — those layers already exist and must not be altered.
- {ocsf_note}

Universal preset requirements (apply to every gold class):
{_UNIV_BULLETS}
"""
else:
    system_prompt = (
        "You are a DSL Lite preset author. You produce ONLY a valid preset.yaml file — "
        "no prose, no code fences, no commentary outside the YAML. "
        "Follow every convention in the skill reference below exactly.\n\n"
        + skill_context
    )
    # Raw-file mode gives the model file contents instead of a parsed schema;
    # the model needs to design the bronze ingestion pattern from scratch.
    if sample_kind == "raw_files":
        input_block = (
            f"Input: {sample_source_desc}\n\n"
            f"No UC table exists yet — design the bronze ingestion pipeline (e.g. Auto Loader "
            f"over the volume path, variant column for unparsed payload) based on the raw file "
            f"contents below.\n\n"
            f"{sample_label}:\n{sample_fenced}\n"
        )
    else:
        input_block = (
            f"Input: {sample_source_desc}\n\n"
            f"Table schema (col_name / data_type / comment):\n```\n{schema_text}\n```\n\n"
            f"{sample_label}:\n{sample_fenced}\n"
        )
    user_prompt = f"""Author a complete `preset.yaml` for this data source.

Source identifiers:
- source:      {source_name}
- source_type: {source_type}
- target path: pipelines/{source_name}/{source_type}/preset.yaml

Target OCSF gold classes: {ocsf_line}

{input_block}
Mode-specific requirements (raw → full preset):
- Produce bronze, silver, and gold sections consistent with the skill references.
- Bronze should preserve the raw payload (variant or string), silver should parse/normalize, gold should map to OCSF.
- {ocsf_note}

Universal preset requirements (apply to every gold class):
{_UNIV_BULLETS}
"""

_total_chars = len(system_prompt) + len(user_prompt)
print(f"\nsystem prompt: {len(system_prompt):,} chars")
print(f"user prompt:   {len(user_prompt):,} chars")
print(f"total:         {_total_chars:,} chars  (~{_total_chars // 4:,} tokens; budget {MODEL_INPUT_CHAR_BUDGET:,} chars)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Call the Databricks Foundation Model API
# MAGIC
# MAGIC Uses the Databricks SDK to query a serving endpoint in the current workspace. The
# MAGIC endpoint is configurable via the `model_endpoint` widget — any chat-completions
# MAGIC compatible foundation model on the workspace will work.

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

model_endpoint = dbutils.widgets.get("model_endpoint").strip()
w              = WorkspaceClient()

def _query_model(messages):
    """Call the serving endpoint, handling Claude/Llama temperature quirks."""
    kwargs = dict(name=model_endpoint, messages=messages, max_tokens=8000)
    # Claude extended-thinking endpoints reject non-1.0 temperature; other Claude
    # variants accept 0 for determinism; Llama/others take the usual range.
    if "claude-opus" in model_endpoint or "thinking" in model_endpoint:
        pass
    elif "claude" in model_endpoint:
        kwargs["temperature"] = 0.0
    else:
        kwargs["temperature"] = 0.1
    return w.serving_endpoints.query(**kwargs).choices[0].message.content.strip()

def _strip_fences(s: str) -> str:
    if s.startswith("```"):
        s = "\n".join(s.splitlines()[1:])
        if s.rstrip().endswith("```"):
            s = s.rstrip().rstrip("`").rstrip()
    return s

preset_yaml = _strip_fences(_query_model([
    ChatMessage(role=ChatMessageRole.SYSTEM, content=system_prompt),
    ChatMessage(role=ChatMessageRole.USER,   content=user_prompt),
]))

print(preset_yaml)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Assemble final preset (splice if silver mode + existing preset)
# MAGIC
# MAGIC In silver mode with an existing preset, the model returned only a `gold:` block.
# MAGIC We validate it with `yaml.safe_load` and then do a text-level splice: everything in
# MAGIC your existing preset up to the old `gold:` line is kept verbatim, and the model's
# MAGIC new `gold:` block replaces whatever came after. This preserves your bronze/silver
# MAGIC bytes, comments, and key order exactly — no YAML round-tripping involved.

# COMMAND ----------

def _splice_gold(base_text: str, generated_yaml_text: str) -> str:
    """Concat `base_text` (bytes before its top-level `gold:`) with the model's gold block."""
    # Validate the model's response parses and has a top-level `gold:` key.
    gen = yaml.safe_load(generated_yaml_text)
    if not isinstance(gen, dict) or "gold" not in gen:
        keys = list(gen.keys()) if isinstance(gen, dict) else type(gen).__name__
        raise ValueError(
            f"Model response in silver mode must be a YAML doc with a top-level `gold:` key. "
            f"Got top-level keys: {keys}"
        )
    before_gold, _ = _split_at_gold(base_text)
    before = before_gold.rstrip() + "\n\n" if before_gold.strip() else ""
    after  = generated_yaml_text.lstrip()
    if not after.endswith("\n"):
        after += "\n"
    return before + after

if input_layer == "silver" and existing_preset_text is not None:
    # _splice_gold already calls yaml.safe_load on the model response, so the result
    # is guaranteed to parse. No second validation needed here.
    final_yaml = _splice_gold(existing_preset_text, preset_yaml)
    print("── SPLICED PRESET (existing bronze/silver + new gold) ──")
else:
    final_yaml = preset_yaml
    print("── FINAL PRESET ────────────────────────────────────────")

# Validate the final document parses as YAML before we let the user save or downstream
# consumers pick it up. Uses SafeLoader via yaml.safe_load — no arbitrary Python
# object deserialization. Required by customer security posture.
try:
    parsed_final = yaml.safe_load(final_yaml)
except yaml.YAMLError as e:
    raise RuntimeError(
        f"Generated preset is not valid YAML — refuse to save. Parser error: {e}"
    ) from e
if not isinstance(parsed_final, dict):
    raise RuntimeError(
        f"Generated preset did not parse to a YAML mapping. Got: {type(parsed_final).__name__}"
    )
expected_keys = {"gold"} if input_layer == "silver" and existing_preset_text is None else {"bronze", "silver", "gold"} if input_layer == "raw" else None
if expected_keys and not expected_keys.issubset(parsed_final.keys()):
    missing = expected_keys - set(parsed_final.keys())
    raise RuntimeError(
        f"Generated preset is missing required top-level keys: {sorted(missing)}. "
        f"Got: {sorted(parsed_final.keys())}"
    )
print(f"✓ YAML validated via SafeLoader (top-level keys: {sorted(parsed_final.keys())})")
print(final_yaml[:4000] + ("..." if len(final_yaml) > 4000 else ""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. (Optional) Save the final preset
# MAGIC
# MAGIC Set the `output_path` widget to a workspace path (`/Workspace/...`) or a UC volume
# MAGIC path (`/Volumes/...`) to persist the file. Leave blank to skip.

# COMMAND ----------

output_path = dbutils.widgets.get("output_path").strip()
overwrite   = dbutils.widgets.get("overwrite").strip().lower() == "true"

if output_path:
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
else:
    print("output_path is empty — not saving. Copy the YAML above into your repo manually.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Refine with feedback (optional)
# MAGIC
# MAGIC Edit the `feedback` string below and re-run this cell to iterate on the generated
# MAGIC preset without re-introspecting the table. In silver mode the model is told to
# MAGIC return only the `gold:` block, and we re-splice into the existing preset.

# COMMAND ----------

feedback = """
# Example refinements — replace with your own:
# - Add a lookup join for user_id → user_name
# - Map field `event.action` to activity_id per OCSF authentication class
"""

if feedback.strip() and not feedback.strip().startswith("#"):
    scope_note = (
        "Return ONLY an updated `gold:` YAML block (no bronze/silver)."
        if input_layer == "silver"
        else "Return the full updated preset.yaml."
    )
    refined = _strip_fences(_query_model([
        ChatMessage(role=ChatMessageRole.SYSTEM,    content=system_prompt),
        ChatMessage(role=ChatMessageRole.USER,      content=user_prompt),
        ChatMessage(role=ChatMessageRole.ASSISTANT, content=preset_yaml),
        ChatMessage(role=ChatMessageRole.USER,      content=f"Apply these refinements. {scope_note}\n\n{feedback}"),
    ]))

    preset_yaml = refined
    if input_layer == "silver" and existing_preset_text is not None:
        final_yaml = _splice_gold(existing_preset_text, preset_yaml)
    else:
        final_yaml = preset_yaml
    print(final_yaml)
else:
    print("No feedback supplied — skipping refinement.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next steps
# MAGIC
# MAGIC 1. Copy the generated `preset.yaml` into `pipelines/<source>/<source_type>/preset.yaml`.
# MAGIC 2. Validate it against real sample data using
# MAGIC    [`notebooks/explorer/preset_explorer.py`](../explorer/preset_explorer.py).
# MAGIC 3. Deploy with the matching bundle under `bundles/<source>/<source_type>/`.
