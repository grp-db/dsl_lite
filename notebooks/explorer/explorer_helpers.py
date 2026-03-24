# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC # DSL Lite Explorer — Helper Functions
# MAGIC
# MAGIC This file is intended to be loaded via `%run ./explorer_helpers` from `preset_explorer`.
# MAGIC It provides batch equivalents of the core DSL Lite transformation functions from `src/dsl.py`.

# COMMAND ----------

from yaml import load, Loader
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import (
    broadcast, col as spark_col, explode_outer, from_json, to_json,
    expr as spark_expr
)

spark = SparkSession.getActiveSession()


# =============================================================================
# Field expression helpers
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
# Lookup helpers
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
    """Apply one or more stream-static lookup joins to a DataFrame."""
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
# Variant explode fallback
# =============================================================================

def _explode_variant_fallback(df: DataFrame, explode_col: str) -> DataFrame:
    df = df.withColumn("_arr", from_json(to_json(spark_col(explode_col)), "array<string>"))
    df = df.withColumn("_exploded", explode_outer(spark_col("_arr")))
    df = df.withColumn("_exploded", spark_expr("parse_json(_exploded)")).drop("_arr")
    return df


print("✓ DSL Lite explorer helpers loaded")
