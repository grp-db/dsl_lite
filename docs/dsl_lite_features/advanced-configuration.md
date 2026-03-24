# DSL Lite — Advanced Configuration

---

## Skipping Bronze/Silver Layers

### With Multi-Task Jobs (SSS)

Skipping layers is done by **not including those tasks** in your job configuration:

**To Skip Bronze:**
- Remove the Bronze task from your job
- Silver task will read from existing Bronze tables (ensure `bronze_database` parameter points to existing tables)

**To Skip Silver:**
- Remove the Silver task from your job
- Gold task automatically maps existing Silver tables from YAML config (no changes needed)
- Ensure Silver tables exist and match the names in `silver.transform[].name` in your YAML

**To Skip Both Bronze and Silver (Gold Only):**
- Only include the Gold task in your job
- Gold task will use existing Silver tables (mapped from YAML)

```json
{
  "name": "DSL Lite Gold Only",
  "tasks": [
    {
      "task_key": "gold",
      "notebook_task": {
        "notebook_path": "/Workspace/Users/user@email.com/dsl_lite/src/sss_gold",
        "base_parameters": {
          "silver_database": "dsl_lite.cisco",
          "preset_file": "/Workspace/Users/user@email.com/dsl_lite/pipelines/cisco/ios/preset.yaml",
          "checkpoints_location": "/Volumes/dsl_lite/checkpoints/gold",
          "continuous": "False"
        }
      }
    }
  ]
}
```

> **Note:** `gold_database` is omitted because all gold tables specify their own `catalog` and `database` in the YAML. If any table omits these, you must provide `gold_database` as a fallback.

**Note:** The `sss_gold.py` notebook automatically maps existing Silver tables from your YAML's `silver.transform[].name` section, so no additional configuration is needed when skipping Silver.

### With Single-Task Medallion Job (SSS)

Skipping layers is done using the `skip_bronze` and `skip_silver` parameters:

**To Skip Bronze:**
- Set `skip_bronze: "True"` in job parameters
- Silver layer will read from existing Bronze tables (ensure `bronze_database` parameter points to existing tables)

**To Skip Silver:**
- Set `skip_silver: "True"` in job parameters
- Gold layer automatically maps existing Silver tables from YAML config
- Ensure Silver tables exist and match the names in `silver.transform[].name` in your YAML

**To Skip Both Bronze and Silver (Gold Only):**

```json
{
  "name": "DSL Lite Gold Only (Medallion)",
  "tasks": [
    {
      "task_key": "medallion",
      "notebook_task": {
        "notebook_path": "/Workspace/Users/user@email.com/dsl_lite/src/sss_medallion",
        "base_parameters": {
          "bronze_database": "dsl_lite.cisco",
          "silver_database": "dsl_lite.cisco",
          "gold_database": "dsl_lite.ocsf",
          "skip_bronze": "True",
          "skip_silver": "True",
          "preset_file": "/Workspace/Users/user@email.com/dsl_lite/pipelines/cisco/ios/preset.yaml",
          "checkpoints_location": "/Volumes/dsl_lite/checkpoints",
          "continuous": "False"
        }
      }
    }
  ]
}
```

### With SDP (Spark Declarative Pipeline)

```json
{
  "configuration": {
    "dsl_lite.silver_database_name": "silver",
    "dsl_lite.config_file": "/Workspace/Users/user@email.com/dsl_lite/pipelines/cisco/ios/preset.yaml",
    "dsl_lite.skip_bronze": "true",
    "dsl_lite.skip_silver": "true"
  }
}
```

> **Note:** `dsl_lite.gold_database_name` is omitted because all gold tables specify their own `catalog` and `database` in the YAML. If any table omits these, you must provide `dsl_lite.gold_database_name` (and optionally `dsl_lite.gold_catalog_name`) as defaults.

---

## Per-Table Catalog/Database Configuration

Both SDP and Spark Job modes support per-table catalog and database configuration in the YAML preset file. This allows you to route different OCSF tables to different catalogs/databases.

**Two Approaches for Flexibility:**

1. **Using Config Parameters** (Recommended for most cases):
   - Specify `bronze_database`, `silver_database`, `gold_database` parameters (or `dsl_lite.*_database_name` for SDP)
   - Tables are constructed from these parameters + table names from YAML
   - Simple and portable across environments

2. **Using Fully Qualified Table Paths** (For advanced scenarios):
   - Specify fully qualified table names directly in YAML `input` fields: `catalog.database.table` or `database.table`
   - No need for database parameters when all tables use fully qualified paths
   - Useful for referencing tables from different catalogs/databases or outside the current pipeline

**Example: Per-Table Catalog/Database in YAML**

```yaml
gold:
  # Table 1: Uses per-table catalog/database
  - name: network_activity
    input: zeek_conn_silver
    catalog: my_catalog_1      # Optional: per-table catalog
    database: my_database_1    # Optional: per-table database
    fields:
      - name: activity_id
        expr: "CASE WHEN conn_state = 'SF' THEN 2 ELSE 6 END"
      # ... other fields ...

  # Table 2: Falls back to global config (gold_database / dsl_lite.gold_database_name)
  - name: dns_activity
    input: zeek_conn_silver
    # No catalog/database specified - uses global defaults
    fields:
      - name: query.hostname
        from: query_name
      # ... other fields ...
```

**Fully Qualified Table Paths:**
- Silver tables can specify `input: catalog.database.table` to reference bronze tables with fully qualified paths
- Gold tables can specify `input: catalog.database.table` to reference silver tables with fully qualified paths
- **Important Distinction:**
  - **YAML `input` fields:** Specify **where to read from** (source tables)
  - **Job/Notebook parameters (`bronze_database`, `silver_database`):** Specify **where to write to** (output tables)
  - **YAML `catalog`/`database` fields (Gold only):** Specify **where to write to** (output tables) — only supported for Gold tables
- **When creating tables** (not skipping), you still need database **parameters** to specify where to write output tables
- **When skipping layers**, database parameters can be omitted if all tables use fully qualified `input` paths
- **Bronze and Silver tables** don't support `catalog`/`database` fields in YAML (unlike Gold tables) — you must use parameters

**How it works:**
- **For Gold Tables:**
  - **Input (where to read from):** If `input` contains a dot (`.`) → treated as fully qualified name, used directly. If `input` has no dot → looked up in `silver_tables` dictionary (constructed from `silver_database` parameter)
  - **Output (where to write to):** If `catalog` and/or `database` are specified in YAML → uses those values. If omitted → falls back to `gold_database` parameter

- **For Silver Tables:**
  - **Input (where to read from):** If `input` is specified and contains a dot (`.`) → treated as fully qualified bronze table name. If `input` is omitted or has no dot → uses default `bronze_table_name` (constructed from `bronze_database` parameter)
  - **Output (where to write to):** Always uses `silver_database` **job parameter** — Silver doesn't support `catalog`/`database` fields in YAML

- **For Bronze Tables:**
  - **Output (where to write to):** Always uses `bronze_database` **job parameter** — Bronze doesn't support `catalog`/`database` fields in YAML

---

## Fully Qualified Table Paths

> **Note:** Fully qualified paths are most useful when **skipping layers**. When creating all layers, you still need database parameters to specify where to write tables.

### Approach 1: Using Simple Input Names (with Database Parameters)

**YAML (`preset.yaml`):**
```yaml
name: cisco_ios
description: "Cisco IOS logs"

autoloader:
  inputs:
    - /Volumes/logs/cisco/ios/
  format: text

bronze:
  name: cisco_ios_bronze
  preTransform:
    - ["*", "TO_TIMESTAMP(...) as time"]

silver:
  transform:
    - name: cisco_ios_silver
      # No input field - uses bronze_database parameter
      fields:
        - name: timestamp
          expr: "..."

gold:
  - name: authentication
    input: cisco_ios_silver  # Simple name - uses silver_database parameter
    filter: facility IN ('AAA', 'SEC_LOGIN')
    fields:
      - name: time
        expr: CAST(timestamp AS TIMESTAMP)
```

**Job Parameters (SSS Medallion):**
```json
{
  "bronze_database": "bronze_db",
  "silver_database": "silver_db",
  "gold_database": "gold_db",
  "preset_file": "/path/to/preset.yaml",
  "checkpoints_location": "/Volumes/checkpoints",
  "skip_bronze": "False",
  "skip_silver": "False"
}
```

**Resulting Tables:**
- Bronze: `bronze_db.cisco_ios_bronze`
- Silver: `silver_db.cisco_ios_silver` (reads from `bronze_db.cisco_ios_bronze`)
- Gold: `gold_db.authentication` (reads from `silver_db.cisco_ios_silver`)

---

### Approach 2: Using Fully Qualified Paths (Best for Skipping Layers)

**Use Case 1: Skipping Bronze, Creating Silver (Cross-Database Read)**

**YAML (`preset.yaml`):**
```yaml
name: cisco_ios
description: "Cisco IOS logs"

# No autoloader or bronze sections needed (skipping bronze)

silver:
  transform:
    - name: cisco_ios_silver
      input: prod_catalog.raw_db.cisco_ios_bronze  # Read from existing bronze in different database
      fields:
        - name: timestamp
          expr: "..."

gold:
  - name: authentication
    input: cisco_ios_silver  # Simple name - uses silver_database parameter
    catalog: prod_catalog
    database: gold_db
    filter: facility IN ('AAA', 'SEC_LOGIN')
    fields:
      - name: time
        expr: CAST(timestamp AS TIMESTAMP)
```

**Job Parameters (SSS Medallion):**
```json
{
  "silver_database": "prod_catalog.enriched_db",
  "preset_file": "/path/to/preset.yaml",
  "checkpoints_location": "/Volumes/checkpoints",
  "skip_bronze": "True",
  "skip_silver": "False"
}
```

**Result:** Silver reads from `prod_catalog.raw_db.cisco_ios_bronze` (existing) but writes to `prod_catalog.enriched_db.cisco_ios_silver` (new table).

---

**Use Case 2: Gold Only — No Database Parameters Needed**

**YAML (`preset.yaml`):**
```yaml
name: cisco_ios
description: "Cisco IOS logs"

gold:
  - name: authentication
    input: prod_catalog.enriched_db.cisco_ios_silver  # Fully qualified path (source table)
    catalog: prod_catalog  # Target catalog where gold table will be written
    database: gold_db      # Target database where gold table will be written
    filter: facility IN ('AAA', 'SEC_LOGIN')
    fields:
      - name: time
        expr: CAST(timestamp AS TIMESTAMP)
```

**Job Parameters (SSS Medallion):**
```json
{
  "preset_file": "/path/to/preset.yaml",
  "checkpoints_location": "/Volumes/checkpoints",
  "skip_bronze": "True",
  "skip_silver": "True"
}
```

---

### Configuration Requirements

**For SSS Mode:**
- `gold_database` parameter is **optional** — only required if any table omits `database` in YAML (used as fallback)
- If **all** tables specify `database` in YAML → you can **omit** `gold_database` parameter
- If **any** table omits `database` in YAML → you **must** provide `gold_database` parameter as fallback
- Per-table `database` in YAML overrides the `gold_database` parameter
- Per-table `catalog` in YAML is optional (if omitted, table uses database only, no catalog)

**For SDP Mode:**
- If **all** tables specify both `catalog` and `database` in YAML → you can **omit** `dsl_lite.gold_database_name` and `dsl_lite.gold_catalog_name` from config
- If **any** table omits `catalog` or `database` in YAML → you **must** provide `dsl_lite.gold_database_name` (and optionally `dsl_lite.gold_catalog_name`) as defaults
- SDP requires both catalog and database to be specified (either per-table in YAML or via Spark conf defaults)

---

## Checkpoint Resets in SDP (Spark Declarative Pipeline)

When schema changes or OCSF mapping updates require reprocessing data through a gold table, you may need to reset the checkpoint for specific streaming flows in SDP. Databricks supports **selective checkpoint resets** via the pipeline update API, allowing you to clear checkpoints for individual flows without restarting the entire pipeline.

> **Reference**: [Start a pipeline update to clear selective streaming flows checkpoints](https://docs.databricks.com/aws/en/ldp/updates#start-a-pipeline-update-to-clear-selective-streaming-flows-checkpoints)

### How to Reset a Checkpoint for a Specific Flow

Use the Databricks Pipelines REST API to trigger a selective checkpoint reset, specifying the **fully qualified table path** of the flow to reset:

```bash
curl -X POST \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "reset_checkpoint_selection": ["<catalog.schema.table>"]
  }' \
  https://<your-workspace>.cloud.databricks.com/api/2.0/pipelines/<your-pipeline-id>/updates
```

**Example** — resetting the checkpoint for a `network_activity` gold table:

```bash
curl -X POST \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "reset_checkpoint_selection": ["my_catalog.gold.network_activity"]
  }' \
  https://my-workspace.cloud.databricks.com/api/2.0/pipelines/abc123/updates
```

This tells SDP to clear only that flow's checkpoint and replay data from the beginning of the silver table. All other flows in the pipeline continue from their existing checkpoints.

### Post-Checkpoint Reset: Deleting Stale Records from Gold Tables

After resetting a checkpoint, the gold table will be repopulated from the beginning of the silver stream. If the previous run wrote records with an older schema version (tracked via `metadata.log_version`), delete those stale records before triggering the checkpoint reset to avoid duplicates.

Use a targeted `DELETE` statement scoped by `metadata.log_provider`, `metadata.log_name`, and `metadata.log_version` to remove only the records from the affected source and schema version:

```sql
-- Delete stale records from a gold table for a specific source and schema version
DELETE FROM catalog.db.table
WHERE metadata.log_provider = '<source>'
  AND metadata.log_name = '<sourcetype>'
  AND metadata.log_version = '<source>@<sourcetype>:version@<version>';
```

**Example** — removing old Zeek connection records before replaying with an updated schema:

```sql
DELETE FROM my_catalog.gold.network_activity
WHERE metadata.log_provider = 'zeek'
  AND metadata.log_name = 'conn'
  AND metadata.log_version = 'zeek@conn:version@1.0';
```

After deletion, trigger the SDP pipeline update with `reset_checkpoint_selection` to replay and repopulate with the new schema version (e.g., `zeek@conn:version@1.1`).

> **Note**: Before resetting the checkpoint, manually increment the `metadata.log_version` value in your gold preset YAML (e.g., `zeek@conn:version@1.0` → `zeek@conn:version@1.1`). This ensures all reprocessed rows are written with the new version tag, making them distinguishable from any previously ingested records and enabling targeted deletes or audits in the future.

### Workflow Summary

**SDP (Spark Declarative Pipeline):**

1. **Increment** `metadata.log_version` in your preset YAML (e.g., `1.0` → `1.1`) to tag reprocessed rows with a new version
2. **Update** any other OCSF field mappings in the preset as needed
3. **Delete** stale records from the gold table scoped to the old `metadata.log_version`
4. **Reset** the checkpoint for the specific flow using `reset_checkpoint_selection`
5. **Run** the pipeline — the flow replays from the beginning and writes records tagged with the new schema version

**SSS (Spark Structured Streaming):**

Unlike SDP, SSS does not have a built-in API for selective checkpoint resets. The checkpoint directory must be **manually deleted** before restarting the job.

1. **Increment** `metadata.log_version` in your preset YAML (e.g., `1.0` → `1.1`)
2. **Update** any other OCSF field mappings in the preset as needed
3. **Delete** stale records from the gold table scoped to the old `metadata.log_version`
4. **Delete** the checkpoint directory for the affected stream — either via `dbutils` or the Databricks UI (DBFS/Volumes browser):

```python
# Delete checkpoint for a specific gold stream via dbutils
dbutils.fs.rm("/Volumes/dsl_lite/checkpoints/gold-network_activity", recurse=True)
```

5. **Restart** the job — the stream replays from the beginning and writes records tagged with the new schema version

> **Note**: The checkpoint path follows the pattern `{checkpoints_location}/gold-{table_name}` as configured in the job parameters.
