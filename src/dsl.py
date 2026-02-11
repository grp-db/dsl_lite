"""
DSL Lite - Core Logic

Built with ❤️ by Databricks Field Engineering & Professional Services

Copyright © Databricks, Inc.
"""

from yaml import load, Loader
from pyspark.sql import DataFrame, SparkSession
from typing import Optional, Dict, Any, List, Union
from utils import substitute_secrets


def load_config_file(config_file: str):
    if not config_file:
        raise Exception("No config file name provided")
    with open(config_file, "r") as f:
        config_data = load(f, Loader=Loader)
    if not config_data:
        raise Exception(f"Can't read config file {config_file}" )

    return config_data



default_autoloader_options = {
    # "cloudFiles.useNotifications": "true",
    "cloudFiles.inferColumnTypes": "true",

}

def get_al_opts(fmt: str, al_conf: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    if not al_conf:
        al_conf = {}
    if fmt == "json":
        return {"cloudFiles.format": "json", "multiLine": al_conf.get("multiline", "false")}
    elif fmt == "jsonl":
        return {"cloudFiles.format": "json"}
    return {"cloudFiles.format": fmt}


def read_bronze_stream(config: Dict[str, Any], input: str, add_opts: Optional[dict] = None) -> DataFrame:
    al_conf = config['autoloader']
    al_opts = default_autoloader_options | get_al_opts(al_conf['format'].lower(), al_conf)
    bronze_conf = config.get('bronze', {})
    if bronze_conf.get('loadAsSingleVariant', False):
        al_opts["singleVariantColumn"] = "data"
    clf_opts = {}
    schema = ""
    for k, v in (al_conf.get("cloudFiles") or {}).items():
        if k == "schemaHintsFile":  # TODO: add handling of schemaHintsFile
            continue
        if k == "schema":
            schema = v
        else:
            clf_opts[f"cloudFiles.{k}"] = v
    al_opts = al_opts | clf_opts | (al_conf.get("options", {})) | (add_opts or {})
    al_opts = substitute_secrets(al_opts)
    print(f"Reading from {input} with options {al_opts}")
    reader = SparkSession.getActiveSession().readStream.format("cloudFiles").options(**al_opts)
    if "schema" in al_conf:
        schema = al_conf['schema']
    if schema:
        reader = reader.schema(schema)
    # TODO: add handling of schemaFile
    df = reader.load(input)
    # TODO: copy implementation
    pre_transforms = bronze_conf.get('preTransform', [])
    for pt in pre_transforms:
        df = df.selectExpr(*pt)
    
    df = df.selectExpr("*", "lower(concat(hex(unix_millis(current_timestamp())), substring(replace(uuid(), '-', ''), 0, 13))) as dsl_id")
    return df


def populate_nested(d: Dict[str, Any], parts: List[str], expr: str):
    if len(parts) == 1:
        d[parts[0]] = expr
    else:
        nested = d.get(parts[0], {})
        populate_nested(nested, parts[1:], expr)
        d[parts[0]] = nested


def generate_struct(k: str, v: Union[Dict[str, Any], str]) -> str:
    if isinstance(v, str):
        return f"{v} as `{k}`"
    elif isinstance(v, dict):
        fields = [generate_struct(k, v) for k, v in v.items()]
        return f"struct({', '.join(fields)}) as `{k}`"
    else:
        raise Exception(f"Wrong type for {v}")


def generate_field_exprs(fields: List[Dict[str, Any]]) -> List[str]:
    new_cols = []
    nested = {}
    for f in fields:
        full_name = f['name']
        expr = ""
        if "expr" in f:
            expr = f['expr']
        elif "literal" in f:
            literal = f['literal']
            if isinstance(literal, str):
                expr = f"'{literal}'"
            else:
                expr = literal
        elif "from" in f:
            expr = f['from']
        else:
            raise Exception(f"Invalid field config {f}")

        if '.' in full_name:
            populate_nested(nested, full_name.split('.'), expr)
        else:
            new_cols.append(f"{expr} as `{full_name}`")

    for k, v in nested.items():
        new_cols.append(generate_struct(k, v))

    return new_cols


def strip_backticks(c: str) -> str:
    if c and c[0] == '`' and c[-1] == '`':
        return c[1:-1]
    return c


# TODO: make sure that we handle data in the same order as described in the docs:
# https://docs.sl.antimatter.io/preset-development/notebook-preset-development-tool#232-order-of-operations
def make_silver_table(bronze_table_name: str, tr_conf: Dict[str, Any]) -> DataFrame:
    df = SparkSession.getActiveSession().readStream.option("skipChangeCommits", "true").table(bronze_table_name)
    if "filter" in tr_conf:
        df = df.filter(tr_conf['filter'])

    temporary_fields = tr_conf.get('utils', {}).get('temporaryFields', [])
    if temporary_fields:
        temp_fields = generate_field_exprs(temporary_fields)
        df = df.selectExpr("*", *temp_fields)
    
    unreferenced_cols_conf = tr_conf.get('utils', {}).get('unreferencedColumns', {})
    orig_cols = []
    if unreferenced_cols_conf.get('preserve', False):
        to_omit = unreferenced_cols_conf.get('omitColumns', [])
        if to_omit:
            to_omit = [strip_backticks(c) for c in to_omit]
            orig_cols = [f"`{c}`" for c in df.columns if c not in to_omit]
        else:
            orig_cols = df.columns
    if "dsl_id" not in orig_cols and "`dsl_id`" not in orig_cols:
        orig_cols.append("dsl_id")
    new_fields = generate_field_exprs(tr_conf.get("fields", []))
            
    ndf = df.selectExpr(*orig_cols, *new_fields)

    if temporary_fields:
        temp_fields_names = [t['name'] for t in temporary_fields]
        ndf = ndf.drop(*temp_fields_names)
    
    if "postFilter" in tr_conf:
        ndf = ndf.filter(tr_conf['postFilter'])
    return ndf


def make_gold_table(silver_table_name: str, tr_conf: Dict[str, Any]) -> DataFrame:
    df = SparkSession.getActiveSession().readStream.option("skipChangeCommits", "true").table(silver_table_name)
    if "filter" in tr_conf:
        df = df.filter(tr_conf['filter'])

    new_fields = generate_field_exprs(tr_conf.get("fields", []))
    # print(f"Generating gold table for {tr_name} with fields {new_fields}")
    # Only include dsl_id if it exists in the source DataFrame (for cases where we skip bronze/silver and source table doesn't have it)
    select_exprs = []
    if "dsl_id" in df.columns:
        select_exprs.append("dsl_id")
    select_exprs.extend(new_fields)
    ndf = df.selectExpr(*select_exprs)
    if "postFilter" in tr_conf:
        ndf = ndf.filter(tr_conf['postFilter'])
    
    return ndf
