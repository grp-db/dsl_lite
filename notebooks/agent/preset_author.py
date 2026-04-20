# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC # DSL Lite — Preset Author Agent
# MAGIC
# MAGIC Generate a `preset.yaml` for a Unity Catalog table using the **Databricks Foundation
# MAGIC Model API**. The notebook runs entirely inside your Databricks workspace — raw data,
# MAGIC schema, and sample rows never leave your environment.
# MAGIC
# MAGIC **How it works**
# MAGIC 1. Load the preset-authoring skill (`SKILL.md` + `references/`) from a workspace path or
# MAGIC    Unity Catalog volume.
# MAGIC 2. Introspect the source table (`DESCRIBE TABLE EXTENDED` + a small `SELECT` sample).
# MAGIC 3. If the input is an already-built silver table and you point at an existing
# MAGIC    `preset.yaml`, load its `bronze:` + `silver:` sections as read-only context.
# MAGIC 4. Build a single system + user prompt. In `silver` mode, ask the model for ONLY the
# MAGIC    `gold:` section. In `raw` mode, ask for a full bronze/silver/gold preset.
# MAGIC 5. Call a Databricks-hosted foundation model via the serving endpoint.
# MAGIC 6. In silver mode, splice the generated `gold:` into the existing preset using
# MAGIC    `ruamel.yaml` — your bronze/silver bytes, key order, and comments stay intact.
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
# MAGIC - `SELECT` permission on the source table.

# COMMAND ----------

dbutils.widgets.text(    "source_table",          "",                                    "Source UC Table (catalog.schema.table)")
dbutils.widgets.text(    "source_name",           "",                                    "Preset source (e.g. cisco)")
dbutils.widgets.text(    "source_type",           "",                                    "Preset source_type (e.g. ios)")
dbutils.widgets.text(    "ocsf_classes",          "",                                    "Target OCSF class(es), comma-separated (e.g. authentication,network_activity)")
dbutils.widgets.dropdown("input_layer",           "silver", ["silver", "raw"],           "Input layer (silver → gold-only; raw → full preset)")
dbutils.widgets.text(    "existing_preset_path",  "",                                    "(Optional) existing preset.yaml — silver mode splices new gold in")
dbutils.widgets.text(    "skill_path",            "/Workspace/Shared/dsl_lite/skills/dsl-lite-preset-dev", "Skill folder (SKILL.md + references/)")
dbutils.widgets.text(    "model_endpoint",        "databricks-meta-llama-3-3-70b-instruct", "Serving endpoint name")
dbutils.widgets.text(    "sample_rows",           "5",                                   "Rows to sample from source table")
dbutils.widgets.text(    "output_path",           "",                                    "(Optional) full path to write preset.yaml")

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
# MAGIC ## 2. Introspect the source table
# MAGIC
# MAGIC Pulls schema and a small sample. Data stays in the workspace — only the schema and
# MAGIC sample rows are sent to the serving endpoint (which is itself Databricks-hosted).

# COMMAND ----------

import json

source_table  = dbutils.widgets.get("source_table").strip()
n_sample      = int(dbutils.widgets.get("sample_rows") or "5")

assert source_table, "source_table widget is required"

schema_rows   = spark.sql(f"DESCRIBE TABLE EXTENDED {source_table}").collect()
schema_text   = "\n".join(f"{r['col_name']:40s} {r['data_type'] or '':30s} {r['comment'] or ''}" for r in schema_rows if r['col_name'])

sample_rows   = spark.sql(f"SELECT to_json(struct(*)) AS _row FROM {source_table} LIMIT {n_sample}").collect()
sample_json   = "[\n" + ",\n".join("  " + r["_row"] for r in sample_rows) + "\n]"

# Hard cap on sample payload sent to the model. Wide/variant-heavy rows can balloon
# well past the serving endpoint's context window; 40 KB ≈ ~10K tokens is plenty for
# the model to infer field patterns without eating the whole prompt budget.
_SAMPLE_JSON_MAX = 40_000
if len(sample_json) > _SAMPLE_JSON_MAX:
    sample_json = sample_json[:_SAMPLE_JSON_MAX] + "\n... [truncated]"

print("── SCHEMA ──────────────────────────────────────────────")
print(schema_text[:2000] + ("..." if len(schema_text) > 2000 else ""))
print("\n── SAMPLE ROWS ─────────────────────────────────────────")
print(sample_json[:2000] + ("..." if len(sample_json) > 2000 else ""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Load existing preset (optional, silver mode only)
# MAGIC
# MAGIC When `input_layer=silver` and `existing_preset_path` is set, we keep the existing
# MAGIC `bronze:` + `silver:` sections verbatim and only ask the model to (re)generate the
# MAGIC `gold:` section. The existing bronze/silver YAML is passed to the model as context so
# MAGIC it can reference real silver column names when authoring the OCSF mappings.
# MAGIC
# MAGIC Uses `ruamel.yaml` to preserve key order and comments in the untouched sections.

# COMMAND ----------

from ruamel.yaml import YAML
from io import StringIO

input_layer          = dbutils.widgets.get("input_layer").strip()
existing_preset_path = dbutils.widgets.get("existing_preset_path").strip()

_yaml = YAML()
_yaml.preserve_quotes = True
_yaml.indent(mapping=2, sequence=4, offset=2)
_yaml.width = 200

existing_preset_doc    = None          # parsed YAML doc, used for splicing on save
existing_bronze_silver = None          # YAML string passed into the prompt

if existing_preset_path:
    with open(existing_preset_path, "r") as f:
        existing_preset_doc = _yaml.load(f)
    subset = {k: existing_preset_doc[k] for k in ("bronze", "silver") if k in existing_preset_doc}
    if subset:
        buf = StringIO()
        _yaml.dump(subset, buf)
        existing_bronze_silver = buf.getvalue()
    print(f"Loaded existing preset from {existing_preset_path} "
          f"(sections: {list(existing_preset_doc.keys()) if existing_preset_doc else []})")
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
assert ocsf_classes,                 "ocsf_classes widget is required (comma-separated)"

if input_layer == "silver":
    system_prompt = (
        "You are a DSL Lite preset author. You produce ONLY a valid YAML document — "
        "no prose, no code fences, no commentary outside the YAML. The input UC table is "
        "ALREADY the silver layer (parsed, typed, normalized). You MUST emit ONLY a top-level "
        "`gold:` key mapping silver columns to the requested OCSF classes. DO NOT emit "
        "`bronze:` or `silver:` keys — those layers already exist and must not be altered. "
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

Target OCSF gold classes: {", ".join(ocsf_classes)}

The input table below is the SILVER layer (already parsed). Map its columns to the
requested OCSF gold classes per the skill's gold-table rules.

Source Unity Catalog table (silver): `{source_table}`

Silver table schema (col_name / data_type / comment):
```
{schema_text}
```

Sample silver rows (JSON):
```json
{sample_json}
```
{existing_bs_block}
Requirements:
- Output a YAML document whose ONLY top-level key is `gold:`.
- Do NOT include `bronze:` or `silver:` keys under any circumstance.
- Include metadata + endpoint structs per the OCSF templates.
- Map fields to the listed OCSF classes using the skill's gold-table rules.
- Output ONLY the YAML. Do not wrap it in triple backticks.
"""
else:
    system_prompt = (
        "You are a DSL Lite preset author. You produce ONLY a valid preset.yaml file — "
        "no prose, no code fences, no commentary outside the YAML. "
        "Follow every convention in the skill reference below exactly.\n\n"
        + skill_context
    )
    user_prompt = f"""Author a complete `preset.yaml` for this data source.

Source identifiers:
- source:      {source_name}
- source_type: {source_type}
- target path: pipelines/{source_name}/{source_type}/preset.yaml

Target OCSF gold classes: {", ".join(ocsf_classes)}

Source Unity Catalog table (raw): `{source_table}`

Table schema (col_name / data_type / comment):
```
{schema_text}
```

Sample rows (JSON):
```json
{sample_json}
```

Requirements:
- Produce bronze, silver, and gold sections consistent with the skill references.
- Use `try_variant_get` for JSON payloads when appropriate.
- Include metadata + endpoint structs per the OCSF templates.
- Map fields to the listed OCSF classes using the skill's gold-table rules.
- Output ONLY the YAML document. Do not wrap it in triple backticks.
"""

_total_chars = len(system_prompt) + len(user_prompt)
print(f"system prompt: {len(system_prompt):,} chars")
print(f"user prompt:   {len(user_prompt):,} chars")
print(f"total:         {_total_chars:,} chars  (~{_total_chars // 4:,} tokens, Llama 3.3 70B limit is 128K)")

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
# MAGIC In silver mode with an existing preset, the model only returned a `gold:` block.
# MAGIC Here we parse it and splice it into the existing preset, preserving the original
# MAGIC bronze/silver bytes, key order, and comments via `ruamel.yaml`.

# COMMAND ----------

def _splice_gold(base_doc, generated_yaml_text):
    """Replace base_doc['gold'] with the gold: block from the model response."""
    generated = _yaml.load(generated_yaml_text)
    if not isinstance(generated, dict) or "gold" not in generated:
        raise ValueError(
            "Model response in silver mode must be a YAML doc with a top-level `gold:` key. "
            f"Got top-level keys: {list(generated.keys()) if isinstance(generated, dict) else type(generated).__name__}"
        )
    base_doc["gold"] = generated["gold"]
    buf = StringIO()
    _yaml.dump(base_doc, buf)
    return buf.getvalue()

if input_layer == "silver" and existing_preset_doc is not None:
    final_yaml = _splice_gold(existing_preset_doc, preset_yaml)
    print("── SPLICED PRESET (existing bronze/silver + new gold) ──")
else:
    final_yaml = preset_yaml
    print("── FINAL PRESET ────────────────────────────────────────")

print(final_yaml[:4000] + ("..." if len(final_yaml) > 4000 else ""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. (Optional) Save the final preset
# MAGIC
# MAGIC Set the `output_path` widget to a workspace path (`/Workspace/...`) or a UC volume
# MAGIC path (`/Volumes/...`) to persist the file. Leave blank to skip.

# COMMAND ----------

output_path = dbutils.widgets.get("output_path").strip()

if output_path:
    if output_path.startswith("/Workspace/") or output_path.startswith("/Volumes/"):
        with open(output_path, "w") as f:
            f.write(final_yaml)
        print(f"Wrote {len(final_yaml):,} chars → {output_path}")
    else:
        raise ValueError("output_path must start with /Workspace/ or /Volumes/")
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
    if input_layer == "silver" and existing_preset_doc is not None:
        final_yaml = _splice_gold(existing_preset_doc, preset_yaml)
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
