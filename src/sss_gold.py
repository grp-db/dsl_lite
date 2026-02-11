# Databricks notebook source
# MAGIC """
# MAGIC DSL Lite - Gold Layer (OCSF) Execution
# MAGIC
# MAGIC Built with ❤️ by Databricks Field Engineering & Professional Services
# MAGIC
# MAGIC Copyright © Databricks, Inc.
# MAGIC """

# COMMAND ----------

dbutils.widgets.text("silver_database", "", "1. Silver Database")
dbutils.widgets.text("gold_database", "", "2. Gold Database")
dbutils.widgets.dropdown("continuous", "False", ["True", "False"], "3. Run Continuously")
dbutils.widgets.text("preset_file", "", "4. Preset File")
dbutils.widgets.text("checkpoints_location", "", "5. Checkpoints Location")

# COMMAND ----------

silver_database = dbutils.widgets.get("silver_database")
gold_database = dbutils.widgets.get("gold_database")
preset_file = dbutils.widgets.get("preset_file")
checkpoints_location = dbutils.widgets.get("checkpoints_location")
is_continuous = dbutils.widgets.get("continuous") == "True"

if preset_file == "" or checkpoints_location == "":
    raise Exception("Please fill in: preset_file, checkpoints_location")

# Note: silver_database validation happens after loading config to check if any gold table needs it

# COMMAND ----------

import time
from typing import Dict, Any

from dsl import load_config_file, make_gold_table
from utils import sanitize_string_for_flow_name

# COMMAND ----------

config_data = load_config_file(preset_file)

# COMMAND ----------

# Validate silver_database requirement: only needed if any gold table doesn't use fully qualified input
gold_tables = config_data.get('gold', [])
gold_tables_need_silver_db = False
for tr_conf in gold_tables:
    input_name = tr_conf.get('input', '')
    if not input_name or '.' not in input_name:
        # This gold table doesn't have a fully qualified input, needs silver_database
        gold_tables_need_silver_db = True
        break

if gold_tables_need_silver_db and silver_database == "":
    raise Exception(
        "silver_database is required because at least one gold table doesn't specify a fully qualified 'input' path. "
        "Either add 'input: catalog.database.table' to each gold table in YAML, or provide 'silver_database' parameter."
    )

sl_conf = config_data.get('silver', {})
silver_tables = {}

# Map existing Silver tables from YAML config
# Note: This assumes Silver tables already exist (when skipping Bronze/Silver tasks)
# The YAML must include silver.transform[].name to map table names
# When skipping silver, we map by silver table name (not input field - that's for bronze reference)
for tr_conf in sl_conf.get('transform', []):
    tr_name = tr_conf.get("name") or config_data["name"]
    if silver_database:
        # Construct from silver_database parameter (backward compatible)
        silver_tables[tr_name] = f"{silver_database}.`{tr_name}`"
    else:
        # No silver_database - gold tables must use fully qualified input paths
        # We still add the name to the dict for error message purposes, but it won't be used
        silver_tables[tr_name] = tr_name

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
        .option("checkpointLocation", f"{checkpoints_location}/gold-{tr_name}") \
        .queryName(f"gold-{tr_name}")

    cluster_by = tr_conf.get("clusterBy")
    if cluster_by:
        writer = writer.clusterBy(*cluster_by)
    if not is_continuous:
        writer = writer.trigger(availableNow=True)

    stream = writer.toTable(tbl_name)
    return stream

# COMMAND ----------

for gold_table in config_data.get('gold', []):
    create_gold_table(gold_table)

# COMMAND ----------

if not is_continuous:
    print("Waiting for Gold streams to finish...")
    while len(spark.streams.active):
        time.sleep(5)
else:
    spark.streams.awaitAnyTermination()

