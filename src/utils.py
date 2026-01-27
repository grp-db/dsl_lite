"""
DSL Lite - Utility Functions

Helper functions for table name resolution, secret substitution, and OCSF sink management.
"""

from pyspark.sql import SparkSession

from typing import Optional, Dict, Any
import re

NETWORK_TABLE_NAME = "network_activity"
HTTP_TABLE_NAME = "http_activity"

__catalog_key_name__ = "dsl_lite.{}_catalog_name"
__database_key_name__ = "dsl_lite.{}_database_name"


def get_qualified_table_name(level: str, name: str, spark: Optional[SparkSession] = None) -> str:
    """Generates table name with catalog and database if specified. 

    Args:
        level (str): The level of the table (silver, gold, bronze, ...).
        name (str): The name of the table on the given level.
        spark (Optional[SparkSession], optional): Spark session. Defaults to None.

    Raises:
        Exception: ValueError if database is not specified when catalog is specified.

    Returns:
        str: The fully qualified table name with catalog and database.
    """
    if not spark:
        spark = SparkSession.getActiveSession()
    catalog = spark.conf.get(__catalog_key_name__.format(level), "")
    database = spark.conf.get(__database_key_name__.format(level), "")
    if catalog and not database:
        raise ValueError("Database must be specified if catalog is specified")
    base = ""
    if catalog:
        base += f"`{catalog}`."
    if database:
        base += f"`{database}`."
    return f"{base}`{name}`"


def sanitize_string_for_flow_name(s: str) -> str:
    """Sanitize a string to be used as a flow/function name.
    
    Args:
        s (str): The string to be sanitized.
        
    Returns:
        str: The sanitized string.
    """
    return re.sub(r"[^a-zA-Z0-9]+", "_", s)[-20:].strip("_")


def get_normalized_table_name(name: str, catalog: Optional[str] = None, database: Optional[str] = None, 
                              spark: Optional[SparkSession] = None) -> str:
    """Get the name for normalized (OCSF) table with catalog and database.
    
    Args:
        name (str): The base name of the table.
        catalog (Optional[str], optional): The catalog name. Defaults to None.
        database (Optional[str], optional): The database name. Defaults to None.
        spark (Optional[SparkSession], optional): Spark session. Defaults to None.

    Raises:
        Exception: Exception if catalog or database are not specified.
        
    Returns:
        str: The normalized table name        
    """
    if not spark:
        spark = SparkSession.getActiveSession()
    if not catalog:
        catalog = spark.conf.get(__catalog_key_name__.format("gold"), "")
    if not database:
        database = spark.conf.get(__database_key_name__.format("gold"), "")
    if not catalog or not database:
        raise Exception("Catalog and Database must be specified explicitly or in Spark conf")
    return f"`{catalog}`.`{database}`.`{name}`"


def get_ocsf_sink(name: str, spark: Optional[SparkSession] = None) -> str:
    """Get OCSF sink for gold tables.
    
    Creates a sink to write to OCSF gold tables.
    
    Args:
        name (str): The name of the sink/table.
        spark (Optional[SparkSession], optional): Spark session. Defaults to None.
    
    Returns:
        str: The sink name
    """
    from pyspark import pipelines as sdp
    sink_name = name
    table_name = get_normalized_table_name(name, spark=spark)
    sdp.create_sink(sink_name, "delta", { "tableName": table_name })
    return sink_name

def get_dbutils():
    try:
        from pyspark.dbutils import DBUtils

        return DBUtils(SparkSession.getActiveSession())
    except:
        return None


def get_secret(m) -> str:
    """
    Returns a value stored inside the secret specified in the matching group.
    :param m: regex match object
    :param glbs: dictionary with variables and functions definition (pass `globals()` from the top-level code)
    :return: value of variable if it's defined, or raises an exception if secret doesn't exist
    """
    dbu = get_dbutils()
    if dbu:
        return dbu.secrets.get(m.group(1), m.group(2))
    return f"scope={m.group(1)}, key={m.group(2)}"
    # return f"scope={m.group(1)}, key={m.group(2)}"


# https://docs.microsoft.com/en-us/azure/databricks/security/secrets/secrets#path-value
# {{secrets/scope/key}}
secrets_re = re.compile(r"\{\{secrets/([^/]+)/([^}]+)\}\}")


def substitute_secret(val: str) -> str:
    """
    Perform substitution of secrets inside the given string template. Secrets are specified as
    `{{secrets/secret_scope_name/secret_name}}` (same syntax as in other places inside Databricks).
    Secret value is always returned as a string
    :param val: string with secret definition
    :return: string with substituted secrets
    """
    return secrets_re.sub(get_secret, val)


def substitute_secrets(d: Dict[str, Any]) -> Dict[str, Any]:
    new_dict = {}
    for k, v in d.items():
        if isinstance(v, str):
            nv = substitute_secret(v)
        else:
            nv = v
        new_dict[k] = nv

    return new_dict



