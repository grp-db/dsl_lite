"""
DSL Lite - Spark Declarative Pipeline (SDP) Execution

Lightweight security data pipeline framework for processing logs into OCSF-compliant tables.

Built with ❤️ by Databricks Field Engineering & Professional Services

Copyright © Databricks, Inc.
"""

from pyspark import pipelines as sdp
import pyspark.sql.functions as F
from pyspark.sql.types import StringType
from pyspark.sql import DataFrame, SparkSession, Column
from typing import Optional, Dict, Any, List, Union

from utils import get_qualified_table_name, sanitize_string_for_flow_name, get_ocsf_sink, substitute_secrets
from dsl import load_config_file, read_bronze_stream, make_silver_table, make_gold_table

config_file = spark.conf.get("dsl_lite.config_file", "")
config_data = load_config_file(config_file)
skip_bronze = spark.conf.get("dsl_lite.skip_bronze", "false").lower() == "true"
skip_silver = spark.conf.get("dsl_lite.skip_silver", "false").lower() == "true"

variant_table_properties = {
        "delta.minWriterVersion": "7",
        "delta.enableDeletionVectors": "true",
        "delta.minReaderVersion": "3",
        "delta.feature.variantType-preview": "supported",
        "delta.feature.variantShredding-preview": "supported",
        "delta.feature.deletionVectors": "supported",
        "delta.feature.invariants": "supported",
    }

sl_conf = config_data.get('silver', {})
silver_tables = {}

if not skip_bronze:
    # bronze layer
    bronze_table_name = get_qualified_table_name(
        "bronze", 
        config_data.get('bronze', {}).get("name") or config_data["name"], spark)
    print(f"Creating bronze table {bronze_table_name}")

    sdp.create_streaming_table(
        name=bronze_table_name,
        cluster_by = config_data.get('bronze', {}).get("clusterBy", ["time"]),
        table_properties = variant_table_properties,
    )

    def create_bronze_flow(input: str, add_opts: Optional[dict] = None):
        print(f"Creating bronze flow for {input}")
        @sdp.append_flow(
            name=f"bronze_{sanitize_string_for_flow_name(input)}",
            target=bronze_table_name,
            comment=f"Ingesting from {input}",
        )
        def flow():
            return read_bronze_stream(config_data, input, add_opts)

    # Load data from specified locations
    for inp in config_data['autoloader']['inputs']:
        create_bronze_flow(inp)
else:
    # Skip bronze - get bronze table name for silver to reference existing bronze
    bronze_table_name = get_qualified_table_name(
        "bronze", 
        config_data.get('bronze', {}).get("name") or config_data["name"], spark)

if not skip_silver:
    # silver layer
    def create_silver_table(tr_conf: Dict[str, Any]):
        tr_name = tr_conf.get("name") or config_data["name"]
        tbl_name = get_qualified_table_name("silver", tr_name, spark)
        silver_tables[tr_name] = tbl_name
        @sdp.table(
            name = get_qualified_table_name("silver", tr_conf.get("name") or config_data["name"], spark),
            cluster_by = tr_conf.get("clusterBy", ["time"]),
            table_properties = variant_table_properties,
        )
        def silver_table():
            # Support fully qualified table names (catalog.database.table or database.table) in input field
            # If input is specified and contains dots, treat it as a fully qualified name; otherwise use default bronze_table_name
            input_table = tr_conf.get("input")
            if input_table and '.' in input_table:
                # Fully qualified name - use directly
                bronze_input = input_table
            else:
                # Use default bronze table name (backward compatible)
                bronze_input = bronze_table_name
            return make_silver_table(bronze_input, tr_conf)

    for tr_conf in sl_conf.get('transform', []):
        create_silver_table(tr_conf)
else:
    # Map existing Silver tables from YAML config
    # When skipping silver, we map by silver table name (not input field - that's for bronze reference)
    for tr_conf in sl_conf.get('transform', []):
        tr_name = tr_conf.get("name") or config_data["name"]
        # Use get_qualified_table_name (backward compatible)
        silver_tables[tr_name] = get_qualified_table_name("silver", tr_name, spark)

# ocsf - gold layer
def create_gold_table(tr_conf: Dict[str, Any]):
    tr_name = tr_conf["name"]
    catalog = tr_conf.get("catalog")
    database = tr_conf.get("database")
    sink_name = get_ocsf_sink(tr_name, catalog=catalog, database=database, spark=spark)
    @sdp.append_flow(name=tr_name, target=sink_name)
    def gold_table():
        # Support fully qualified table names (catalog.database.table or database.table) in input field
        # If input contains dots, treat it as a fully qualified name; otherwise look up in silver_tables
        input_name = tr_conf['input']
        if '.' in input_name:
            # Fully qualified name - use directly
            silver_table_name = input_name
        else:
            # Simple name - look up in silver_tables
            if input_name not in silver_tables:
                raise Exception(f"Gold table '{tr_name}' references unknown silver table '{input_name}'. Available: {list(silver_tables.keys())}")
            silver_table_name = silver_tables[input_name]
        return make_gold_table(silver_table_name, tr_conf)

for gold_table in config_data.get('gold', []):
    create_gold_table(gold_table)
