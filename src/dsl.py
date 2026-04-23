"""
DSL Lite - Core Logic

Built with ❤️ by Databricks Field Engineering & Professional Services

Copyright © Databricks, Inc.
"""

from yaml import safe_load
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import broadcast, col as spark_col, explode_outer, from_json, to_json, expr
from typing import Optional, Dict, Any, List, Union
from utils import substitute_secrets


def load_config_file(config_file: str):
    if not config_file:
        raise Exception("No config file name provided")
    with open(config_file, "r") as f:
        config_data = safe_load(f)
    if not config_data:
        raise Exception(f"Can't read config file {config_file}" )

    return config_data



default_autoloader_options = {
    # "cloudFiles.useNotifications": "true",
    "cloudFiles.inferColumnTypes": "true",

}

def get_al_opts(fmt: str, al_conf: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    if not al_conf:
        al_conf = {}
    if fmt == "json":
        return {"cloudFiles.format": "json", "multiLine": al_conf.get("multiline", "false")}
    elif fmt == "jsonl":
        return {"cloudFiles.format": "json"}
    return {"cloudFiles.format": fmt}


def read_bronze_stream(config: Dict[str, Any], input: str, add_opts: Optional[dict] = None) -> DataFrame:
    al_conf = config['autoloader']
    al_opts = default_autoloader_options | get_al_opts(al_conf['format'].lower(), al_conf)
    bronze_conf = config.get('bronze', {})
    if bronze_conf.get('loadAsSingleVariant', False):
        al_opts["singleVariantColumn"] = "data"
    clf_opts = {}
    schema = ""
    for k, v in (al_conf.get("cloudFiles") or {}).items():
        if k == "schemaHintsFile":  # TODO: add handling of schemaHintsFile
            continue
        if k == "schema":
            schema = v
        else:
            clf_opts[f"cloudFiles.{k}"] = v
    al_opts = al_opts | clf_opts | (al_conf.get("options", {})) | (add_opts or {})
    al_opts = substitute_secrets(al_opts)
    print(f"Reading from {input} with options {al_opts}")
    reader = SparkSession.getActiveSession().readStream.format("cloudFiles").options(**al_opts)
    if "schema" in al_conf:
        schema = al_conf['schema']
    if schema:
        reader = reader.schema(schema)
    # TODO: add handling of schemaFile
    df = reader.load(input)
    # TODO: copy implementation
    pre_transforms = bronze_conf.get('preTransform', [])
    if pre_transforms:
        # Auto-inject _metadata into the first preTransform pass.
        # _metadata is a hidden Auto Loader column not included in "*" — it must be
        # explicitly selected before any selectExpr, or it's gone from the DF.
        # Guard against users who already declare it manually.
        first_pass = list(pre_transforms[0])
        if not any(e.strip().strip('"') == "_metadata" for e in first_pass):
            first_pass = first_pass + ["_metadata"]
        pre_transforms = [first_pass] + list(pre_transforms[1:])
    for pt in pre_transforms:
        df = df.selectExpr(*pt)

    # Auto-inject standard bronze columns — engine always provides these so preset
    # authors don't have to. Guards prevent duplicates if a preset declares them manually.
    is_json = bronze_conf.get('loadAsSingleVariant', False)
    payload_expr = "to_json(data)" if is_json else "value"
    auto_exprs = []
    if "record_id" not in df.columns:
        auto_exprs.append(f"md5(concat_ws('_', {payload_expr}, _metadata.file_name)) as record_id")
    if "date" not in df.columns:
        auto_exprs.append("CAST(time AS DATE) as date")
    if "processed_time" not in df.columns:
        auto_exprs.append("CURRENT_TIMESTAMP() as processed_time")
    if auto_exprs:
        df = df.selectExpr("*", *auto_exprs)

    # dsl_id: timestamp hex + 13 chars of uuid (streaming-safe; monotonically_increasing_id() is not supported in streaming).
    # Note: In streaming micro-batches, uuid()/timestamp may repeat for all rows in a batch, so duplicate dsl_ids can occur; dedupe by (dsl_id, time, source, ...) if needed.
    # Substring uses 1-based position (Spark SQL); use 1 not 0 for first 13 chars of uuid.
    if "dsl_id" not in df.columns:
        df = df.selectExpr(
            "*",
            "lower(concat(hex(unix_millis(current_timestamp())), substring(replace(uuid(), '-', ''), 1, 13))) as dsl_id"
        )

    # Apply lookups if configured
    lookups = bronze_conf.get('lookups', [])
    if lookups:
        df = apply_lookups(df, lookups)

    # Optional: transform after lookups (i.e. build named_struct from lookup columns)
    post_transforms = bronze_conf.get('postTransform', [])
    if post_transforms:
        df = df.selectExpr(*post_transforms)

    # Optional: drop columns by name (i.e. after building a struct from lookup columns)
    drop_cols = bronze_conf.get('drop', [])
    if drop_cols:
        drop_cols = [strip_backticks(c) for c in drop_cols]
        existing = [c for c in drop_cols if c in df.columns]
        if existing:
            df = df.drop(*existing)

    # Enforce standard bronze column order: identity → routing → time → payload → provenance → lineage.
    # Extra columns (from lookups etc.) are appended after the standard set.
    payload_col = "data" if is_json else "value"
    standard_cols = ["record_id", "source", "sourcetype", "time", "date", payload_col, "_metadata", "processed_time", "dsl_id"]
    ordered = [c for c in standard_cols if c in df.columns]
    extra_cols = [c for c in df.columns if c not in standard_cols]
    df = df.select(*(ordered + extra_cols))

    return df


def populate_nested(d: Dict[str, Any], parts: List[str], expr: str):
    if len(parts) == 1:
        d[parts[0]] = expr
    else:
        nested = d.get(parts[0], {})
        populate_nested(nested, parts[1:], expr)
        d[parts[0]] = nested


def generate_struct(k: str, v: Union[Dict[str, Any], str]) -> str:
    if isinstance(v, str):
        return f"{v} as `{k}`"
    elif isinstance(v, dict):
        fields = [generate_struct(k, v) for k, v in v.items()]
        return f"struct({', '.join(fields)}) as `{k}`"
    else:
        raise Exception(f"Wrong type for {v}")


def generate_field_exprs(fields: List[Dict[str, Any]]) -> List[str]:
    new_cols = []
    nested = {}
    for f in fields:
        full_name = f['name']
        expr = ""
        if "expr" in f:
            expr = f['expr']
        elif "literal" in f:
            literal = f['literal']
            if isinstance(literal, str):
                expr = f"'{literal}'"
            else:
                expr = literal
        elif "from" in f:
            expr = f['from']
        else:
            raise Exception(f"Invalid field config {f}")

        if '.' in full_name:
            populate_nested(nested, full_name.split('.'), expr)
        else:
            new_cols.append(f"{expr} as `{full_name}`")

    for k, v in nested.items():
        new_cols.append(generate_struct(k, v))

    return new_cols


def strip_backticks(c: str) -> str:
    if c and c[0] == '`' and c[-1] == '`':
        return c[1:-1]
    return c


def read_lookup(source_conf: Dict[str, Any]) -> DataFrame:
    """
    Read a lookup table or file.
    
    Args:
        source_conf: Configuration dict with 'type', 'path', optionally 'format' and 'options'
    
    Returns:
        DataFrame: The lookup DataFrame (batch read, not streaming)
    """
    source_type = source_conf.get('type', 'table')
    path = source_conf.get('path')
    
    if not path:
        raise Exception("Lookup source must specify 'path'")
    
    spark = SparkSession.getActiveSession()
    
    if source_type == 'table':
        # Read as table (supports fully qualified names: catalog.database.table)
        return spark.read.table(path)
    elif source_type in ['csv', 'parquet', 'json', 'jsonl']:
        # Read as file
        format_type = source_conf.get('format', source_type)
        options = source_conf.get('options', {})
        
        reader = spark.read.format(format_type)
        if options:
            reader = reader.options(**options)
        
        return reader.load(path)
    else:
        raise Exception(f"Unsupported lookup source type: {source_type}")


def apply_lookups(df: DataFrame, lookups: List[Dict[str, Any]]) -> DataFrame:
    """
    Apply one or more lookup joins to a DataFrame.
    
    Args:
        df: Main DataFrame (streaming or batch)
        lookups: List of lookup configurations
    
    Returns:
        DataFrame: DataFrame with lookup columns added
    """
    result_df = df
    
    for lookup_conf in lookups:
        lookup_name = lookup_conf.get('name', 'unnamed')
        
        # Read lookup table/file (batch read)
        try:
            lookup_df = read_lookup(lookup_conf['source'])
        except Exception as e:
            raise Exception(f"Failed to read lookup '{lookup_name}': {str(e)}")
        
        # Build join condition
        join_conf = lookup_conf.get('join', {})
        if not join_conf:
            raise Exception(
                f"Lookup '{lookup_name}' must specify a 'join' section with 'on' conditions. "
                f"Available keys in lookup config: {list(lookup_conf.keys())}"
            )
        
        join_type = join_conf.get('type', 'left')
        
        # Handle YAML boolean issue: 'on' is interpreted as True in YAML
        # Try 'on' first (if quoted as "on" in YAML), then True (if unquoted)
        # Note: Users should quote 'on' as "on" in YAML to avoid this issue
        join_conditions = join_conf.get('on') or join_conf.get(True) or []
        
        # If join_conditions is a list of dicts (from YAML parsing issue), convert to simple format
        if join_conditions and isinstance(join_conditions, list) and len(join_conditions) > 0:
            if isinstance(join_conditions[0], dict):
                # Convert from [{'left': 'source', 'right': 'source'}, ...] format
                # This happens when YAML parses the list incorrectly
                # Extract the 'left' or 'right' value (they should be the same for simple format)
                join_conditions = [item.get('left') or item.get('right') for item in join_conditions if isinstance(item, dict)]
        
        if not join_conditions:
            raise Exception(
                f"Lookup '{lookup_name}' must specify join conditions in 'join.on'. "
                f"Note: In YAML, 'on:' must be quoted as '\"on\":' to avoid being interpreted as boolean True. "
                f"Found join config: {join_conf}"
            )
        
        # Parse join conditions using Spark Column API for better type safety
        join_exprs = []
        for condition in join_conditions:
            if '=' in condition:
                # Format: "main.column = lookup.column"
                parts = [p.strip() for p in condition.split('=', 1)]  # Split on first '=' only
                if len(parts) != 2:
                    raise Exception(f"Invalid join condition format: {condition}. Expected 'main.column = lookup.column'")
                
                main_col_expr = parts[0].replace('main.', '').strip()
                lookup_col_expr = parts[1].replace('lookup.', '').strip()
                
                # Validate columns exist
                main_col_name = strip_backticks(main_col_expr)
                lookup_col_name = strip_backticks(lookup_col_expr)
                
                if main_col_name not in result_df.columns:
                    raise Exception(f"Join condition error in lookup '{lookup_name}': column '{main_col_name}' not found in main DataFrame")
                if lookup_col_name not in lookup_df.columns:
                    raise Exception(f"Join condition error in lookup '{lookup_name}': column '{lookup_col_name}' not found in lookup DataFrame")
                
                # Build Column expression using spark_col() with explicit alias references
                join_exprs.append(spark_col(f"main.{main_col_name}") == spark_col(f"lookup.{lookup_col_name}"))
            else:
                # Simple format: just column name (assumes same name in both tables)
                col_name = strip_backticks(condition.strip())
                
                if col_name not in result_df.columns:
                    raise Exception(
                        f"Join condition error in lookup '{lookup_name}': column '{col_name}' not found in main DataFrame. "
                        f"Available columns: {result_df.columns}"
                    )
                if col_name not in lookup_df.columns:
                    raise Exception(
                        f"Join condition error in lookup '{lookup_name}': column '{col_name}' not found in lookup DataFrame. "
                        f"Available columns: {lookup_df.columns}"
                    )
                
                # For same column name, use spark_col() with explicit aliases to avoid ambiguity
                join_exprs.append(spark_col(f"main.{col_name}") == spark_col(f"lookup.{col_name}"))
        
        # Combine multiple conditions with AND
        if len(join_exprs) == 1:
            join_expr = join_exprs[0]
        else:
            join_expr = join_exprs[0]
            for expr in join_exprs[1:]:
                join_expr = join_expr & expr
        
        # Determine which lookup columns to include (keep original names for join, prefix after)
        select_cols = lookup_conf.get('select', [])
        prefix = lookup_conf.get('prefix', '')
        
        # Validate selected columns exist in lookup
        if select_cols:
            for col_name in select_cols:
                if col_name not in lookup_df.columns:
                    raise Exception(f"Lookup '{lookup_name}': column '{col_name}' not found in lookup DataFrame. Available columns: {lookup_df.columns}")
            lookup_cols_to_join = select_cols
        else:
            # Include all lookup columns
            lookup_cols_to_join = lookup_df.columns
        
        # Apply broadcast hint for small lookups (optional, can be configured)
        if lookup_conf.get('broadcast', False):
            lookup_df = broadcast(lookup_df)
        
        # Perform join (stream-static join for streaming DataFrames)
        # Spark automatically handles stream-static joins when joining streaming with batch DataFrame
        # Use aliases to avoid column name conflicts
        main_df_alias = result_df.alias("main")
        lookup_df_alias = lookup_df.alias("lookup")
        
        if join_type == 'left':
            joined_df = main_df_alias.join(lookup_df_alias, join_expr, 'left')
        elif join_type == 'inner':
            joined_df = main_df_alias.join(lookup_df_alias, join_expr, 'inner')
        elif join_type == 'right':
            joined_df = main_df_alias.join(lookup_df_alias, join_expr, 'right')
        elif join_type == 'full':
            joined_df = main_df_alias.join(lookup_df_alias, join_expr, 'full')
        else:
            raise Exception(f"Unsupported join type: {join_type}. Must be one of: left, inner, right, full")
        
        # After join, select main columns and lookup columns with prefix
        main_cols = [spark_col(f"main.{col}").alias(col) for col in result_df.columns]
        if prefix:
            lookup_cols = [spark_col(f"lookup.{col}").alias(f"{prefix}{col}") for col in lookup_cols_to_join]
        else:
            lookup_cols = [spark_col(f"lookup.{col}") for col in lookup_cols_to_join]
        
        result_df = joined_df.select(*main_cols, *lookup_cols)
    
    return result_df


# TODO: make sure that we handle data in the same order as described in the docs:
# https://docs.sl.antimatter.io/preset-development/notebook-preset-development-tool#232-order-of-operations
def make_silver_table(bronze_table_name: str, tr_conf: Dict[str, Any]) -> DataFrame:
    df = SparkSession.getActiveSession().readStream.option("skipChangeCommits", "true").table(bronze_table_name)
    
    # Apply lookups BEFORE other transformations (so lookup columns are available for field expressions)
    lookups = tr_conf.get('lookups', [])
    if lookups:
        df = apply_lookups(df, lookups)
    
    if "filter" in tr_conf:
        df = df.filter(tr_conf['filter'])

    temporary_fields = tr_conf.get('utils', {}).get('temporaryFields', [])
    if temporary_fields:
        temp_fields = generate_field_exprs(temporary_fields)
        df = df.selectExpr("*", *temp_fields)
    
    unreferenced_cols_conf = tr_conf.get('utils', {}).get('unreferencedColumns', {})
    orig_cols = []
    if unreferenced_cols_conf.get('preserve', False):
        to_omit = unreferenced_cols_conf.get('omitColumns', [])
        if to_omit:
            to_omit = [strip_backticks(c) for c in to_omit]
            orig_cols = [f"`{c}`" for c in df.columns if c not in to_omit]
        else:
            orig_cols = df.columns
    if "dsl_id" not in orig_cols and "`dsl_id`" not in orig_cols:
        orig_cols.append("dsl_id")
    new_fields = generate_field_exprs(tr_conf.get("fields", []))
            
    ndf = df.selectExpr(*orig_cols, *new_fields)

    if temporary_fields:
        temp_fields_names = [t['name'] for t in temporary_fields]
        ndf = ndf.drop(*temp_fields_names)
    
    if "postFilter" in tr_conf:
        ndf = ndf.filter(tr_conf['postFilter'])
    return ndf


def _explode_variant_fallback(df: DataFrame, explode_col: str) -> DataFrame:
    """Fallback when variant_explode_outer/lateralJoin are not available: convert VARIANT array via to_json/from_json/explode/parse_json."""
    df = df.withColumn("_arr", from_json(to_json(spark_col(explode_col)), "array<string>"))
    df = df.withColumn("_exploded", explode_outer(spark_col("_arr")))
    df = df.withColumn("_exploded", expr("parse_json(_exploded)")).drop("_arr")
    return df


def make_gold_table(silver_table_name: str, tr_conf: Dict[str, Any]) -> DataFrame:
    df = SparkSession.getActiveSession().readStream.option("skipChangeCommits", "true").table(silver_table_name)
    if "filter" in tr_conf:
        df = df.filter(tr_conf['filter'])

    # Optional: explode an array (or variant array) column so each element becomes a row.
    # Use when one silver row has an array of items (e.g. DNS queries) and you want one gold row per item.
    # Field expressions can reference the exploded element as "_exploded" (e.g. try_variant_get(_exploded, '$.hostname', 'STRING')).
    explode_col = tr_conf.get("explode")
    if explode_col:
        # explode_outer() requires ARRAY or MAP; VARIANT columns use variant_explode_outer when available, else a conversion.
        field = next((f for f in df.schema.fields if f.name == explode_col), None)
        is_variant = field is not None and "variant" in str(field.dataType).lower()
        if is_variant:
            # Prefer variant_explode_outer + lateralJoin (Spark 4 / DBR 16.1+). TVF returns pos, key, value; we expose value as _exploded.
            spark_session = SparkSession.getActiveSession()
            tvf = getattr(getattr(spark_session, "tvf", None), "variant_explode_outer", None)
            lateral_join = getattr(df, "lateralJoin", None)
            if tvf is not None and lateral_join is not None:
                try:
                    exploded_tbl = tvf(spark_col(explode_col))
                    df = df.lateralJoin(exploded_tbl, how="left_outer")
                    df = df.withColumnRenamed("value", "_exploded").drop("pos", "key")
                except Exception:
                    # Fallback if TVF/lateralJoin fails (e.g. runtime mismatch)
                    df = _explode_variant_fallback(df, explode_col)
            else:
                df = _explode_variant_fallback(df, explode_col)
        else:
            df = df.withColumn("_exploded", explode_outer(spark_col(explode_col)))

    new_fields = generate_field_exprs(tr_conf.get("fields", []))
    # Only include dsl_id if it exists in the source DataFrame (for cases where we skip bronze/silver and source table doesn't have it)
    select_exprs = []
    if "dsl_id" in df.columns:
        select_exprs.append("dsl_id")
    select_exprs.extend(new_fields)
    ndf = df.selectExpr(*select_exprs)
    if "postFilter" in tr_conf:
        ndf = ndf.filter(tr_conf['postFilter'])
    
    return ndf
