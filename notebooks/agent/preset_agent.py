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
# MAGIC
# MAGIC > **⚠️ Serverless environment version**
# MAGIC > This notebook imports `pyyaml`, which is bundled in serverless environment **v2+**.
# MAGIC > If you see `ModuleNotFoundError: No module named 'yaml'`, open the **Environment**
# MAGIC > side panel on the right and switch to the latest environment version.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Widget reference
# MAGIC
# MAGIC ### Source identity (required)
# MAGIC | Widget | Default | Purpose |
# MAGIC |---|---|---|
# MAGIC | `source_name` | _(empty)_ | Preset source slug (e.g. `cisco`, `zeek`, `cloudflare`). Required. |
# MAGIC | `source_type` | _(empty)_ | Preset source_type slug (e.g. `ios`, `conn`, `gateway_dns`). Required. |
# MAGIC
# MAGIC ### Input — one of these must be set
# MAGIC | Widget | Default | Purpose |
# MAGIC |---|---|---|
# MAGIC | `source_table` | _(empty)_ | UC table `catalog.schema.table`. Use for an already-parsed silver table or a variant-style raw landing table. |
# MAGIC | `raw_sample_path` | _(empty)_ | Volume path to a file **or folder** of raw log samples. Use when no UC table exists yet. |
# MAGIC | `input_layer` | `silver` | `silver` = input is a parsed UC table. `raw` = input is raw log files. |
# MAGIC
# MAGIC ### Output control
# MAGIC | Widget | Default | Purpose |
# MAGIC |---|---|---|
# MAGIC | `target_layers` | `auto` | What to emit. `auto` = silver→gold, raw→full. Explicit values: `full` (bronze+silver+gold), `bronze_silver`, `gold`. |
# MAGIC | `ocsf_classes` | _(empty)_ | Comma-separated OCSF class(es) to map to. Leave blank to let the model infer 1–3. |
# MAGIC | `existing_preset_path` | _(empty)_ | For `target_layers=gold` only: path to an existing `preset.yaml` — splices the new gold block in, preserving bronze/silver bytes. |
# MAGIC
# MAGIC ### Additional context (optional)
# MAGIC | Widget | Default | Purpose |
# MAGIC |---|---|---|
# MAGIC | `source_docs` | _(empty)_ | Vendor field documentation injected after sample data. Accepts a **URL** (fetched at runtime, best-effort) or **pasted text** (schema tables, field descriptions, enum values). Fall back to pasted text if the URL fetch fails (e.g. outbound access blocked). |
# MAGIC | `ddl_path` | _(empty)_ | Workspace path to `notebooks/ddl/create_ocsf_tables.py`. When set, the agent is constrained to only generate gold fields that exist in the enforced Delta DDL — prevents invented OCSF fields that would fail on pipeline deployment. |
# MAGIC
# MAGIC ### Sampling (raw mode especially)
# MAGIC | Widget | Default | Purpose |
# MAGIC |---|---|---|
# MAGIC | `sample_rows` | `auto` | Rows / files to sample. Integer, `auto` (pack to prompt budget, capped at 200), or `all` (no count cap). |
# MAGIC | `sample_filter` | _(empty)_ | UC-table mode only. Optional SQL `WHERE` clause body (no leading `WHERE`) to filter sample rows before sampling. Use to skip rows where key columns are NULL so the model sees meaningful data — e.g. `dns_record IS NOT NULL`. |
# MAGIC | `max_file_bytes` | `65536` | Raw mode only. Max bytes read per file (default 64KB). `0` = full opt-out of per-file and cumulative caps. |
# MAGIC
# MAGIC ### Environment
# MAGIC | Widget | Default | Purpose |
# MAGIC |---|---|---|
# MAGIC | `skill_path` | `/Workspace/Shared/dsl_lite/skills/dsl-lite-preset-dev` | Folder containing `SKILL.md` + `references/*.md`. |
# MAGIC | `model_endpoint` | `databricks-claude-opus-4-7` | Serving endpoint name. Opus 4.7 is the most reliable for complex OCSF mappings; Sonnet 4.7 works and is cheaper; Llama 3.3 frequently fails YAML parse. |
# MAGIC
# MAGIC ### Save
# MAGIC | Widget | Default | Purpose |
# MAGIC |---|---|---|
# MAGIC | `output_path` | _(empty)_ | Where to write the final YAML. Must start with `/Workspace/` or `/Volumes/`. Blank = skip save. |
# MAGIC | `overwrite` | `false` | Allow overwriting an existing file at `output_path`. |

# COMMAND ----------

dbutils.widgets.text(    "source_table",          "",                                    "(Optional if raw_sample_path set) Source UC Table (catalog.schema.table) — used for silver input or raw landing table")
dbutils.widgets.text(    "raw_sample_path",       "",                                    "(Raw mode, no table yet) volume path to a file or folder of raw log samples")
dbutils.widgets.text(    "source_name",           "",                                    "Preset source (e.g. cisco)")
dbutils.widgets.text(    "source_type",           "",                                    "Preset source_type (e.g. ios)")
dbutils.widgets.text(    "ocsf_classes",          "",                                    "(Optional) target OCSF class(es), comma-separated — leave blank to let the model infer")
dbutils.widgets.dropdown("input_layer",           "silver", ["silver", "raw"],           "Input layer — silver = UC table already parsed; raw = volume of raw files")
dbutils.widgets.dropdown("target_layers",         "auto",   ["auto", "full", "bronze_silver", "gold"], "Layers to emit — auto infers from input_layer (silver→gold, raw→full)")
dbutils.widgets.text(    "existing_preset_path",  "",                                    "(Optional, gold target) existing preset.yaml — splices the new gold: block in")
dbutils.widgets.text(    "skill_path",            "/Workspace/Shared/dsl_lite/skills/dsl-lite-preset-dev", "Skill folder (SKILL.md + references/)")
dbutils.widgets.text(    "model_endpoint",        "databricks-claude-opus-4-7",          "Serving endpoint name")
dbutils.widgets.text(    "sample_rows",           "auto",                                "Rows / files to sample — integer, 'auto' (pack to prompt budget), or 'all' (no cap)")
dbutils.widgets.text(    "sample_filter",         "",                                    "(UC-table mode) optional SQL WHERE clause body to filter sample rows, e.g. `dns_record IS NOT NULL`")
dbutils.widgets.text(    "max_file_bytes",        "65536",                               "(Raw mode) max bytes per file; 0 disables both per-file and cumulative caps — full opt-out")
dbutils.widgets.text(    "source_docs",           "",                                    "(Optional) vendor docs URL (fetched at runtime) or pasted text — schema tables, field descriptions, enum values")
dbutils.widgets.text(    "ddl_path",              "",                                    "(Optional) path to create_ocsf_tables.py — constrains gold fields to DDL-defined columns only")
dbutils.widgets.text(    "output_path",           "",                                    "(Optional) full path to write preset.yaml")
dbutils.widgets.dropdown("overwrite",             "false", ["false", "true"],           "Allow overwrite if output_path already exists")

# COMMAND ----------

# MAGIC %run ./agent_helpers

# COMMAND ----------

# Read widgets once, up front.
source_table         = dbutils.widgets.get("source_table").strip()
raw_sample_path      = dbutils.widgets.get("raw_sample_path").strip()
source_name          = dbutils.widgets.get("source_name").strip()
source_type          = dbutils.widgets.get("source_type").strip()
ocsf_classes         = [c.strip() for c in dbutils.widgets.get("ocsf_classes").split(",") if c.strip()]
input_layer          = dbutils.widgets.get("input_layer").strip()
target_layers_raw    = dbutils.widgets.get("target_layers").strip()
existing_preset_path = dbutils.widgets.get("existing_preset_path").strip()
skill_path           = dbutils.widgets.get("skill_path").rstrip("/")
model_endpoint       = dbutils.widgets.get("model_endpoint").strip()
sample_rows_raw      = dbutils.widgets.get("sample_rows")
sample_filter        = dbutils.widgets.get("sample_filter").strip()
max_file_bytes       = int(dbutils.widgets.get("max_file_bytes").strip() or "65536")
source_docs          = dbutils.widgets.get("source_docs").strip()
ddl_path             = dbutils.widgets.get("ddl_path").strip()
output_path          = dbutils.widgets.get("output_path").strip()

_SOURCE_DOCS_CHAR_CAP = 20_000  # ~5K tokens — enough for a field reference table

if source_docs.startswith("http"):
    try:
        import urllib.request, re as _re
        _req = urllib.request.Request(
            source_docs,
            headers={"User-Agent": "Mozilla/5.0 (compatible; DSLLiteAgent/1.0)"},
        )
        with urllib.request.urlopen(_req, timeout=10) as _r:
            _raw = _re.sub(r"<[^>]+>", " ", _r.read().decode("utf-8", errors="replace"))
            source_docs = _re.sub(r"[ \t]{2,}", " ", _re.sub(r"\n{3,}", "\n\n", _raw)).strip()
        if len(source_docs) > _SOURCE_DOCS_CHAR_CAP:
            source_docs = source_docs[:_SOURCE_DOCS_CHAR_CAP]
            print(f"  source_docs: truncated to {_SOURCE_DOCS_CHAR_CAP:,} chars (full page was larger)")
        else:
            print(f"  source_docs: fetched {len(source_docs):,} chars")
    except Exception as _e:
        print(f"  ⚠ source_docs URL fetch failed ({_e}) — paste text directly into the widget instead")
        source_docs = ""
elif len(source_docs) > _SOURCE_DOCS_CHAR_CAP:
    source_docs = source_docs[:_SOURCE_DOCS_CHAR_CAP]
    print(f"  source_docs: truncated pasted text to {_SOURCE_DOCS_CHAR_CAP:,} chars")

source_docs_block = (
    f"\n## Source Field Reference\n\n{source_docs}\n"
    if source_docs else ""
)
overwrite            = dbutils.widgets.get("overwrite").strip().lower() == "true"

assert source_name and source_type, "source_name and source_type widgets are required"

# Resolve target_layers=auto → {full | bronze_silver | gold} and validate the
# combination against input_layer. Use this value (not the widget text) everywhere downstream.
target_layers = resolve_target_layers(input_layer, target_layers_raw)
print(f"input_layer={input_layer}  →  target_layers={target_layers}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Load the preset-authoring skill

# COMMAND ----------

skill_context = load_skill(skill_path)

# COMMAND ----------

ocsf_schemas = load_ocsf_ddl_schemas(ddl_path) if ddl_path else {}
schema_constraints_block = build_ocsf_schema_constraints(ocsf_classes, ocsf_schemas) if ocsf_schemas else ""
if schema_constraints_block:
    print(f"  OCSF schema constraints: {len(schema_constraints_block):,} chars "
          f"({len(ocsf_classes) if ocsf_classes else len(ocsf_schemas)} table(s) constrained)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Introspect the input
# MAGIC
# MAGIC Two supported inputs:
# MAGIC - **`source_table`** (UC table) — we pull schema + JSON-encoded sample rows.
# MAGIC - **`raw_sample_path`** (volume path) — raw file contents, for `input_layer=raw`.
# MAGIC
# MAGIC Data stays in the workspace — only schema/samples reach the serving endpoint.

# COMMAND ----------

n_sample, auto_sample = resolve_sample_rows(sample_rows_raw)
intro = introspect_input(source_table, raw_sample_path, n_sample, max_file_bytes, sample_filter)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Load existing preset (optional, gold-target only)
# MAGIC
# MAGIC When `target_layers=gold` and `existing_preset_path` is set, we keep the existing
# MAGIC `bronze:` + `silver:` sections verbatim and only ask the model to (re)generate the
# MAGIC `gold:` section. Useful for the two-pass workflow: deploy `bronze_silver` first,
# MAGIC then come back and add `gold` against the now-populated silver table.

# COMMAND ----------

existing_preset_text, existing_bronze_silver = load_existing_preset(existing_preset_path)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Pack sample rows against the prompt budget

# COMMAND ----------

budget = compute_sample_budget(skill_context, intro["schema_text"], existing_bronze_silver, source_docs, schema_constraints_block)
sample = pack_samples(intro["sample_items"], intro["sample_kind"], budget)

print_input_summary(intro, sample["packed_count"], sample["total_count"], auto_sample)
print(f"\npacked {sample['packed_count']}/{sample['total_count']} sample item(s) → "
      f"{len(sample['block']):,} chars (budget {budget:,} chars)")
print(f"\n── {sample['label'].upper()} (preview) ────────────────────")
print(sample["block"][:2000] + ("..." if len(sample["block"]) > 2000 else ""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Build the prompts — **edit this cell to tune the agent**
# MAGIC
# MAGIC The system prompt holds the skill bundle; the user prompt varies by `target_layers`:
# MAGIC
# MAGIC | `target_layers` | Requires | Produces | Notes |
# MAGIC |-----------------|----------|----------|-------|
# MAGIC | `full`          | raw      | `bronze:` + `silver:` + `gold:` | Original raw-mode behaviour. |
# MAGIC | `bronze_silver` | raw      | `bronze:` + `silver:` only      | Deploy/iterate B+S first; revisit gold later. |
# MAGIC | `gold`          | silver   | `gold:` only                    | Splices into `existing_preset_path` if provided. |
# MAGIC
# MAGIC Tweak the wording, bullets, or scope below — re-run this cell and the model call
# MAGIC cell without re-introspecting the source.

# COMMAND ----------

# Silver input requires a parsed table — raw files alone have no silver schema.
if input_layer == "silver" and intro["sample_kind"] == "raw_files":
    raise ValueError(
        "input_layer=silver requires a UC source_table. For raw files, switch input_layer=raw."
    )

# OCSF directive — inferred by the model if `ocsf_classes` is empty.
if ocsf_classes:
    ocsf_line = ", ".join(ocsf_classes)
    ocsf_note = "Map fields to the listed OCSF classes using the skill's gold-table rules."
else:
    ocsf_line = "(not specified — infer 1–3 appropriate classes from the schema + sample)"
    ocsf_note = (
        "No OCSF classes were specified. Pick 1–3 appropriate OCSF gold classes from the "
        "skill's class catalog based on the schema and sample rows, emit a gold section for "
        "each, and include a top-of-file YAML comment listing the classes you selected and why."
    )

# Only include OCSF-specific requirements when we're actually emitting a gold section.
emits_gold   = target_layers in ("full", "gold")
reqs         = OUTPUT_FORMAT_REQUIREMENTS + (GOLD_REQUIREMENTS if emits_gold else [])
reqs_bullets = "\n".join(f"- {r}" for r in reqs)
reqs_header  = ("Universal preset requirements (apply to every gold class):"
                if emits_gold else "Universal preset requirements:")

sample_fenced = (f"```{sample['fence']}\n{sample['block']}\n```"
                 if sample["fence"] else sample["block"])

if target_layers == "gold":
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

Input: {intro['sample_source_desc']}

Silver table schema (col_name / data_type / comment):
```
{intro['schema_text']}
```

{sample['label']}:
{sample_fenced}
{existing_bs_block}{source_docs_block}{schema_constraints_block}
Mode-specific requirements (silver → gold-only):
- Output a YAML document whose ONLY top-level key is `gold:`.
- Do NOT include `bronze:` or `silver:` keys under any circumstance — those layers already exist and must not be altered.
- {ocsf_note}

{reqs_header}
{reqs_bullets}
"""
elif target_layers == "bronze_silver":
    system_prompt = (
        "You are a DSL Lite preset author. You produce ONLY a valid YAML document — "
        "no prose, no code fences, no commentary outside the YAML. You MUST emit ONLY "
        "top-level `bronze:` and `silver:` keys. DO NOT emit a `gold:` key — the gold "
        "(OCSF) layer will be authored in a follow-up pass once the silver table exists "
        "and can be validated. "
        "Follow every convention in the skill reference below exactly.\n\n"
        + skill_context
    )
    input_block = (
        f"Input: {intro['sample_source_desc']}\n\n"
        f"No UC table exists yet — design the bronze ingestion pipeline (e.g. Auto Loader "
        f"over the volume path, variant column for unparsed payload) based on the raw file "
        f"contents below.\n\n"
        f"{sample['label']}:\n{sample_fenced}\n"
    )
    user_prompt = f"""Author ONLY the `bronze:` and `silver:` sections of `preset.yaml` for this data source.

Source identifiers:
- source:      {source_name}
- source_type: {source_type}
- target path: pipelines/{source_name}/{source_type}/preset.yaml

{input_block}{source_docs_block}
Mode-specific requirements (raw → bronze + silver only):
- Output a YAML document whose top-level keys are EXACTLY `bronze:` and `silver:` — no `gold:`.
- Bronze should preserve the raw payload (variant or string) and capture ingestion metadata.
- Silver should parse/normalize into typed columns ready for downstream OCSF mapping.
- Do NOT include `gold:` under any circumstance — the gold layer is deferred to a later pass.

{reqs_header}
{reqs_bullets}
"""
else:  # target_layers == "full"
    system_prompt = (
        "You are a DSL Lite preset author. You produce ONLY a valid preset.yaml file — "
        "no prose, no code fences, no commentary outside the YAML. "
        "Follow every convention in the skill reference below exactly.\n\n"
        + skill_context
    )
    input_block = (
        f"Input: {intro['sample_source_desc']}\n\n"
        f"No UC table exists yet — design the bronze ingestion pipeline (e.g. Auto Loader "
        f"over the volume path, variant column for unparsed payload) based on the raw file "
        f"contents below.\n\n"
        f"{sample['label']}:\n{sample_fenced}\n"
    )
    user_prompt = f"""Author a complete `preset.yaml` for this data source.

Source identifiers:
- source:      {source_name}
- source_type: {source_type}
- target path: pipelines/{source_name}/{source_type}/preset.yaml

Target OCSF gold classes: {ocsf_line}

{input_block}{source_docs_block}{schema_constraints_block}
Mode-specific requirements (raw → full preset):
- Produce bronze, silver, and gold sections consistent with the skill references.
- Bronze should preserve the raw payload (variant or string), silver should parse/normalize, gold should map to OCSF.
- {ocsf_note}

{reqs_header}
{reqs_bullets}
"""

print_prompt_summary(system_prompt, user_prompt)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Call the Databricks Foundation Model API

# COMMAND ----------

w = WorkspaceClient()

preset_yaml = strip_fences(query_model(w, model_endpoint, [
    ChatMessage(role=ChatMessageRole.SYSTEM, content=system_prompt),
    ChatMessage(role=ChatMessageRole.USER,   content=user_prompt),
]))

print(preset_yaml)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Assemble final preset (splice if gold target + existing preset)
# MAGIC
# MAGIC With `target_layers=gold` and an existing preset, the model returned only a `gold:`
# MAGIC block. We validate it and do a text-level splice: everything up to the old `gold:`
# MAGIC line is kept verbatim, and the new `gold:` block replaces whatever came after.

# COMMAND ----------

final_yaml = assemble_final(
    preset_yaml=preset_yaml,
    existing_preset_text=existing_preset_text,
    target_layers=target_layers,
)

print_header = ("── SPLICED PRESET (existing bronze/silver + new gold) ──"
                if target_layers == "gold" and existing_preset_text is not None
                else "── FINAL PRESET ────────────────────────────────────────")
print(print_header)
# Print BEFORE validating so that a parse failure still shows the assembled text —
# you can hand-edit `final_yaml` in a scratch cell and re-run validate + section 8.
print(final_yaml[:4000] + ("..." if len(final_yaml) > 4000 else ""))

parsed = validate_final_yaml(final_yaml, target_layers, existing_preset_text)

# Prepend the human-readable file header (skip for gold splice — existing header stays).
if not (target_layers == "gold" and existing_preset_text is not None):
    file_header = build_preset_header(
        model_endpoint=model_endpoint,
        source_name=source_name,
        source_type=source_type,
        raw_sample_path=raw_sample_path,
        source_table=source_table,
        preset_parsed=parsed,
    )
    final_yaml = file_header + final_yaml

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. (Optional) Save the final preset
# MAGIC
# MAGIC Set the `output_path` widget to a workspace path (`/Workspace/...`) or a UC volume
# MAGIC path (`/Volumes/...`) to persist the file. Leave blank to skip.

# COMMAND ----------

if output_path:
    write_preset(output_path, final_yaml, overwrite)
else:
    print("output_path is empty — not saving. Copy the YAML above into your repo manually.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Refine with feedback (optional) — **vibe with the agent**
# MAGIC
# MAGIC Edit the `feedback` string below and re-run this cell to iterate on the generated
# MAGIC preset without re-introspecting the source. The `scope_note` is what tells the model
# MAGIC which layers to return — tweak it if you want to widen or narrow the refinement.

# COMMAND ----------

feedback = """
# Example refinements — replace with your own:
# - Add a lookup join for user_id → user_name
# - Map field `event.action` to activity_id per OCSF authentication class
"""

if feedback.strip() and not feedback.strip().startswith("#"):
    scope_note = {
        "gold":          "Return ONLY an updated `gold:` YAML block (no bronze/silver).",
        "bronze_silver": "Return ONLY updated `bronze:` and `silver:` YAML blocks (no gold).",
        "full":          "Return the full updated preset.yaml.",
    }[target_layers]
    preset_yaml = strip_fences(query_model(w, model_endpoint, [
        ChatMessage(role=ChatMessageRole.SYSTEM,    content=system_prompt),
        ChatMessage(role=ChatMessageRole.USER,      content=user_prompt),
        ChatMessage(role=ChatMessageRole.ASSISTANT, content=preset_yaml),
        ChatMessage(role=ChatMessageRole.USER,      content=f"Apply these refinements. {scope_note}\n\n{feedback}"),
    ]))
    final_yaml = assemble_final(
        preset_yaml=preset_yaml,
        existing_preset_text=existing_preset_text,
        target_layers=target_layers,
    )
    print("── REFINED PRESET ──────────────────────────────────────")
    print(final_yaml[:4000] + ("..." if len(final_yaml) > 4000 else ""))
    refined_parsed = validate_final_yaml(final_yaml, target_layers, existing_preset_text)
    if not (target_layers == "gold" and existing_preset_text is not None):
        file_header = build_preset_header(
            model_endpoint=model_endpoint,
            source_name=source_name,
            source_type=source_type,
            raw_sample_path=raw_sample_path,
            source_table=source_table,
            preset_parsed=refined_parsed,
            refined=True,
        )
        final_yaml = file_header + final_yaml
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
