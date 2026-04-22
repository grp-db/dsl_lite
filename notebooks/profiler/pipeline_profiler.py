# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC # DSL Lite — Pipeline Profiler
# MAGIC
# MAGIC Use this notebook to validate and compare pipelines before deployment.
# MAGIC It covers four checks that can be run independently or all at once:
# MAGIC
# MAGIC | Check | What it does | Inputs needed |
# MAGIC |---|---|---|
# MAGIC | **Schema Diff** | Column-by-column comparison of source vs target table | `source_table` + `target_table` |
# MAGIC | **Data Profile** | Side-by-side null rates for source vs target | `source_table` + `target_table` |
# MAGIC | **E2E Sample Run** | Runs N rows through bronze → silver → gold via the preset | `preset_file` + `sample_data_path` |
# MAGIC | **OCSF Coverage** | Flags empty/high-null fields in a gold table | `target_table` (or output of E2E run) |
# MAGIC
# MAGIC **Typical migration workflow:**
# MAGIC 1. Set `source_table` to the legacy table being replaced
# MAGIC 2. Set `target_table` to the new dsl_lite gold table
# MAGIC 3. Set `checks` to `all` and click **Run All**
# MAGIC 4. Review the diff — confirm no required columns are missing or regressed
# MAGIC
# MAGIC > **⚠️ Serverless environment version**
# MAGIC > Requires PyYAML (serverless environment v2+). If you see
# MAGIC > `ModuleNotFoundError: No module named 'yaml'`, switch the environment version
# MAGIC > in the **Environment** side panel.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Widget reference
# MAGIC
# MAGIC ### Tables (Schema Diff, Data Profile, OCSF Coverage)
# MAGIC | Widget | Default | Purpose |
# MAGIC |---|---|---|
# MAGIC | `source_table` | _(empty)_ | Legacy / existing table to compare against (e.g. `catalog.schema.old_dns_logs`). |
# MAGIC | `target_table` | _(empty)_ | New dsl_lite gold table (e.g. `catalog.schema.dns_activity`). |
# MAGIC
# MAGIC ### Preset (E2E Sample Run)
# MAGIC | Widget | Default | Purpose |
# MAGIC |---|---|---|
# MAGIC | `preset_file` | _(empty)_ | Full workspace path to the `preset.yaml` under test. |
# MAGIC | `sample_data_path` | _(empty)_ | Sample log file or folder. Blank → uses `autoloader.inputs[0]` from the preset. |
# MAGIC
# MAGIC ### Options
# MAGIC | Widget | Default | Purpose |
# MAGIC |---|---|---|
# MAGIC | `checks` | `all` | Which checks to run: `all`, `schema_diff`, `data_profile`, `e2e_sample`, `ocsf_coverage`. |
# MAGIC | `sample_size` | `100` | Rows sampled for data profile and E2E run. |
# MAGIC | `null_threshold` | `80` | Null % at or above which a column is flagged as a warning. |
# MAGIC | `flatten_schema` | `false` | Recursively compare nested struct fields in schema diff. |

# COMMAND ----------

dbutils.widgets.text(    "source_table",      "",    "Source / Legacy Table")
dbutils.widgets.text(    "target_table",      "",    "Target / DSL Lite Table")
dbutils.widgets.text(    "preset_file",       "",    "Preset File Path")
dbutils.widgets.text(    "sample_data_path",  "",    "Sample Data Path (blank → autoloader.inputs[0])")
dbutils.widgets.dropdown("checks", "all",
    ["all", "schema_diff", "data_profile", "e2e_sample", "ocsf_coverage"],
    "Checks to run")
dbutils.widgets.text(    "sample_size",       "100", "Sample size (rows)")
dbutils.widgets.text(    "null_threshold",    "80",  "Null % warning threshold")
dbutils.widgets.dropdown("flatten_schema",    "false", ["false", "true"], "Flatten struct fields in schema diff")

# COMMAND ----------

# MAGIC %run ../explorer/explorer_helpers

# COMMAND ----------

# MAGIC %run ./profiler_helpers

# COMMAND ----------

source_table     = dbutils.widgets.get("source_table").strip()
target_table     = dbutils.widgets.get("target_table").strip()
preset_file      = dbutils.widgets.get("preset_file").strip()
sample_data_path = dbutils.widgets.get("sample_data_path").strip()
checks           = dbutils.widgets.get("checks").strip()
sample_size      = int(dbutils.widgets.get("sample_size").strip() or "100")
null_threshold   = float(dbutils.widgets.get("null_threshold").strip() or "80")
flatten_schema   = dbutils.widgets.get("flatten_schema").strip().lower() == "true"

run_schema_diff  = checks in ("all", "schema_diff")
run_data_profile = checks in ("all", "data_profile")
run_e2e          = checks in ("all", "e2e_sample")
run_ocsf         = checks in ("all", "ocsf_coverage")

print(f"checks={checks}")
print(f"  schema_diff={run_schema_diff}  data_profile={run_data_profile}  e2e_sample={run_e2e}  ocsf_coverage={run_ocsf}")
print(f"  source_table={source_table or '(not set)'}  target_table={target_table or '(not set)'}")
print(f"  preset_file={preset_file or '(not set)'}  sample_size={sample_size}  null_threshold={null_threshold}%")

# COMMAND ----------

# MAGIC %md ## Schema Diff

# COMMAND ----------

if run_schema_diff:
    if source_table and target_table:
        compare_schemas(source_table, target_table, flatten=flatten_schema)
    else:
        print("Skipped — set both source_table and target_table to run schema diff.")

# COMMAND ----------

# MAGIC %md ## Data Profile

# COMMAND ----------

if run_data_profile:
    if source_table and target_table:
        compare_profiles(source_table, target_table,
                         sample_size=sample_size, null_threshold=null_threshold)
    else:
        print("Skipped — set both source_table and target_table to run data profile.")

# COMMAND ----------

# MAGIC %md ## E2E Sample Run

# COMMAND ----------

bronze_df   = None
silver_dfs  = {}

if run_e2e:
    if preset_file:
        config, fmt, sample_path = load_config(preset_file, sample_data_path)
        bronze_df, silver_dfs = run_e2e_sample(config, sample_path, fmt, n_rows=sample_size)
    else:
        print("Skipped — set preset_file to run E2E sample.")

# COMMAND ----------

# MAGIC %md ## OCSF Coverage

# COMMAND ----------

if run_ocsf:
    if target_table:
        check_ocsf_coverage(
            spark.table(target_table).limit(sample_size),
            target_table,
            null_threshold=null_threshold
        )
    else:
        print("Skipped — set target_table to run OCSF coverage check.")
