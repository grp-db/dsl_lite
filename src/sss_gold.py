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

if silver_database == "" or preset_file == "" or checkpoints_location == "":
    raise Exception("Please fill in: silver_database, preset_file, checkpoints_location")

# COMMAND ----------

import time
from typing import Dict, Any

from dsl import load_config_file, make_gold_table
from utils import sanitize_string_for_flow_name

# COMMAND ----------

config_data = load_config_file(preset_file)

# COMMAND ----------

sl_conf = config_data.get('silver', {})
silver_tables = {}

# Map existing Silver tables from YAML config
# Note: This assumes Silver tables already exist (when skipping Bronze/Silver tasks)
# The YAML must include silver.transform[].name to map table names
for tr_conf in sl_conf.get('transform', []):
    tr_name = tr_conf.get("name") or config_data["name"]
    silver_tables[tr_name] = f"{silver_database}.`{tr_name}`"

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
    df = make_gold_table(silver_tables[tr_conf['input']], tr_conf)
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

