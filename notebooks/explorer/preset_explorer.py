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
# MAGIC > **⚠️ Serverless environment version**
# MAGIC > This notebook imports `pyyaml`, which is bundled in serverless environment **v2+**.
# MAGIC > If you see `ModuleNotFoundError: No module named 'yaml'`, open the **Environment**
# MAGIC > side panel on the right and switch to the latest environment version.
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

# MAGIC %md
# MAGIC ## Widget reference
# MAGIC
# MAGIC ### Required
# MAGIC | Widget | Default | Purpose |
# MAGIC |---|---|---|
# MAGIC | `preset_file` | _(empty)_ | Full workspace path to the `preset.yaml` under test. |
# MAGIC
# MAGIC ### Input
# MAGIC | Widget | Default | Purpose |
# MAGIC |---|---|---|
# MAGIC | `sample_data_path` | _(empty)_ | File or folder of sample logs. Blank → uses `autoloader.inputs[0]` from the preset. |
# MAGIC | `input_row_limit` | `0` | Cap rows at the initial read so preTransform + lookups run against fewer records. `0` = no cap. |
# MAGIC
# MAGIC ### Layer & table gating
# MAGIC | Widget | Default | Purpose |
# MAGIC |---|---|---|
# MAGIC | `layers` | `all` | Which layers to execute. `all`, `bronze`, `bronze_silver`, `silver_gold`, `gold_only`. |
# MAGIC | `silver_table_filter` | _(empty)_ | Comma-separated silver table names to run. Blank = all. Useful when a preset defines multiple silver tables. |
# MAGIC | `gold_table_filter` | _(empty)_ | Comma-separated gold table names to run. Blank = all. |
# MAGIC
# MAGIC ### Display
# MAGIC | Widget | Default | Purpose |
# MAGIC |---|---|---|
# MAGIC | `display_limit` | `50` | Rows shown in `display()` per layer. |
# MAGIC | `register_temp_views` | `false` | Register `bronze_df` and each silver DataFrame as temp views (`bronze`, `<silver_name>`) for ad-hoc SQL in scratch cells. |
# MAGIC
# MAGIC ### Validation (optional)
# MAGIC | Widget | Default | Purpose |
# MAGIC |---|---|---|
# MAGIC | `ddl_path` | _(empty)_ | Workspace path to `notebooks/ddl/create_ocsf_tables.py`. When set, each gold table is validated against its DDL column list — extra columns (not in DDL) and missing required fields are flagged immediately. |
# MAGIC
# MAGIC **Notes.** `layers=gold_only` requires silver tables to exist in Unity Catalog — the explorer reads them via `spark.read.table(...)` from each gold's `input` reference.

# COMMAND ----------

dbutils.widgets.text(    "preset_file",          "",   "Preset File Path")
dbutils.widgets.text(    "sample_data_path",     "",   "Sample Data Path (blank → autoloader.inputs[0])")
dbutils.widgets.text(    "input_row_limit",      "0",  "Cap rows at initial read (0 = no cap)")
dbutils.widgets.dropdown("layers",               "all", ["all", "bronze", "bronze_silver", "silver_gold", "gold_only"], "Which layers to execute")
dbutils.widgets.text(    "silver_table_filter",  "",   "(Optional) comma-separated silver table names to run")
dbutils.widgets.text(    "gold_table_filter",    "",   "(Optional) comma-separated gold table names to run")
dbutils.widgets.text(    "display_limit",        "50", "Rows to display per layer")
dbutils.widgets.dropdown("register_temp_views",  "false", ["false", "true"], "Register bronze + silver DataFrames as temp views for ad-hoc SQL")
dbutils.widgets.text(    "ddl_path",             "",   "(Optional) path to create_ocsf_tables.py — enables gold schema validation")

# COMMAND ----------

# MAGIC %run ./explorer_helpers

# COMMAND ----------

preset_file         = dbutils.widgets.get("preset_file").strip()
sample_data_path    = dbutils.widgets.get("sample_data_path").strip()
input_row_limit     = int(dbutils.widgets.get("input_row_limit").strip() or "0")
layers              = dbutils.widgets.get("layers").strip()
silver_table_filter = [s.strip() for s in dbutils.widgets.get("silver_table_filter").split(",") if s.strip()]
gold_table_filter   = [s.strip() for s in dbutils.widgets.get("gold_table_filter").split(",") if s.strip()]
display_limit       = int(dbutils.widgets.get("display_limit").strip() or "50")
register_temp_views = dbutils.widgets.get("register_temp_views").strip().lower() == "true"
ddl_path            = dbutils.widgets.get("ddl_path").strip()

ocsf_schemas = load_ocsf_ddl_schemas(ddl_path) if ddl_path else None

config, fmt, sample_path = load_config(preset_file, sample_data_path)

run_bronze = layers in ("all", "bronze", "bronze_silver")
run_slv    = layers in ("all", "bronze_silver", "silver_gold")
run_gld    = layers in ("all", "silver_gold", "gold_only")
print(f"layers={layers} → bronze={run_bronze}  silver={run_slv}  gold={run_gld}")

# COMMAND ----------

# MAGIC %md ## Bronze

# COMMAND ----------

bronze_df = None
if run_bronze:
    bronze_df = read_bronze_batch(config, sample_path, fmt, display_limit, input_row_limit)
    if register_temp_views:
        bronze_df.createOrReplaceTempView("bronze")
        print("  registered temp view: `bronze`")
else:
    print("Skipped (layers setting).")

# COMMAND ----------

# MAGIC %md ## Silver

# COMMAND ----------

silver_dfs = {}
if run_slv:
    if bronze_df is None and layers != "silver_gold":
        raise RuntimeError("Silver needs a bronze_df. Set layers to include bronze, or use 'gold_only' to read silver from UC.")
    silver_dfs = run_silver(config, bronze_df, display_limit, silver_table_filter)
    if register_temp_views:
        for name, df in silver_dfs.items():
            df.createOrReplaceTempView(name)
        if silver_dfs:
            print(f"  registered temp view(s): {list(silver_dfs.keys())}")
else:
    print("Skipped (layers setting).")

# COMMAND ----------

# MAGIC %md ## Gold

# COMMAND ----------

if run_gld:
    run_gold(config, silver_dfs, display_limit, gold_table_filter, ocsf_schemas)
else:
    print("Skipped (layers setting).")
