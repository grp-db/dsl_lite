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
# MAGIC 3. Build a single system + user prompt: skill content as the system message, table
# MAGIC    metadata + task instructions as the user message.
# MAGIC 4. Call a Databricks-hosted foundation model via the serving endpoint.
# MAGIC 5. Review the generated `preset.yaml` and (optionally) save it into the repo tree.
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

dbutils.widgets.text("source_table",   "",                                    "Source UC Table (catalog.schema.table)")
dbutils.widgets.text("source_name",    "",                                    "Preset source (e.g. cisco)")
dbutils.widgets.text("source_type",    "",                                    "Preset source_type (e.g. ios)")
dbutils.widgets.text("ocsf_classes",   "",                                    "Target OCSF class(es), comma-separated (e.g. authentication,network_activity)")
dbutils.widgets.text("skill_path",     "/Workspace/Shared/dsl_lite/skills/dsl-lite-preset-dev", "Skill folder (SKILL.md + references/)")
dbutils.widgets.text("model_endpoint", "databricks-meta-llama-3-3-70b-instruct", "Serving endpoint name")
dbutils.widgets.text("sample_rows",    "5",                                   "Rows to sample from source table")
dbutils.widgets.text("output_path",    "",                                    "(Optional) full path to write preset.yaml")

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
# MAGIC ## 3. Build the prompt

# COMMAND ----------

source_name   = dbutils.widgets.get("source_name").strip()
source_type   = dbutils.widgets.get("source_type").strip()
ocsf_classes  = [c.strip() for c in dbutils.widgets.get("ocsf_classes").split(",") if c.strip()]

assert source_name and source_type, "source_name and source_type widgets are required"
assert ocsf_classes,                 "ocsf_classes widget is required (comma-separated)"

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

Source Unity Catalog table: `{source_table}`

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
# MAGIC ## 4. Call the Databricks Foundation Model API
# MAGIC
# MAGIC Uses the Databricks SDK to query a serving endpoint in the current workspace. The
# MAGIC endpoint is configurable via the `model_endpoint` widget — any chat-completions
# MAGIC compatible foundation model on the workspace will work.

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

model_endpoint = dbutils.widgets.get("model_endpoint").strip()
w              = WorkspaceClient()

query_kwargs = dict(
    name=model_endpoint,
    messages=[
        ChatMessage(role=ChatMessageRole.SYSTEM, content=system_prompt),
        ChatMessage(role=ChatMessageRole.USER,   content=user_prompt),
    ],
    max_tokens=8000,
)

# Claude extended-thinking endpoints (e.g. Opus 4.x) reject non-1.0 temperature;
# for other Claude variants temperature works but we default to 0 for determinism.
# Llama / other OSS endpoints accept the usual 0–1 range.
if "claude-opus" in model_endpoint or "thinking" in model_endpoint:
    pass  # omit temperature entirely
elif "claude" in model_endpoint:
    query_kwargs["temperature"] = 0.0
else:
    query_kwargs["temperature"] = 0.1

response = w.serving_endpoints.query(**query_kwargs)

preset_yaml = response.choices[0].message.content.strip()

# Strip accidental fences the model may add despite instructions
if preset_yaml.startswith("```"):
    preset_yaml = "\n".join(preset_yaml.splitlines()[1:])
    if preset_yaml.rstrip().endswith("```"):
        preset_yaml = preset_yaml.rstrip().rstrip("`").rstrip()

print(preset_yaml)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. (Optional) Save the generated preset
# MAGIC
# MAGIC Set the `output_path` widget to a workspace path (`/Workspace/...`) or a UC volume
# MAGIC path (`/Volumes/...`) to persist the file. Leave blank to skip.

# COMMAND ----------

output_path = dbutils.widgets.get("output_path").strip()

if output_path:
    if output_path.startswith("/Workspace/") or output_path.startswith("/Volumes/"):
        with open(output_path, "w") as f:
            f.write(preset_yaml)
        print(f"Wrote {len(preset_yaml):,} chars → {output_path}")
    else:
        raise ValueError("output_path must start with /Workspace/ or /Volumes/")
else:
    print("output_path is empty — not saving. Copy the YAML above into your repo manually.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Refine with feedback (optional)
# MAGIC
# MAGIC Edit the `feedback` string below and re-run this cell to iterate on the generated
# MAGIC preset without re-introspecting the table.

# COMMAND ----------

feedback = """
# Example refinements — replace with your own:
# - Move src_endpoint population to the silver layer
# - Add a lookup join for user_id → user_name on the silver layer
# - Map field `event.action` to activity_id per OCSF authentication class
"""

if feedback.strip() and not feedback.strip().startswith("#"):
    refine_messages = [
        ChatMessage(role=ChatMessageRole.SYSTEM, content=system_prompt),
        ChatMessage(role=ChatMessageRole.USER,   content=user_prompt),
        ChatMessage(role=ChatMessageRole.ASSISTANT, content=preset_yaml),
        ChatMessage(role=ChatMessageRole.USER,   content=f"Apply these refinements and return the full updated preset.yaml:\n\n{feedback}"),
    ]
    refined = w.serving_endpoints.query(
        name=model_endpoint,
        messages=refine_messages,
        max_tokens=8000,
        temperature=0.1,
    ).choices[0].message.content.strip()

    if refined.startswith("```"):
        refined = "\n".join(refined.splitlines()[1:])
        if refined.rstrip().endswith("```"):
            refined = refined.rstrip().rstrip("`").rstrip()

    preset_yaml = refined
    print(preset_yaml)
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
