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

# Note: bronze_database and silver_database validation happens after loading config
# to check if any table needs them (when using fully qualified paths, they can be omitted)

# Note: gold_database validation happens after loading config to check if any table needs it

# COMMAND ----------

import time
from typing import Optional, Dict, Any

from dsl import load_config_file, read_bronze_stream, make_silver_table, make_gold_table
from utils import sanitize_string_for_flow_name

# COMMAND ----------

config_data = load_config_file(preset_file)

# COMMAND ----------

# Validate bronze_database requirement: only needed if any silver table doesn't use fully qualified input
sl_conf = config_data.get('silver', {})
if not skip_bronze:
    # Need bronze_database when creating bronze tables (to know where to WRITE output)
    # Note: Fully qualified paths in silver.input only specify where to READ FROM, not where to write
    if bronze_database == "":
        raise Exception(
            "bronze_database is required when creating bronze tables (to specify where to write output). "
            "Fully qualified paths in 'input' fields only specify where to read from. "
            "Either provide 'bronze_database' parameter, or set 'skip_bronze=True' to use existing bronze tables."
        )
elif not skip_silver:
    # When skipping bronze but creating silver, check if silver tables need bronze_database
    silver_tables_need_bronze_db = False
    for tr_conf in sl_conf.get('transform', []):
        input_table = tr_conf.get("input")
        if not input_table or '.' not in input_table:
            silver_tables_need_bronze_db = True
            break
    if silver_tables_need_bronze_db and bronze_database == "":
        raise Exception(
            "bronze_database is required because at least one silver table doesn't specify a fully qualified 'input' path. "
            "Either add 'input: catalog.database.table' to each silver table in YAML, or provide 'bronze_database' parameter."
        )

# Validate silver_database requirement: only needed if any gold table doesn't use fully qualified input
gold_tables = config_data.get('gold', [])
if not skip_silver:
    # Need silver_database when creating silver tables (to know where to WRITE output)
    # Note: Fully qualified paths in gold.input only specify where to READ FROM, not where to write
    # Silver tables don't support per-table catalog/database like gold tables do
    if silver_database == "":
        raise Exception(
            "silver_database is required when creating silver tables (to specify where to write output). "
            "Fully qualified paths in 'input' fields only specify where to read from. "
            "Silver tables don't support per-table catalog/database configuration like gold tables do. "
            "Either provide 'silver_database' parameter, or set 'skip_silver=True' to use existing silver tables."
        )
else:
    # When skipping silver, check if gold tables need silver_database
    gold_tables_need_silver_db = False
    for tr_conf in gold_tables:
        input_name = tr_conf.get('input', '')
        if not input_name or '.' not in input_name:
            gold_tables_need_silver_db = True
            break
    if gold_tables_need_silver_db and silver_database == "":
        raise Exception(
            "silver_database is required because at least one gold table doesn't specify a fully qualified 'input' path. "
            "Either add 'input: catalog.database.table' to each gold table in YAML, or provide 'silver_database' parameter."
        )

# Validate gold_database requirement: only needed if any gold table omits 'database' in YAML
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
    # Only construct if bronze_database was provided (otherwise silver tables must use fully qualified input)
    if bronze_database:
        bronze_table_name = f"{bronze_database}.`{config_data.get('bronze', {}).get('name') or config_data['name']}`"
        print(f"Skipping bronze layer, using existing table: {bronze_table_name}")
    else:
        bronze_table_name = None
        print("Skipping bronze layer - silver tables must use fully qualified 'input' paths")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Silver Layer

# COMMAND ----------

if not skip_silver:
    def create_silver_table(tr_conf: Dict[str, Any]):
        tr_name = tr_conf.get("name") or config_data["name"]
        tbl_name = f"{silver_database}.`{tr_name}`"
        
        # Support fully qualified table names (catalog.database.table or database.table) in input field
        # If input is specified and contains dots, treat it as a fully qualified name; otherwise use default bronze_table_name
        input_table = tr_conf.get("input")
        if input_table and '.' in input_table:
            # Fully qualified name - use directly
            bronze_input = input_table
        else:
            # Use default bronze table name (backward compatible)
            if not bronze_table_name:
                raise Exception(f"Silver table '{tr_name}' requires either a fully qualified 'input: catalog.database.table' path, or 'bronze_database' parameter must be provided.")
            bronze_input = bronze_table_name
        
        df = make_silver_table(bronze_input, tr_conf)
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
    # When skipping silver, we map by silver table name (not input field - that's for bronze reference)
    # If silver_database is provided, construct table names; otherwise gold tables must use fully qualified input paths
    for tr_conf in sl_conf.get('transform', []):
        tr_name = tr_conf.get("name") or config_data["name"]
        if silver_database:
            # Construct from silver_database parameter (backward compatible)
            silver_tables[tr_name] = f"{silver_database}.`{tr_name}`"
        else:
            # No silver_database - gold tables must use fully qualified input paths
            # We still add the name to the dict for error message purposes, but it won't be used
            silver_tables[tr_name] = tr_name
    if silver_database:
        print(f"Skipping silver layer, using existing table(s): {list(silver_tables.values())}")
    else:
        print(f"Skipping silver layer - gold tables must use fully qualified 'input' paths")

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
    
    df = make_gold_table(silver_table_name, tr_conf)
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

