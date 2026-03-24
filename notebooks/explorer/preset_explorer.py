# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC # DSL Lite — Interactive Preset Explorer
# MAGIC
# MAGIC Use this notebook to interactively develop and validate preset YAML configurations
# MAGIC **without** running a full SDP or SSS pipeline. Each layer (Bronze → Silver → Gold)
# MAGIC is executed as a Spark batch operation, and results are displayed inline so you can
# MAGIC iterate on your YAML side-by-side with the output.
# MAGIC
# MAGIC **How to use:**
# MAGIC 1. Set `preset_file` to the full workspace path of your `preset.yaml`
# MAGIC 2. Set `sample_data_path` to a local sample file or folder (leave blank to use the first path in `autoloader.inputs`)
# MAGIC 3. Run **All** — each layer displays its output below the cell
# MAGIC 4. Tweak your YAML and re-run to iterate
# MAGIC
# MAGIC **Supported formats:** `text` / `syslog`, `json`, `jsonl`, `csv`, `parquet`
# MAGIC
# MAGIC > **Note:** This notebook runs batch reads, not streaming. Auto Loader options
# MAGIC > (e.g. `cloudFiles.inferColumnTypes`) are ignored. Schema inference is used by default.

# COMMAND ----------

dbutils.widgets.text("preset_file", "", "Preset File Path")
dbutils.widgets.text("sample_data_path", "", "Sample Data Path (leave blank → uses autoloader.inputs[0])")
dbutils.widgets.text("display_limit", "50", "Rows to Display per Layer")

# COMMAND ----------

# MAGIC %run ./explorer_helpers

# COMMAND ----------

# =============================================================================
# Load preset YAML and resolve sample data path
# =============================================================================

from yaml import load, Loader

preset_file     = dbutils.widgets.get("preset_file").strip()
sample_override = dbutils.widgets.get("sample_data_path").strip()
display_limit   = int(dbutils.widgets.get("display_limit").strip() or "50")

if not preset_file:
    raise ValueError("Set the 'preset_file' widget to the full path of your preset.yaml")

with open(preset_file, "r") as f:
    config = load(f, Loader=Loader)

# Resolve sample data path
if sample_override:
    sample_path = sample_override
else:
    inputs = config.get("autoloader", {}).get("inputs", [])
    if not inputs:
        raise ValueError("No 'autoloader.inputs' found in preset and no sample_data_path provided")
    sample_path = inputs[0]

fmt = config.get("autoloader", {}).get("format", "text").lower()

# Print summary
print(f"Preset  : {config.get('name', '(unnamed)')}")
print(f"Format  : {fmt}")
print(f"Sample  : {sample_path}")
print(f"Limit   : {display_limit} rows per layer\n")

silver_names = [t["name"] for t in config.get("silver", {}).get("transform", [])]
gold_names   = [t["name"] for t in config.get("gold", [])]
print(f"Silver tables : {silver_names}")
print(f"Gold tables   : {gold_names}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bronze Layer
# MAGIC Reads sample data, applies `preTransform`, adds `dsl_id`, runs lookups and `postTransform`.

# COMMAND ----------

# =============================================================================
# Bronze — batch read + preTransform + dsl_id + lookups + postTransform
# =============================================================================

_FMT_MAP = {
    "text": "text", "syslog": "text",
    "json": "json", "jsonl": "json",
    "csv": "csv", "parquet": "parquet",
}
spark_fmt = _FMT_MAP.get(fmt, fmt)

# Build read options
_al_conf = config.get("autoloader", {})
read_opts = {}
if fmt in ("json", "jsonl"):
    read_opts["multiLine"] = str(_al_conf.get("multiline", "false"))
elif fmt == "csv":
    read_opts["header"] = "true"
    read_opts["inferSchema"] = "true"
for k, v in (_al_conf.get("options") or {}).items():
    read_opts[k] = v

# Schema (optional)
_cf = _al_conf.get("cloudFiles") or {}
schema_str = _al_conf.get("schema") or _cf.get("schema")

reader = spark.read.format(spark_fmt).options(**read_opts)
if schema_str:
    reader = reader.schema(schema_str)

bronze_df = reader.load(sample_path)

# preTransform — each element is a list of SQL expressions (one selectExpr pass per element)
bronze_conf = config.get("bronze", {})
for pt in bronze_conf.get("preTransform", []):
    if isinstance(pt, list):
        bronze_df = bronze_df.selectExpr(*pt)
    elif isinstance(pt, str):
        bronze_df = bronze_df.selectExpr(pt)

# dsl_id (same expression as production)
bronze_df = bronze_df.selectExpr(
    "*",
    "lower(concat(hex(unix_millis(current_timestamp())), substring(replace(uuid(), '-', ''), 1, 13))) as dsl_id"
)

# Lookups
if bronze_conf.get("lookups"):
    bronze_df = apply_lookups(bronze_df, bronze_conf["lookups"])

# postTransform
if bronze_conf.get("postTransform"):
    bronze_df = bronze_df.selectExpr(*bronze_conf["postTransform"])

# Drop
drop_cols = [strip_backticks(c) for c in bronze_conf.get("drop", [])]
existing_drops = [c for c in drop_cols if c in bronze_df.columns]
if existing_drops:
    bronze_df = bronze_df.drop(*existing_drops)

print(f"Bronze schema ({len(bronze_df.columns)} columns): {bronze_df.columns}")
display(bronze_df.limit(display_limit))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver Layer
# MAGIC Applies filter, temporary fields, field expressions, and post-filter for each silver transform.

# COMMAND ----------

# =============================================================================
# Silver — one display per silver transform
# =============================================================================

silver_dfs = {}  # {table_name: DataFrame} — used by gold layer below

for tr_conf in config.get("silver", {}).get("transform", []):
    silver_name = tr_conf["name"]
    print(f"\n{'='*60}")
    print(f"Silver table: {silver_name}")
    print(f"{'='*60}")

    # Determine source: use fully qualified input if specified, else bronze_df
    input_ref = tr_conf.get("input")
    if input_ref and "." in str(input_ref):
        print(f"  Reading from existing table: {input_ref}")
        df = spark.read.table(input_ref)
    else:
        df = bronze_df

    # Lookups
    if tr_conf.get("lookups"):
        df = apply_lookups(df, tr_conf["lookups"])

    # Filter
    if "filter" in tr_conf:
        print(f"  Filter: {tr_conf['filter']}")
        df = df.filter(tr_conf["filter"])

    # Temporary fields
    temp_fields_conf = (tr_conf.get("utils") or {}).get("temporaryFields", [])
    if temp_fields_conf:
        df = df.selectExpr("*", *generate_field_exprs(temp_fields_conf))

    # Unreferenced columns (preserve original columns if configured)
    unreferenced_conf = (tr_conf.get("utils") or {}).get("unreferencedColumns", {})
    orig_cols = []
    if unreferenced_conf.get("preserve", False):
        to_omit = [strip_backticks(c) for c in unreferenced_conf.get("omitColumns", [])]
        orig_cols = [f"`{c}`" for c in df.columns if c not in to_omit]
    if "dsl_id" not in orig_cols and "`dsl_id`" not in orig_cols:
        orig_cols.append("dsl_id")

    new_fields = generate_field_exprs(tr_conf.get("fields", []))
    df = df.selectExpr(*orig_cols, *new_fields)

    # Drop temporary fields
    if temp_fields_conf:
        df = df.drop(*[t["name"] for t in temp_fields_conf])

    # Post-filter
    if "postFilter" in tr_conf:
        df = df.filter(tr_conf["postFilter"])

    silver_dfs[silver_name] = df
    print(f"  Schema ({len(df.columns)} columns): {df.columns}")
    display(df.limit(display_limit))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold Layer
# MAGIC Maps each silver table to OCSF-compliant fields. Applies filter, optional explode, and field expressions.

# COMMAND ----------

# =============================================================================
# Gold — one display per gold table
# =============================================================================

for tr_conf in config.get("gold", []):
    gold_name = tr_conf["name"]
    print(f"\n{'='*60}")
    print(f"Gold table: {gold_name}")
    print(f"{'='*60}")

    # Resolve silver source
    input_ref = tr_conf.get("input")
    if input_ref and "." in str(input_ref):
        print(f"  Reading from existing table: {input_ref}")
        df = spark.read.table(input_ref)
    elif input_ref and input_ref in silver_dfs:
        df = silver_dfs[input_ref]
    elif silver_dfs:
        df = next(iter(silver_dfs.values()))
    else:
        print(f"  ⚠️  No silver DataFrame found for input '{input_ref}' — skipping")
        continue

    # Filter
    if "filter" in tr_conf:
        print(f"  Filter: {tr_conf['filter']}")
        df = df.filter(tr_conf["filter"])

    # Explode (for array/variant columns)
    explode_col = tr_conf.get("explode")
    if explode_col:
        field = next((f for f in df.schema.fields if f.name == explode_col), None)
        is_variant = field is not None and "variant" in str(field.dataType).lower()
        if is_variant:
            tvf = getattr(getattr(spark, "tvf", None), "variant_explode_outer", None)
            lateral_join = getattr(df, "lateralJoin", None)
            if tvf is not None and lateral_join is not None:
                try:
                    exploded_tbl = tvf(spark_col(explode_col))
                    df = df.lateralJoin(exploded_tbl, how="left_outer")
                    df = df.withColumnRenamed("value", "_exploded").drop("pos", "key")
                except Exception:
                    df = _explode_variant_fallback(df, explode_col)
            else:
                df = _explode_variant_fallback(df, explode_col)
        else:
            df = df.withColumn("_exploded", explode_outer(spark_col(explode_col)))

    # Field expressions
    new_fields = generate_field_exprs(tr_conf.get("fields", []))
    select_exprs = []
    if "dsl_id" in df.columns:
        select_exprs.append("dsl_id")
    select_exprs.extend(new_fields)
    df = df.selectExpr(*select_exprs)

    # Post-filter
    if "postFilter" in tr_conf:
        df = df.filter(tr_conf["postFilter"])

    print(f"  Schema ({len(df.columns)} columns): {df.columns}")
    display(df.limit(display_limit))
