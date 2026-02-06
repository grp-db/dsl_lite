# Databricks notebook source
# MAGIC """
# MAGIC DSL Lite - Spark Structured Streaming (SSS) Medallion Execution
# MAGIC
# MAGIC Combined execution of Bronze → Silver → Gold layers in a single notebook.
# MAGIC
# MAGIC Built with ❤️ by Databricks Field Engineering & Professional Services
# MAGIC
# MAGIC Copyright © Databricks, Inc.
# MAGIC """

# COMMAND ----------

dbutils.widgets.text("bronze_database", "", "1. Bronze Database")
dbutils.widgets.text("silver_database", "", "2. Silver Database")
dbutils.widgets.text("gold_database", "", "3. Gold Database (optional - only needed if tables omit 'database' in YAML)")
dbutils.widgets.dropdown("skip_bronze", "False", ["True", "False"], "4. Skip Bronze (use existing)")
dbutils.widgets.dropdown("skip_silver", "False", ["True", "False"], "5. Skip Silver (use existing)")
dbutils.widgets.dropdown("continuous", "False", ["True", "False"], "6. Run Continuously")
dbutils.widgets.text("preset_file", "", "7. Preset File")
dbutils.widgets.text("checkpoints_location", "", "8. Checkpoints Location")

# COMMAND ----------

bronze_database = dbutils.widgets.get("bronze_database")
silver_database = dbutils.widgets.get("silver_database")
gold_database = dbutils.widgets.get("gold_database")
skip_bronze = dbutils.widgets.get("skip_bronze") == "True"
skip_silver = dbutils.widgets.get("skip_silver") == "True"
preset_file = dbutils.widgets.get("preset_file")
checkpoints_location = dbutils.widgets.get("checkpoints_location")
is_continuous = dbutils.widgets.get("continuous") == "True"

if preset_file == "" or checkpoints_location == "":
    raise Exception("Please fill in: preset_file, checkpoints_location")

if not skip_bronze and bronze_database == "":
    raise Exception("Please fill in: bronze_database (or set skip_bronze=True)")

if not skip_silver and silver_database == "":
    raise Exception("Please fill in: silver_database (or set skip_silver=True)")

# Note: gold_database validation happens after loading config to check if any table needs it

# COMMAND ----------

import time
from typing import Optional, Dict, Any

from dsl import load_config_file, read_bronze_stream, make_silver_table, make_gold_table
from utils import sanitize_string_for_flow_name

# COMMAND ----------

config_data = load_config_file(preset_file)

# COMMAND ----------

# Validate gold_database requirement: only needed if any gold table omits 'database' in YAML
gold_tables = config_data.get('gold', [])
if gold_tables:
    tables_missing_database = [t.get("name") for t in gold_tables if not t.get("database")]
    if tables_missing_database and gold_database == "":
        raise Exception(
            f"gold_database is required because the following gold table(s) don't specify 'database' in YAML: {', '.join(tables_missing_database)}. "
            f"Either add 'database' to each table in YAML, or provide 'gold_database' parameter as fallback."
        )

# COMMAND ----------

variant_table_properties = {
    "delta.minWriterVersion": "7",
    "delta.enableDeletionVectors": "true",
    "delta.minReaderVersion": "3",
    "delta.feature.variantType-preview": "supported",
    "delta.feature.variantShredding-preview": "supported",
    "delta.feature.deletionVectors": "supported",
    "delta.feature.invariants": "supported",
}

# COMMAND ----------

sl_conf = config_data.get('silver', {})
silver_tables = {}

# COMMAND ----------
# MAGIC %md
# MAGIC ## Bronze Layer

# COMMAND ----------

if not skip_bronze:
    bronze_table_name = f"{bronze_database}.`{config_data.get('bronze', {}).get('name') or config_data['name']}`"
    print(f"Creating bronze table {bronze_table_name}")
    
    bronze_cluster_by = config_data.get('bronze', {}).get("clusterBy", ["time"])
    
    def start_bronze_flow(input: str, add_opts: Optional[dict] = None):
        df = read_bronze_stream(config_data, input, add_opts)
        writer = df.writeStream \
            .option("checkpointLocation", f"{checkpoints_location}/bronze-{sanitize_string_for_flow_name(input)}") \
            .queryName(f"bronze-{sanitize_string_for_flow_name(input)}")
        
        if bronze_cluster_by:
            writer = writer.clusterBy(*bronze_cluster_by)
        if not is_continuous:
            writer = writer.trigger(availableNow=True)
        
        stream = writer.toTable(bronze_table_name)
        return stream
    
    # Load data from specified locations
    bronze_streams = []
    for inp in config_data['autoloader']['inputs']:
        bronze_streams.append(start_bronze_flow(inp))
    
    print(f"Started {len(bronze_streams)} bronze stream(s)")
else:
    # Skip bronze - get bronze table name for silver to reference existing bronze
    bronze_table_name = f"{bronze_database}.`{config_data.get('bronze', {}).get('name') or config_data['name']}`"
    print(f"Skipping bronze layer, using existing table: {bronze_table_name}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Silver Layer

# COMMAND ----------

if not skip_silver:
    def create_silver_table(tr_conf: Dict[str, Any]):
        tr_name = tr_conf.get("name") or config_data["name"]
        tbl_name = f"{silver_database}.`{tr_name}`"
        df = make_silver_table(bronze_table_name, tr_conf)
        writer = df.writeStream \
            .option("checkpointLocation", f"{checkpoints_location}/silver-{sanitize_string_for_flow_name(tr_name)}") \
            .queryName(f"silver-{sanitize_string_for_flow_name(tr_name)}")
        
        cluster_by = tr_conf.get("clusterBy", ["time"])
        if cluster_by:
            writer = writer.clusterBy(*cluster_by)
        if not is_continuous:
            writer = writer.trigger(availableNow=True)
        
        stream = writer.toTable(tbl_name)
        silver_tables[tr_name] = tbl_name
        return stream
    
    silver_streams = []
    for tr_conf in sl_conf.get('transform', []):
        silver_streams.append(create_silver_table(tr_conf))
    
    print(f"Started {len(silver_streams)} silver stream(s)")
else:
    # Map existing Silver tables from YAML config
    for tr_conf in sl_conf.get('transform', []):
        tr_name = tr_conf.get("name") or config_data["name"]
        silver_tables[tr_name] = f"{silver_database}.`{tr_name}`"
    print(f"Skipping silver layer, using existing table(s): {list(silver_tables.values())}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Gold Layer

# COMMAND ----------

def create_gold_table(tr_conf: Dict[str, Any]):
    tr_name = tr_conf["name"]
    catalog = tr_conf.get("catalog")
    database = tr_conf.get("database") or gold_database
    if not database:
        raise Exception(f"Table '{tr_name}' must specify 'database' in YAML, or provide 'gold_database' parameter as fallback")
    if catalog:
        tbl_name = f"`{catalog}`.`{database}`.`{tr_name}`"
    else:
        tbl_name = f"{database}.`{tr_name}`"
    
    if tr_conf['input'] not in silver_tables:
        raise Exception(f"Gold table '{tr_name}' references unknown silver table '{tr_conf['input']}'. Available: {list(silver_tables.keys())}")
    
    df = make_gold_table(silver_tables[tr_conf['input']], tr_conf)
    writer = df.writeStream \
        .option("checkpointLocation", f"{checkpoints_location}/gold-{sanitize_string_for_flow_name(tr_name)}") \
        .queryName(f"gold-{sanitize_string_for_flow_name(tr_name)}")
    
    cluster_by = tr_conf.get("clusterBy")
    if cluster_by:
        writer = writer.clusterBy(*cluster_by)
    if not is_continuous:
        writer = writer.trigger(availableNow=True)
    
    stream = writer.toTable(tbl_name)
    return stream

gold_streams = []
for gold_table in config_data.get('gold', []):
    gold_streams.append(create_gold_table(gold_table))

print(f"Started {len(gold_streams)} gold stream(s)")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Wait for Completion

# COMMAND ----------

if not is_continuous:
    print("Waiting for all streams to finish...")
    while len(spark.streams.active):
        active_count = len(spark.streams.active)
        print(f"  Active streams: {active_count}")
        time.sleep(5)
    print("✅ All streams completed!")
else:
    print("Running continuously. Streams will run until manually stopped.")
    spark.streams.awaitAnyTermination()

