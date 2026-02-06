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

if bronze_database == "" or silver_database == "" or preset_file == "" or checkpoints_location == "":
    raise Exception("Please fill in: bronze_database, silver_database, preset_file, checkpoints_location")

# COMMAND ----------

import time
from typing import Dict, Any

from dsl import load_config_file, make_silver_table
from utils import sanitize_string_for_flow_name

# COMMAND ----------

config_data = load_config_file(preset_file)

# COMMAND ----------

bronze_table_name = f"{bronze_database}.`{config_data.get('bronze', {}).get('name') or config_data['name']}`"
sl_conf = config_data.get('silver', {})

def create_silver_table(tr_conf: Dict[str, Any]):
    tr_name = tr_conf.get("name") or config_data["name"]
    tbl_name = f"{silver_database}.`{tr_name}`"
    df = make_silver_table(bronze_table_name, tr_conf)
    writer = df.writeStream \
        .option("checkpointLocation", f"{checkpoints_location}/silver-{sanitize_string_for_flow_name(tr_name)}") \
        .queryName(f"silver-{tr_name}")

    cluster_by = tr_conf.get("clusterBy", ["time"]),
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

