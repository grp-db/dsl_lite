# Databricks notebook source
# MAGIC """
# MAGIC DSL Lite - Spark Job Execution
# MAGIC
# MAGIC Built with ❤️ by Databricks Field Engineering & Professional Services
# MAGIC
# MAGIC Copyright © Databricks, Inc.
# MAGIC """

# COMMAND ----------

dbutils.widgets.text("bronze_database", "", "1. Bronze Database")
dbutils.widgets.text("silver_database", "", "2. Silver Database")
dbutils.widgets.text("gold_database", "", "3. Gold Database")
dbutils.widgets.dropdown("continuous", "False", ["True", "False"], "4. Run Continuosly")
dbutils.widgets.text("preset_file", "", "5. Preset File")
dbutils.widgets.text("checkpoints_location", "", "6. Checkpoints location")

# COMMAND ----------

bronze_database = dbutils.widgets.get("bronze_database")
silver_database = dbutils.widgets.get("silver_database")
gold_database = dbutils.widgets.get("gold_database")
preset_file = dbutils.widgets.get("preset_file")
checkpoints_location = dbutils.widgets.get("checkpoints_location")
is_continuous = dbutils.widgets.get("continuous") == "True"
if bronze_database == "" or silver_database == "" or gold_database == "" or preset_file == "" or checkpoints_location == "":
    raise Exception("Please fill in all required fields")

# COMMAND ----------

import time

import pyspark.sql.functions as F
from pyspark.sql.types import StringType
from pyspark.sql import DataFrame, SparkSession, Column
from typing import Optional, Dict, Any, List, Union

from dsl import load_config_file, read_bronze_stream, make_silver_table, make_gold_table
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

    # TODO: check if the table already exists, and if not, then wait until the first stream is finished...
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
    # TODO: in continuos mode, wait until bronze table is created and then start silver
    # Technically, it will be not necessary if it will be implemented in the `start_bronze_flow`
    pass

# COMMAND ----------

sl_conf = config_data.get('silver', {})
silver_tables = {}

# COMMAND ----------

def create_silver_table(tr_conf: Dict[str, Any]):
    tr_name = tr_conf.get("name") or config_data["name"]
    tbl_name = f"{silver_database}.`{tr_name}`"
    silver_tables[tr_name] = tbl_name
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
    # TODO: in continuos mode, wait until each silver table is created and then start gold processing
    pass

# COMMAND ----------

def create_gold_table(tr_conf: Dict[str, Any]):
    tr_name = tr_conf["name"]
    tbl_name = f"{gold_database}.`{tr_name}`"
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
