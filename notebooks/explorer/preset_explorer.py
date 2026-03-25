# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC # DSL Lite — Interactive Preset Explorer
# MAGIC
# MAGIC Use this notebook to interactively develop and validate preset YAML configurations
# MAGIC **without** running a full SDP or SSS pipeline. Each layer (Bronze → Silver → Gold)
# MAGIC is executed as a Spark batch operation so you can iterate on your YAML side-by-side
# MAGIC with the output.
# MAGIC
# MAGIC **How to use:**
# MAGIC 1. Set `preset_file` to the full workspace path of your `preset.yaml`
# MAGIC 2. Set `sample_data_path` to a sample file or folder (leave blank to use `autoloader.inputs[0]`)
# MAGIC 3. Click **Run All** — each layer displays its output below the cell
# MAGIC 4. Tweak your YAML and re-run the affected cell to iterate
# MAGIC
# MAGIC See `tutorials/building-a-preset-end-to-end.md` for a full walkthrough.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Note on `data` column type (JSON presets)
# MAGIC
# MAGIC In production (SDP / SSS), Auto Loader reads JSON records into a single `data VARIANT`
# MAGIC column using `loadAsSingleVariant`. The explorer runs on **serverless compute via Spark
# MAGIC Connect**, which does not support the VARIANT type in its Python client protocol — any
# MAGIC DataFrame holding a VARIANT column will fail schema serialisation before `display()` runs.
# MAGIC
# MAGIC To work around this, the explorer keeps `data` as a plain **STRING** (the raw JSON) and
# MAGIC transparently rewrites VARIANT-dependent expressions at runtime:
# MAGIC
# MAGIC | Production YAML expression | Explorer equivalent |
# MAGIC |----------------------------|---------------------|
# MAGIC | `try_variant_get(data, '$.field', 'STRING')` | `get_json_object(data, '$.field')` |
# MAGIC | `CAST(... AS VARIANT)` | `CAST(... AS STRING)` |
# MAGIC | `to_json(data)` | `data` (already a JSON string) |
# MAGIC
# MAGIC **The values are identical** — only the column type annotation differs. Your YAML is
# MAGIC validated correctly and deployed to SDP / SSS unchanged.
# MAGIC
# MAGIC > **Array-type fields** (`'ARRAY<STRING>'`, `'ARRAY<INT>'`, etc.) will appear as raw
# MAGIC > JSON strings (e.g. `["a","b"]`) rather than typed arrays. This is a display-only
# MAGIC > difference and does not affect the correctness of field mapping validation.

# COMMAND ----------

# MAGIC %pip install pyyaml

# COMMAND ----------

dbutils.widgets.text("preset_file",     "",   "Preset File Path")
dbutils.widgets.text("sample_data_path", "",  "Sample Data Path (leave blank → autoloader.inputs[0])")
dbutils.widgets.text("display_limit",   "50", "Rows to Display per Layer")

# COMMAND ----------

# MAGIC %run ./explorer_helpers

# COMMAND ----------

config, fmt, sample_path = load_config(
    dbutils.widgets.get("preset_file").strip(),
    dbutils.widgets.get("sample_data_path").strip()
)
display_limit = int(dbutils.widgets.get("display_limit").strip() or "50")

# COMMAND ----------

# MAGIC %md ## Bronze

# COMMAND ----------

bronze_df = read_bronze_batch(config, sample_path, fmt, display_limit)

# COMMAND ----------

# MAGIC %md ## Silver

# COMMAND ----------

silver_dfs = run_silver(config, bronze_df, display_limit)

# COMMAND ----------

# MAGIC %md ## Gold

# COMMAND ----------

run_gold(config, silver_dfs, display_limit)
