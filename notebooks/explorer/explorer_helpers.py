# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC # DSL Lite Explorer — Helper Functions
# MAGIC
# MAGIC Loaded via `%run ./explorer_helpers` from `preset_explorer`.
# MAGIC Provides batch equivalents of the core DSL Lite transformation functions
# MAGIC and the bronze / silver / gold execution functions used by the explorer.

# COMMAND ----------

import re

from yaml import safe_load
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import (
    broadcast, col as spark_col, explode_outer, from_json, to_json,
    expr as spark_expr
)

spark = SparkSession.getActiveSession()


# =============================================================================
# Batch expression rewriter
# =============================================================================

def _rewrite_expr(e: str) -> str:
    """
    Rewrite expressions that use VARIANT-dependent functions so they work in
    batch/Spark-Connect mode without requiring the VARIANT type.

    - to_json(try_variant_get(col, '$.path' [, 'TYPE'])) → get_json_object(col, '$.path')
      (combined form — Okta/nested patterns wrap try_variant_get in to_json)
    - try_variant_get(col, '$.path', 'TYPE') → get_json_object(col, '$.path')
    - try_variant_get(col, '$.path') → get_json_object(col, '$.path')  [2-arg form]
    - CAST(... AS VARIANT) → CAST(... AS STRING)
    - to_json(data) → data
    """
    # 1. to_json(try_variant_get(col, 'path', 'type')) → get_json_object(col, 'path')
    e = re.sub(
        r"to_json\(\s*try_variant_get\(([^,]+),\s*('[^']*'),\s*'[^']*'\)\s*\)",
        r"get_json_object(\1, \2)",
        e,
        flags=re.IGNORECASE,
    )
    # 2. to_json(try_variant_get(col, 'path')) → get_json_object(col, 'path')  [2-arg]
    e = re.sub(
        r"to_json\(\s*try_variant_get\(([^,]+),\s*('[^']*')\)\s*\)",
        r"get_json_object(\1, \2)",
        e,
        flags=re.IGNORECASE,
    )
    # 3. try_variant_get(col, 'path', 'type') → get_json_object(col, 'path')  [3-arg]
    e = re.sub(
        r"try_variant_get\(([^,]+),\s*('[^']*'),\s*'[^']*'\)",
        r"get_json_object(\1, \2)",
        e,
        flags=re.IGNORECASE,
    )
    # 4. try_variant_get(col, 'path') → get_json_object(col, 'path')  [2-arg]
    e = re.sub(
        r"try_variant_get\(([^,]+),\s*('[^']*')\)",
        r"get_json_object(\1, \2)",
        e,
        flags=re.IGNORECASE,
    )
    # 5. to_json(data) → data  (data is already a JSON STRING in batch mode)
    e = re.sub(r"\bto_json\(\s*data\s*\)", "data", e, flags=re.IGNORECASE)
    # 6. CAST(... AS VARIANT) → CAST(... AS STRING)
    e = e.replace("AS VARIANT", "AS STRING")
    return e


def _rewrite_array_index(e: str) -> str:
    """
    Rewrite expr[n] array indexing to get(expr, n) for NULL-safe access.
    Only rewrites when [ is immediately preceded by ) (indexing a function result).
    Uses balanced-paren scanning to find the full array expression boundary.
    """
    if not re.search(r'\)\[\d+\]', e):
        return e

    result = []
    i = 0
    while i < len(e):
        # Detect ')' followed by '[digits]'
        if e[i] == ')':
            ahead = re.match(r'\[(\d+)\]', e[i + 1:])
            if ahead:
                n = ahead.group(1)
                # Build result_str including this closing paren, then find its matching open
                result_str = ''.join(result) + ')'
                depth, k = 0, len(result_str) - 1
                while k >= 0:
                    if result_str[k] == ')':
                        depth += 1
                    elif result_str[k] == '(':
                        depth -= 1
                        if depth == 0:
                            break
                    k -= 1
                # Walk back further to include the function/column name
                p = k - 1
                while p >= 0 and (result_str[p].isalnum() or result_str[p] == '_'):
                    p -= 1
                start = p + 1
                array_expr = result_str[start:]
                result = list(result_str[:start]) + list(f"get({array_expr}, {n})")
                i += 1 + len(ahead.group(0))  # skip past '[n]'
                continue
        result.append(e[i])
        i += 1

    return ''.join(result)


def _rewrite_exprs(exprs: list) -> list:
    return [_rewrite_array_index(_rewrite_expr(e)) for e in exprs]


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
        config = safe_load(f)

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
# Diagnostic helpers
# =============================================================================

def _null_summary(df: DataFrame, row_count: int) -> list:
    """Return list of column names where every row is NULL (likely a broken mapping)."""
    if row_count == 0:
        return []
    null_counts = df.selectExpr(*[
        f"sum(case when `{c}` is null then 1 else 0 end)"
        for c in df.columns
    ]).collect()[0]
    return [
        c for c, nc in zip(df.columns, null_counts)
        if nc == row_count and c != "dsl_id"
    ]


# =============================================================================
# Bronze
# =============================================================================

_FMT_MAP = {
    "text": "text", "syslog": "text",
    "json": "json", "jsonl": "json",
    "csv": "csv", "parquet": "parquet",
}

def read_bronze_batch(config: dict, sample_path: str, fmt: str,
                      display_limit: int = 50, input_row_limit: int = 0) -> DataFrame:
    """
    Batch-read sample data and apply bronze preTransform, dsl_id, lookups, and postTransform.

    input_row_limit: if > 0, caps rows at the initial read so downstream transforms and
    lookups run against fewer records — useful for fast iteration on big folders. 0 = no cap.

    Returns:
        bronze DataFrame
    """
    spark_fmt = _FMT_MAP.get(fmt, fmt)
    al_conf = config.get("autoloader", {})
    bronze_conf = config.get("bronze", {})
    load_as_single_variant = bronze_conf.get("loadAsSingleVariant", False)

    if load_as_single_variant:
        # Mirror Auto Loader's singleVariantColumn behaviour in batch mode.
        # We keep 'data' as a plain STRING (raw JSON) rather than VARIANT because
        # Spark Connect cannot serialise the VARIANT proto type and will throw
        # PySparkValueError("data type ... is not supported") on schema access.
        # All try_variant_get() calls are rewritten to get_json_object() below,
        # which works identically on STRING for display/validation purposes.
        df = spark.read.text(sample_path)
        df = df.withColumn("data", spark_col("value"))
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

    # Cap rows early so preTransform / lookups run against the limited set.
    if input_row_limit and input_row_limit > 0:
        df = df.limit(input_row_limit)
        print(f"  input_row_limit : capped at {input_row_limit} rows before transforms")

    # preTransform — rewrite VARIANT-dependent expressions for batch compatibility
    for pt in bronze_conf.get("preTransform", []):
        if isinstance(pt, list):
            df = df.selectExpr(*_rewrite_exprs(pt))
        elif isinstance(pt, str):
            df = df.selectExpr(_rewrite_expr(pt))

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

    row_count = df.count()
    print(f"  Rows    : {row_count}")
    print(f"  Columns : {len(df.columns)} → {df.columns}")
    display(df.limit(display_limit))
    return df


# =============================================================================
# Silver
# =============================================================================

def run_silver(config: dict, bronze_df: DataFrame, display_limit: int = 50,
               table_filter: list = None) -> dict:
    """
    Apply silver transforms from the preset config.

    table_filter: if non-empty, only run the listed silver tables (by name).
    Use to iterate on a single table in a preset that defines multiple.

    Returns:
        dict of {silver_table_name: DataFrame}
    """
    silver_dfs = {}
    tf = set(table_filter or [])

    for tr_conf in config.get("silver", {}).get("transform", []):
        silver_name = tr_conf["name"]
        if tf and silver_name not in tf:
            print(f"  [skipped] silver table '{silver_name}' not in table_filter")
            continue
        print(f"\n{'='*60}")
        print(f"Silver table: {silver_name}")
        print(f"{'='*60}")

        try:
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
                df = df.selectExpr("*", *_rewrite_exprs(generate_field_exprs(temp_fields_conf)))

            unreferenced_conf = (tr_conf.get("utils") or {}).get("unreferencedColumns", {})
            orig_cols = []
            if unreferenced_conf.get("preserve", False):
                to_omit = [strip_backticks(c) for c in unreferenced_conf.get("omitColumns", [])]
                orig_cols = [f"`{c}`" for c in df.columns if c not in to_omit]
            if "dsl_id" not in orig_cols and "`dsl_id`" not in orig_cols:
                orig_cols.append("dsl_id")

            df = df.selectExpr(*orig_cols, *_rewrite_exprs(generate_field_exprs(tr_conf.get("fields", []))))

            if temp_fields_conf:
                df = df.drop(*[t["name"] for t in temp_fields_conf])

            if "postFilter" in tr_conf:
                df = df.filter(tr_conf["postFilter"])

            row_count = df.count()
            print(f"  Rows    : {row_count}")
            print(f"  Columns : {len(df.columns)}")
            null_fields = _null_summary(df, row_count)
            if null_fields:
                print(f"  ⚠️  All-null fields (check silver mappings): {null_fields}")
            silver_dfs[silver_name] = df
            display(df.limit(display_limit))

        except Exception as e:
            print(f"  ❌ Error processing silver table '{silver_name}': {e}")

    return silver_dfs


# =============================================================================
# Gold
# =============================================================================

def run_gold(config: dict, silver_dfs: dict, display_limit: int = 50,
             table_filter: list = None):
    """
    Apply gold table mappings from the preset config and display each.

    table_filter: if non-empty, only run the listed gold tables (by name).
    """
    tf = set(table_filter or [])

    for tr_conf in config.get("gold", []):
        gold_name = tr_conf["name"]
        if tf and gold_name not in tf:
            print(f"  [skipped] gold table '{gold_name}' not in table_filter")
            continue
        print(f"\n{'='*60}")
        print(f"Gold table: {gold_name}")
        print(f"{'='*60}")

        try:
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
            select_exprs.extend(_rewrite_exprs(generate_field_exprs(tr_conf.get("fields", []))))

            df = df.selectExpr(*select_exprs)

            if "postFilter" in tr_conf:
                df = df.filter(tr_conf["postFilter"])

            row_count = df.count()
            if row_count == 0:
                print(f"  ⚠️  0 rows — filter may be too restrictive")
            else:
                print(f"  Rows    : {row_count}")
                null_fields = _null_summary(df, row_count)
                if null_fields:
                    print(f"  ⚠️  All-null fields (check gold mappings): {null_fields}")
            print(f"  Columns : {len(df.columns)}")
            display(df.limit(display_limit))

        except Exception as e:
            print(f"  ❌ Error processing gold table '{gold_name}': {e}")


print("✓ DSL Lite explorer helpers loaded")
