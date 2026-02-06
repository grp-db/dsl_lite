# Databricks notebook source
# MAGIC """
# MAGIC DSL Lite - Bronze Layer Execution
# MAGIC
# MAGIC Built with ❤️ by Databricks Field Engineering & Professional Services
# MAGIC
# MAGIC Copyright © Databricks, Inc.
# MAGIC """

# COMMAND ----------

dbutils.widgets.text("bronze_database", "", "1. Bronze Database")
dbutils.widgets.dropdown("continuous", "False", ["True", "False"], "2. Run Continuously")
dbutils.widgets.text("preset_file", "", "3. Preset File")
dbutils.widgets.text("checkpoints_location", "", "4. Checkpoints Location")

# COMMAND ----------

bronze_database = dbutils.widgets.get("bronze_database")
preset_file = dbutils.widgets.get("preset_file")
checkpoints_location = dbutils.widgets.get("checkpoints_location")
is_continuous = dbutils.widgets.get("continuous") == "True"

if bronze_database == "" or preset_file == "" or checkpoints_location == "":
    raise Exception("Please fill in: bronze_database, preset_file, checkpoints_location")

# COMMAND ----------

import time
from typing import Optional, Dict, Any

from dsl import load_config_file, read_bronze_stream
from utils import sanitize_string_for_flow_name

# COMMAND ----------

config_data = load_config_file(preset_file)

# COMMAND ----------

bronze_table_name = f"{bronze_database}.`{config_data.get('bronze', {}).get('name') or config_data['name']}`"
print(f"Creating bronze table {bronze_table_name}")

bronze_cluster_by = config_data.get('bronze', {}).get("clusterBy", ["time"])

def start_bronze_flow(input: str, add_opts: Optional[dict] = None):
    df = read_bronze_stream(config_data, input, add_opts)
    writer = df.writeStream \
        .option("checkpointLocation", f"{checkpoints_location}/bronze-{sanitize_string_for_flow_name(input)}") \
        .queryName(f"bronze-{input}")

    if bronze_cluster_by:
        writer = writer.clusterBy(*bronze_cluster_by)
    if not is_continuous:
        writer = writer.trigger(availableNow=True)

    stream = writer.toTable(bronze_table_name)
    return stream

# Load data from specified locations
for inp in config_data['autoloader']['inputs']:
    start_bronze_flow(inp)

# COMMAND ----------

if not is_continuous:
    print("Waiting for Bronze streams to finish...")
    while len(spark.streams.active):
        time.sleep(5)
else:
    spark.streams.awaitAnyTermination()

