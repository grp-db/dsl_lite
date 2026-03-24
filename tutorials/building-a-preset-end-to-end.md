# Building a Preset End-to-End: From Raw Logs to OCSF Pipeline

This tutorial walks through the full development workflow for a new DSL Lite preset —
from raw sample logs to a validated, production-ready SDP or SSS pipeline.

---

## Prerequisites

- Databricks workspace with Unity Catalog enabled
- `src/` directory uploaded to your workspace (e.g. `/Workspace/Users/<you>/dsl_lite/src/`)
- `notebooks/explorer/` uploaded to your workspace
- A sample log file accessible from Databricks (Volumes, DBFS, or workspace files)
- Gold OCSF tables created via `notebooks/ddl/create_ocsf_tables.py`

---

## Step 1: Get Sample Logs

Place a small representative sample of your log file somewhere accessible in Databricks:

```
/Volumes/<catalog>/<schema>/raw_logs/<source>/<sourcetype>/sample.log
```

DSL Lite ships with examples under `raw_logs/` (Cisco IOS, Zeek, Cloudflare, GitHub, AWS)
that you can use as reference while building your own.

---

## Step 2: Create a Starter Preset YAML

Start from an existing template in `ocsf_templates/` that matches your log format and OCSF
event class, or copy the closest pipeline preset from `pipelines/`.

Create a folder for your new source:

```
pipelines/
  <source>/
    <sourcetype>/
      preset.yaml
```

A minimal preset looks like this:

```yaml
name: my_source_type
description: "My Source logs"

autoloader:
  inputs:
    - /Volumes/<catalog>/<schema>/raw_logs/my_source/my_type/
  format: text   # text | json | jsonl | csv | parquet

bronze:
  name: my_source_type_bronze
  preTransform:
    -
      - "*"
      - "_metadata.file_path"
      - CAST(NULL AS TIMESTAMP) as time    # TODO: extract real timestamp
      - CAST('my_source' AS STRING) as source
      - CAST('my_type' AS STRING) as sourcetype
      - CURRENT_TIMESTAMP() as processed_time

silver:
  transform:
    - name: my_source_type_silver
      utils:
        unreferencedColumns:
          preserve: true
      fields:
        - name: event_field
          expr: "value"   # TODO: parse fields from raw log

gold:
  - name: network_activity   # or whichever OCSF class fits
    input: my_source_type_silver
    fields:
      - name: time
        from: time
      - name: metadata.version
        literal: "1.7.0"
      - name: metadata.log_provider
        from: source
      - name: metadata.log_name
        from: sourcetype
      - name: metadata.log_version
        literal: "my_source@my_type:version@1.0"
      - name: metadata.processed_time
        expr: CURRENT_TIMESTAMP()
```

> See `docs/dsl_lite_features/architecture.md` for the full metadata field reference and
> `docs/ocsf_event_categories/` for OCSF class schemas by category.

---

## Step 3: Run the Explorer Notebook

Open `notebooks/explorer/preset_explorer` in Databricks and set the widgets:

| Widget | Value |
|--------|-------|
| `preset_file` | `/Workspace/Users/<you>/dsl_lite/pipelines/<source>/<type>/preset.yaml` |
| `sample_data_path` | `/Volumes/.../sample.log` (or leave blank to use `autoloader.inputs[0]`) |
| `display_limit` | `50` (increase if you need more rows to validate edge cases) |

Click **Run All**. The notebook executes three sections:

### Bronze output
Verify the raw data is being read correctly and your metadata fields (`time`, `source`,
`sourcetype`, `processed_time`) are populated. Common issues:
- `time` is `null` → fix your timestamp regex or cast expression in `preTransform`
- `_metadata.file_path` is empty → normal if reading a single file directly rather than a folder

### Silver output
Verify your parsed fields are extracted correctly. Common issues:
- Fields are empty strings → adjust your `REGEXP_EXTRACT` pattern or JSON path
- Fields are present but wrong type → add an explicit `CAST(... AS <type>)` in the `expr`

### Gold output
Verify the OCSF struct is populated correctly. Common issues:
- `metadata` struct fields are null → check that `source`/`sourcetype` flowed through from bronze
- Nested struct fields (e.g. `src_endpoint.ip`) are missing → check the dot-notation field name in your YAML
- Filter is too aggressive → temporarily comment out the `filter:` line and re-run to see all rows

---

## Step 4: Iterate on the YAML

The typical iteration loop:

1. Edit `preset.yaml` in your IDE or Databricks editor
2. Switch back to `preset_explorer` and re-run **only the affected cell** (Bronze, Silver, or Gold)
3. Verify the output looks correct
4. Repeat until all three layers produce the expected schema and values

> **Tip:** Use `display_limit: 200+` when validating edge cases like multiline logs,
> null fields, or rare event types. The gold filter is applied per-table, so set it
> to something broad while iterating and tighten it later.

---

## Step 5: Deploy as a Pipeline

Once the explorer output looks correct, deploy to production:

### SDP (Spark Declarative Pipeline)

1. Create a Lakeflow Spark Declarative Pipeline in Databricks
2. Set the entry point to `src/sdp_medallion.py`
3. Add the configuration:

```json
{
  "configuration": {
    "dsl_lite.bronze_database_name": "bronze",
    "dsl_lite.silver_database_name": "silver",
    "dsl_lite.gold_database_name": "gold",
    "dsl_lite.gold_catalog_name": "<your_catalog>",
    "dsl_lite.config_file": "/Workspace/Users/<you>/dsl_lite/pipelines/<source>/<type>/preset.yaml"
  }
}
```

4. Run the pipeline — bronze → silver → gold will execute in order

### SSS (Spark Structured Streaming Job)

1. Create a Databricks Job with a single task pointing to `src/sss_medallion.py`
2. Set the task parameters:

```json
{
  "bronze_database": "<catalog>.bronze",
  "silver_database": "<catalog>.silver",
  "gold_database": "<catalog>.gold",
  "preset_file": "/Workspace/Users/<you>/dsl_lite/pipelines/<source>/<type>/preset.yaml",
  "checkpoints_location": "/Volumes/<catalog>/<schema>/checkpoints",
  "continuous": "False"
}
```

3. Run the job

> For Gold Only, skipping layers, checkpoint resets, and other advanced scenarios
> see [docs/dsl_lite_features/advanced-configuration.md](../docs/dsl_lite_features/advanced-configuration.md).

---

## Tips

- **Start with silver `preserve: true`** — setting `unreferencedColumns.preserve: true` in silver keeps all bronze columns available in gold, making it easier to reference fields while building your mapping. Remove it once the mapping is finalized.
- **Use `raw_logs/` samples** — the included sample files are small enough to iterate quickly and cover real-world log formats.
- **Validate OCSF structs** — in the gold display output, click the expand arrow on a `metadata`, `src_endpoint`, or `connection_info` cell to inspect nested struct values directly.
- **`metadata.log_version` matters** — set it from the start (e.g. `my_source@my_type:version@1.0`). When you make breaking changes to the mapping later, incrementing this version enables targeted record cleanup. See [checkpoint resets](../docs/dsl_lite_features/advanced-configuration.md#checkpoint-resets-in-sdp-spark-declarative-pipeline).
