# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC # DSL Lite Explorer — Helper Functions
# MAGIC
# MAGIC Loaded via `%run ./explorer_helpers` from `preset_explorer`.
# MAGIC Provides batch equivalents of the core DSL Lite transformation functions
# MAGIC and the bronze / silver / gold execution functions used by the explorer.

# COMMAND ----------

from yaml import load, Loader
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import (
    broadcast, col as spark_col, explode_outer, from_json, to_json,
    expr as spark_expr
)

spark = SparkSession.getActiveSession()


# =============================================================================
# Field expression helpers (mirrors src/dsl.py)
# =============================================================================

def populate_nested(d: dict, parts: list, expr: str):
    if len(parts) == 1:
        d[parts[0]] = expr
    else:
        nested = d.get(parts[0], {})
        populate_nested(nested, parts[1:], expr)
        d[parts[0]] = nested


def generate_struct(k: str, v) -> str:
    if isinstance(v, str):
        return f"{v} as `{k}`"
    elif isinstance(v, dict):
        fields = [generate_struct(k2, v2) for k2, v2 in v.items()]
        return f"struct({', '.join(fields)}) as `{k}`"
    else:
        raise Exception(f"Wrong type for field value: {v}")


def generate_field_exprs(fields: list) -> list:
    """Convert a list of DSL Lite field configs to Spark SQL selectExpr strings."""
    new_cols = []
    nested = {}
    for f in fields:
        full_name = f["name"]
        if "expr" in f:
            expr_str = f["expr"]
        elif "literal" in f:
            literal = f["literal"]
            expr_str = f"'{literal}'" if isinstance(literal, str) else str(literal)
        elif "from" in f:
            expr_str = f["from"]
        else:
            raise Exception(f"Invalid field config (must have expr, literal, or from): {f}")

        if "." in full_name:
            populate_nested(nested, full_name.split("."), expr_str)
        else:
            new_cols.append(f"{expr_str} as `{full_name}`")

    for k, v in nested.items():
        new_cols.append(generate_struct(k, v))

    return new_cols


def strip_backticks(c: str) -> str:
    if c and c[0] == "`" and c[-1] == "`":
        return c[1:-1]
    return c


# =============================================================================
# Lookup helpers (mirrors src/dsl.py)
# =============================================================================

def read_lookup(source_conf: dict) -> DataFrame:
    """Read a lookup table or file as a batch DataFrame."""
    source_type = source_conf.get("type", "table")
    path = source_conf.get("path")
    if not path:
        raise Exception("Lookup source must specify 'path'")
    if source_type == "table":
        return spark.read.table(path)
    elif source_type in ("csv", "parquet", "json", "jsonl"):
        fmt = source_conf.get("format", source_type)
        opts = source_conf.get("options", {})
        reader = spark.read.format(fmt)
        if opts:
            reader = reader.options(**opts)
        return reader.load(path)
    else:
        raise Exception(f"Unsupported lookup source type: {source_type}")


def apply_lookups(df: DataFrame, lookups: list) -> DataFrame:
    """Apply one or more lookup joins to a DataFrame."""
    for lookup_conf in lookups:
        lookup_df = read_lookup(lookup_conf["source"])

        join_conf = lookup_conf.get("join", {})
        join_type = join_conf.get("type", "left")
        join_conditions = join_conf.get("on") or join_conf.get(True) or []

        join_exprs = []
        for condition in join_conditions:
            if "=" in condition:
                parts = [p.strip() for p in condition.split("=", 1)]
                main_col = strip_backticks(parts[0].replace("main.", "").strip())
                lkp_col  = strip_backticks(parts[1].replace("lookup.", "").strip())
                join_exprs.append(
                    spark_col(f"main.{main_col}") == spark_col(f"lookup.{lkp_col}")
                )
            else:
                col_name = strip_backticks(condition.strip())
                join_exprs.append(
                    spark_col(f"main.{col_name}") == spark_col(f"lookup.{col_name}")
                )

        join_expr = join_exprs[0]
        for e in join_exprs[1:]:
            join_expr = join_expr & e

        select_cols = lookup_conf.get("select", [])
        prefix = lookup_conf.get("prefix", "")
        lookup_cols = select_cols if select_cols else lookup_df.columns

        if lookup_conf.get("broadcast", False):
            lookup_df = broadcast(lookup_df)

        joined = df.alias("main").join(lookup_df.alias("lookup"), join_expr, join_type)
        main_cols = [spark_col(f"main.{c}").alias(c) for c in df.columns]
        lkp_cols = (
            [spark_col(f"lookup.{c}").alias(f"{prefix}{c}") for c in lookup_cols]
            if prefix
            else [spark_col(f"lookup.{c}") for c in lookup_cols]
        )
        df = joined.select(*main_cols, *lkp_cols)
    return df


# =============================================================================
# Variant explode fallback (mirrors src/dsl.py)
# =============================================================================

def _explode_variant_fallback(df: DataFrame, explode_col: str) -> DataFrame:
    df = df.withColumn("_arr", from_json(to_json(spark_col(explode_col)), "array<string>"))
    df = df.withColumn("_exploded", explode_outer(spark_col("_arr")))
    df = df.withColumn("_exploded", spark_expr("parse_json(_exploded)")).drop("_arr")
    return df


# =============================================================================
# Config loader
# =============================================================================

def load_config(preset_file: str, sample_override: str = "") -> tuple:
    """
    Load a preset YAML and resolve the sample data path.

    Returns:
        (config dict, format string, resolved sample path)
    """
    if not preset_file:
        raise ValueError("Set the 'preset_file' widget to the full path of your preset.yaml")

    with open(preset_file, "r") as f:
        config = load(f, Loader=Loader)

    if sample_override:
        sample_path = sample_override
    else:
        inputs = config.get("autoloader", {}).get("inputs", [])
        if not inputs:
            raise ValueError("No 'autoloader.inputs' found in preset and no sample_data_path provided")
        sample_path = inputs[0]

    fmt = config.get("autoloader", {}).get("format", "text").lower()

    print(f"Preset  : {config.get('name', '(unnamed)')}")
    print(f"Format  : {fmt}")
    print(f"Sample  : {sample_path}\n")
    print(f"Silver tables : {[t['name'] for t in config.get('silver', {}).get('transform', [])]}")
    print(f"Gold tables   : {[t['name'] for t in config.get('gold', [])]}")

    return config, fmt, sample_path


# =============================================================================
# Bronze
# =============================================================================

_FMT_MAP = {
    "text": "text", "syslog": "text",
    "json": "json", "jsonl": "json",
    "csv": "csv", "parquet": "parquet",
}

def read_bronze_batch(config: dict, sample_path: str, fmt: str, display_limit: int = 50) -> DataFrame:
    """
    Batch-read sample data and apply bronze preTransform, dsl_id, lookups, and postTransform.

    Returns:
        bronze DataFrame
    """
    spark_fmt = _FMT_MAP.get(fmt, fmt)
    al_conf = config.get("autoloader", {})
    bronze_conf = config.get("bronze", {})
    load_as_single_variant = bronze_conf.get("loadAsSingleVariant", False)

    if load_as_single_variant:
        # Mirror Auto Loader's singleVariantColumn behaviour: read raw text then
        # create a VARIANT 'data' column so preTransform try_variant_get() works.
        # withColumn preserves _metadata so the preTransform can still access
        # _metadata.file_path in the same selectExpr call.
        df = spark.read.text(sample_path)
        df = df.withColumn("data", spark_expr("parse_json(value)"))
    else:
        # Build read options
        read_opts = {}
        if fmt in ("json", "jsonl"):
            read_opts["multiLine"] = str(al_conf.get("multiline", "false"))
        elif fmt == "csv":
            read_opts["header"] = "true"
            read_opts["inferSchema"] = "true"
        for k, v in (al_conf.get("options") or {}).items():
            read_opts[k] = v

        schema_str = al_conf.get("schema") or (al_conf.get("cloudFiles") or {}).get("schema")
        reader = spark.read.format(spark_fmt).options(**read_opts)
        if schema_str:
            reader = reader.schema(schema_str)

        df = reader.load(sample_path)

    # preTransform
    bronze_conf = config.get("bronze", {})
    for pt in bronze_conf.get("preTransform", []):
        if isinstance(pt, list):
            df = df.selectExpr(*pt)
        elif isinstance(pt, str):
            df = df.selectExpr(pt)

    # dsl_id
    df = df.selectExpr(
        "*",
        "lower(concat(hex(unix_millis(current_timestamp())), substring(replace(uuid(), '-', ''), 1, 13))) as dsl_id"
    )

    # Lookups
    if bronze_conf.get("lookups"):
        df = apply_lookups(df, bronze_conf["lookups"])

    # postTransform
    if bronze_conf.get("postTransform"):
        df = df.selectExpr(*bronze_conf["postTransform"])

    # Drop
    drop_cols = [strip_backticks(c) for c in bronze_conf.get("drop", [])]
    existing_drops = [c for c in drop_cols if c in df.columns]
    if existing_drops:
        df = df.drop(*existing_drops)

    print(f"Bronze schema ({len(df.columns)} columns): {df.columns}")
    display(df.limit(display_limit))
    return df


# =============================================================================
# Silver
# =============================================================================

def run_silver(config: dict, bronze_df: DataFrame, display_limit: int = 50) -> dict:
    """
    Apply all silver transforms from the preset config.

    Returns:
        dict of {silver_table_name: DataFrame}
    """
    silver_dfs = {}

    for tr_conf in config.get("silver", {}).get("transform", []):
        silver_name = tr_conf["name"]
        print(f"\n{'='*60}")
        print(f"Silver table: {silver_name}")
        print(f"{'='*60}")

        input_ref = tr_conf.get("input")
        if input_ref and "." in str(input_ref):
            print(f"  Reading from existing table: {input_ref}")
            df = spark.read.table(input_ref)
        else:
            df = bronze_df

        if tr_conf.get("lookups"):
            df = apply_lookups(df, tr_conf["lookups"])

        if "filter" in tr_conf:
            print(f"  Filter: {tr_conf['filter']}")
            df = df.filter(tr_conf["filter"])

        temp_fields_conf = (tr_conf.get("utils") or {}).get("temporaryFields", [])
        if temp_fields_conf:
            df = df.selectExpr("*", *generate_field_exprs(temp_fields_conf))

        unreferenced_conf = (tr_conf.get("utils") or {}).get("unreferencedColumns", {})
        orig_cols = []
        if unreferenced_conf.get("preserve", False):
            to_omit = [strip_backticks(c) for c in unreferenced_conf.get("omitColumns", [])]
            orig_cols = [f"`{c}`" for c in df.columns if c not in to_omit]
        if "dsl_id" not in orig_cols and "`dsl_id`" not in orig_cols:
            orig_cols.append("dsl_id")

        df = df.selectExpr(*orig_cols, *generate_field_exprs(tr_conf.get("fields", [])))

        if temp_fields_conf:
            df = df.drop(*[t["name"] for t in temp_fields_conf])

        if "postFilter" in tr_conf:
            df = df.filter(tr_conf["postFilter"])

        silver_dfs[silver_name] = df
        print(f"  Schema ({len(df.columns)} columns): {df.columns}")
        display(df.limit(display_limit))

    return silver_dfs


# =============================================================================
# Gold
# =============================================================================

def run_gold(config: dict, silver_dfs: dict, display_limit: int = 50):
    """Apply all gold table mappings from the preset config and display each."""

    for tr_conf in config.get("gold", []):
        gold_name = tr_conf["name"]
        print(f"\n{'='*60}")
        print(f"Gold table: {gold_name}")
        print(f"{'='*60}")

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

        if "filter" in tr_conf:
            print(f"  Filter: {tr_conf['filter']}")
            df = df.filter(tr_conf["filter"])

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

        select_exprs = []
        if "dsl_id" in df.columns:
            select_exprs.append("dsl_id")
        select_exprs.extend(generate_field_exprs(tr_conf.get("fields", [])))

        # VARIANT output type is not needed for display and can fail in batch
        # selectExpr on some runtimes. Replace with STRING for explorer mode.
        select_exprs = [e.replace("AS VARIANT", "AS STRING") for e in select_exprs]

        df = df.selectExpr(*select_exprs)

        if "postFilter" in tr_conf:
            df = df.filter(tr_conf["postFilter"])

        print(f"  Schema ({len(df.columns)} columns): {df.columns}")
        display(df.limit(display_limit))


print("✓ DSL Lite explorer helpers loaded")
