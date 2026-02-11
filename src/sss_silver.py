# Databricks notebook source
# MAGIC """
# MAGIC DSL Lite - Silver Layer Execution
# MAGIC
# MAGIC Built with ❤️ by Databricks Field Engineering & Professional Services
# MAGIC
# MAGIC Copyright © Databricks, Inc.
# MAGIC """

# COMMAND ----------

dbutils.widgets.text("bronze_database", "", "1. Bronze Database")
dbutils.widgets.text("silver_database", "", "2. Silver Database")
dbutils.widgets.dropdown("continuous", "False", ["True", "False"], "3. Run Continuously")
dbutils.widgets.text("preset_file", "", "4. Preset File")
dbutils.widgets.text("checkpoints_location", "", "5. Checkpoints Location")

# COMMAND ----------

bronze_database = dbutils.widgets.get("bronze_database")
silver_database = dbutils.widgets.get("silver_database")
preset_file = dbutils.widgets.get("preset_file")
checkpoints_location = dbutils.widgets.get("checkpoints_location")
is_continuous = dbutils.widgets.get("continuous") == "True"

if preset_file == "" or checkpoints_location == "":
    raise Exception("Please fill in: preset_file, checkpoints_location")

if silver_database == "":
    raise Exception("Please fill in: silver_database")

# Note: bronze_database validation happens after loading config to check if any silver table needs it

# COMMAND ----------

import time
from typing import Dict, Any

from dsl import load_config_file, make_silver_table
from utils import sanitize_string_for_flow_name

# COMMAND ----------

config_data = load_config_file(preset_file)

# COMMAND ----------

# Validate bronze_database requirement: only needed if any silver table doesn't use fully qualified input
sl_conf = config_data.get('silver', {})
silver_tables_need_bronze_db = False
for tr_conf in sl_conf.get('transform', []):
    input_table = tr_conf.get("input")
    if not input_table or '.' not in input_table:
        # This silver table doesn't have a fully qualified input, needs bronze_database
        silver_tables_need_bronze_db = True
        break

if silver_tables_need_bronze_db and bronze_database == "":
    raise Exception(
        "bronze_database is required because at least one silver table doesn't specify a fully qualified 'input' path. "
        "Either add 'input: catalog.database.table' to each silver table in YAML, or provide 'bronze_database' parameter."
    )

bronze_table_name = f"{bronze_database}.`{config_data.get('bronze', {}).get('name') or config_data['name']}`" if bronze_database else None

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
        .queryName(f"silver-{tr_name}")

    cluster_by = tr_conf.get("clusterBy", ["time"])
    if cluster_by:
        writer = writer.clusterBy(*cluster_by)
    if not is_continuous:
        writer = writer.trigger(availableNow=True)

    stream = writer.toTable(tbl_name)
    return stream

# COMMAND ----------

for tr_conf in sl_conf.get('transform', []):
    create_silver_table(tr_conf)

# COMMAND ----------

if not is_continuous:
    print("Waiting for Silver streams to finish...")
    while len(spark.streams.active):
        time.sleep(5)
else:
    spark.streams.awaitAnyTermination()

