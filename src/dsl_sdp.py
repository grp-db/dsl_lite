"""
DSL Lite - Spark Declarative Pipeline (SDP) Execution

Lightweight security data pipeline framework for processing logs into OCSF-compliant tables.
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

variant_table_properties = {
        "delta.minWriterVersion": "7",
        "delta.enableDeletionVectors": "true",
        "delta.minReaderVersion": "3",
        "delta.feature.variantType-preview": "supported",
        "delta.feature.variantShredding-preview": "supported",
        "delta.feature.deletionVectors": "supported",
        "delta.feature.invariants": "supported",
    }

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

sl_conf = config_data.get('silver', {})
silver_tables = {}

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
        return make_silver_table(bronze_table_name, tr_conf)

for tr_conf in sl_conf.get('transform', []):
    create_silver_table(tr_conf)

# ocsf - gold layer
def create_gold_table(tr_conf: Dict[str, Any]):
    tr_name = tr_conf["name"]
    sink_name = get_ocsf_sink(tr_name, spark)
    @sdp.append_flow(name=tr_name, target=sink_name)
    def gold_table():
        return make_gold_table(silver_tables[tr_conf['input']], tr_conf)

for gold_table in config_data.get('gold', []):
    create_gold_table(gold_table)
