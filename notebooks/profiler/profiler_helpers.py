# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC # DSL Lite Profiler — Helper Functions
# MAGIC
# MAGIC Loaded via `%run ./profiler_helpers` from `pipeline_profiler`.
# MAGIC Requires `%run ../explorer/explorer_helpers` to be loaded first
# MAGIC (provides `read_bronze_batch`, `run_silver`, `run_gold`).

# COMMAND ----------

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.types import StructType
from pyspark.sql import functions as F

spark = SparkSession.getActiveSession()

# OCSF classification fields that must never be null in a gold table
_OCSF_REQUIRED = {
    "time", "category_uid", "category_name", "class_uid", "class_name",
    "type_uid", "activity_id", "severity_id", "severity",
}


# =============================================================================
# Schema comparison
# =============================================================================

def _flatten_schema(schema: StructType, prefix: str = "") -> dict:
    """Recursively flatten a StructType into dot-notation column → type strings."""
    fields = {}
    for field in schema.fields:
        full_name = f"{prefix}{field.name}"
        if isinstance(field.dataType, StructType):
            fields.update(_flatten_schema(field.dataType, prefix=f"{full_name}."))
        else:
            fields[full_name] = str(field.dataType)
    return fields


def compare_schemas(table_a: str, table_b: str, flatten: bool = False) -> None:
    """
    Print a column-by-column schema diff between two Delta tables.

    table_a: source / legacy table
    table_b: target / new dsl_lite table
    flatten: if True, recurse into nested struct fields
    """
    schema_a_raw = spark.table(table_a).schema
    schema_b_raw = spark.table(table_b).schema

    if flatten:
        schema_a = _flatten_schema(schema_a_raw)
        schema_b = _flatten_schema(schema_b_raw)
    else:
        schema_a = {f.name: str(f.dataType) for f in schema_a_raw.fields}
        schema_b = {f.name: str(f.dataType) for f in schema_b_raw.fields}

    all_cols = sorted(set(schema_a) | set(schema_b))
    missing = type_mismatch = new_cols = 0
    rows = []

    for col in all_cols:
        in_a, in_b = col in schema_a, col in schema_b
        type_a = schema_a.get(col, "—")
        type_b = schema_b.get(col, "—")

        if in_a and in_b:
            if type_a == type_b:
                status = "✓ match"
            else:
                status = "⚠ type mismatch"
                type_mismatch += 1
        elif in_a:
            status = "✗ missing from target"
            missing += 1
        else:
            status = "+ new in target"
            new_cols += 1

        rows.append((col, type_a, type_b, status))

    a_label = table_a.split(".")[-1]
    b_label = table_b.split(".")[-1]

    print(f"\nSchema diff:  {table_a}  →  {table_b}")
    print(f"  Source columns        : {len(schema_a)}")
    print(f"  Target columns        : {len(schema_b)}")
    print(f"  ✗ Missing from target : {missing}")
    print(f"  ⚠ Type mismatches     : {type_mismatch}")
    print(f"  + New in target       : {new_cols}")

    result = spark.createDataFrame(
        rows,
        ["column", f"type_source ({a_label})", f"type_target ({b_label})", "status"]
    )
    display(result.orderBy(F.col("status").desc(), "column"))


# =============================================================================
# Data profile
# =============================================================================

def profile_table(table_name: str, sample_size: int = 100) -> DataFrame:
    """
    Return a per-column null profile for a sample of rows from a Delta table.
    Columns: column, sampled_rows, null_count, null_pct
    """
    df = spark.table(table_name).limit(sample_size)
    n = df.count()

    if n == 0:
        print(f"  ⚠ {table_name}: 0 rows — cannot profile")
        return spark.createDataFrame([], "column STRING, sampled_rows LONG, null_count LONG, null_pct DOUBLE")

    null_expr = [f"sum(case when `{c}` is null then 1 else 0 end) as `{c}`" for c in df.columns]
    null_counts = df.selectExpr(*null_expr).collect()[0].asDict()

    rows = [
        (c, n, int(null_counts.get(c) or 0), round((null_counts.get(c) or 0) / n * 100, 1))
        for c in df.columns
    ]
    return spark.createDataFrame(rows, ["column", "sampled_rows", "null_count", "null_pct"])


def compare_profiles(table_a: str, table_b: str, sample_size: int = 100,
                     null_threshold: float = 80.0) -> None:
    """
    Compare null rates between source and target tables side by side.
    Flags columns where the target null rate exceeds null_threshold.
    """
    a_label = table_a.split(".")[-1]
    b_label = table_b.split(".")[-1]

    print(f"\nData profile comparison ({sample_size} rows each): {table_a}  →  {table_b}")
    prof_a = profile_table(table_a, sample_size)
    prof_b = profile_table(table_b, sample_size)

    joined = (
        prof_a.alias("a")
        .join(prof_b.alias("b"), on="column", how="outer")
        .select(
            F.coalesce(F.col("a.column"), F.col("b.column")).alias("column"),
            F.col(f"a.null_pct").alias(f"null_pct_{a_label}"),
            F.col(f"b.null_pct").alias(f"null_pct_{b_label}"),
        )
        .withColumn(
            "status",
            F.when(F.col(f"null_pct_{b_label}").isNull(), "✗ missing from target")
             .when(F.col(f"null_pct_{a_label}").isNull(), "+ new in target")
             .when(F.col(f"null_pct_{b_label}") >= null_threshold, f"⚠ high null rate in target (≥{null_threshold}%)")
             .when(
                F.col(f"null_pct_{b_label}") > F.col(f"null_pct_{a_label}") + 20,
                "⚠ null rate increased in target"
             )
             .otherwise("✓")
        )
    )

    display(joined.orderBy(F.col("status").desc(), "column"))


# =============================================================================
# E2E sample pipeline run
# =============================================================================

def run_e2e_sample(config: dict, sample_path: str, fmt: str,
                   n_rows: int = 100) -> tuple:
    """
    Run n_rows through the full bronze → silver → gold pipeline using the preset.
    Returns (bronze_df, silver_dfs).
    Depends on read_bronze_batch / run_silver / run_gold from explorer_helpers.
    """
    print(f"\nE2E sample run — {n_rows} rows through full pipeline")
    bronze_df = read_bronze_batch(config, sample_path, fmt,
                                  display_limit=n_rows, input_row_limit=n_rows)
    silver_dfs = run_silver(config, bronze_df, display_limit=n_rows)
    run_gold(config, silver_dfs, display_limit=n_rows)
    return bronze_df, silver_dfs


# =============================================================================
# OCSF coverage check
# =============================================================================

def check_ocsf_coverage(df: DataFrame, table_name: str,
                        null_threshold: float = 80.0) -> None:
    """
    Report field population rates for a gold DataFrame.
    Flags required OCSF fields that are 100% null and any field above null_threshold%.
    """
    n = df.count()
    if n == 0:
        print(f"  ⚠ {table_name}: 0 rows — cannot check coverage")
        return

    null_expr = [f"sum(case when `{c}` is null then 1 else 0 end) as `{c}`" for c in df.columns]
    null_counts = df.selectExpr(*null_expr).collect()[0].asDict()

    rows = []
    for c in df.columns:
        null_count = int(null_counts.get(c) or 0)
        null_pct = round(null_count / n * 100, 1)
        required = c in _OCSF_REQUIRED

        if null_pct == 100 and required:
            status = "✗ required field empty"
        elif null_pct == 100:
            status = "✗ completely empty"
        elif null_pct >= null_threshold:
            status = f"⚠ high null rate (≥{null_threshold}%)"
        else:
            status = "✓"

        rows.append((c, n, null_count, null_pct, "yes" if required else "", status))

    result = spark.createDataFrame(
        rows, ["column", "total_rows", "null_count", "null_pct", "ocsf_required", "status"]
    )
    print(f"\nOCSF coverage: {table_name}  ({n} rows sampled)")
    display(result.orderBy(F.col("null_pct").desc(), "column"))


print("✓ DSL Lite profiler helpers loaded")
