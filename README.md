# DSL Lite - Lightweight Cybersecurity Data Pipeline Framework

> **🏗️ Databricks Cybersecurity Accelerator**  
> Built by Databricks Field Engineering & Professional Services

## Overview

**DSL Lite** is a reusable cybersecurity accelerator designed for building end-to-end cyber lakehouse architectures using an augmented medallion approach with [OCSF (Open Cybersecurity Schema Framework)](https://schema.ocsf.io/) compliance.

This lightweight, self-deployable framework uses configuration files called "presets" to transform security logs into bronze, silver, and gold layers with OCSF-compliant schemas. It's designed for customers building complex cybersecurity projects and use cases that require:
- **Scalable data ingestion** from multiple security log sources
- **Standardized schema transformation** to OCSF data models
- **Flexible deployment** in self-managed or restricted environments
- **Production-ready pipelines** with minimal configuration

### About This Accelerator

This accelerator was developed by the **Databricks Field Engineering and Professional Services teams** to enable customers to rapidly deploy enterprise-grade cybersecurity data pipelines. While Databricks owns the intellectual property, this accelerator is made publicly available to support the broader security community in building robust cyber lakehouse architectures on the Databricks platform.

---

## 📑 Table of Contents

- [Overview](#overview)
- [Cyber Medallion Architecture](#cyber-medallion-architecture-best-practices)
  - [Layer-by-Layer Architecture](#layer-by-layer-architecture)
  - [Data Flow Examples](#data-flow-examples-by-format)
  - [OCSF Metadata Mapping](#ocsf-metadata-field-mapping)
  - [Performance Optimization](#performance-optimization-guidelines)
- [Project Structure](#project-structure)
- [Getting Started](#how-to-use)
  - [Spark Declarative Pipeline (SDP)](#execute-as-spark-declarative-pipeline-sdp)
  - [Spark Structured Streaming (SSS)](#execute-as-spark-structured-streaming-sss-job)
- [Advanced Configuration](#advanced-configuration)
  - [Skipping Layers](#skipping-bronzesilver-layers)
  - [Per-Table Catalog/Database](#per-table-catalogdatabase-configuration)
  - [Fully Qualified Table Paths](#end-to-end-comparison-simple-input-names-vs-fully-qualified-paths)
  - [Lookup Joins](#lookup-joins)
- [Development & Testing Tool](#development--testing-tool)
- [Key Features](#key-features)
- [Supported Data Sources](#supported-data-sources)
- [License & Attribution](#license--attribution)

---

## Cyber Medallion Architecture Best Practices

DSL Lite implements a three-layer medallion architecture optimized for cybersecurity data pipelines. Each layer serves a specific purpose in the data transformation journey from raw logs to OCSF-compliant analytics-ready tables.

### Common Input Formats

- **JSON / JSON Lines**: Semi-structured events with nested fields
- **CSV**: With headers (Auto Loader CSV format) or without headers (text format with `from_csv` in Silver)
- **Syslog**: RFC 3164/5424 text-based log messages

### Layer-by-Layer Architecture

| Layer | Step | Description | Schema Example | Output | Performance |
|-------|------|-------------|----------------|--------|-------------|
| **Bronze** | **Ingest & Amend** | Raw data ingestion with minimal transformation. Preserves original data in `data` (VARIANT for JSON, STRUCT for CSV with headers) or `value` (STRING for syslog/text/CSV without headers). Spark SQL adds metadata tags for downstream processing. | `data VARIANT/STRUCT` **OR** `value STRING`<br/><br/>**+ 7 Spark SQL metadata fields:**<br/>`time TIMESTAMP` *(required)*<br/>`date DATE` *(optional)*<br/>`host STRING` *(optional, if applicable)*<br/>`source STRING` *(recommended)*<br/>`sourcetype STRING` *(recommended)*<br/>`processed_time TIMESTAMP` *(recommended)*<br/>`file_path STRING` *(recommended)*<br/><br/>**+ DSL Lite ID:**<br/>`dsl_id STRING` (unique identifier) | **Delta Table (Streaming)**<br/>- Auto Loader for incremental ingestion<br/>- Supports schema evolution<br/>- Raw data preservation | `CLUSTER BY (time)`<br/><br/>Optimizes time-based queries and improves compression |
| **Silver** | **Parse & Structure** | Flattens nested JSON from `data` field, extracts structured fields from `value` using regex patterns, or parses CSV with `from_csv()`. Converts unstructured logs into typed, queryable columns. Applies business logic, filters, and temporary fields. | **JSON:** Extracted from `data` VARIANT<br/>`source_ip STRING`<br/>`dest_ip STRING`<br/>`port INT`<br/>`protocol STRING`<br/>`action STRING`<br/>`bytes_in BIGINT`<br/>`bytes_out BIGINT`<br/>`duration DOUBLE`<br/>`user STRING`<br/><br/>**Syslog:** Extracted from `value` STRING<br/>`severity STRING`<br/>`facility STRING`<br/>`process STRING`<br/>`pid INT`<br/>`message STRING`<br/><br/>**+ 7 Spark SQL metadata fields**<br/>**+ DSL Lite ID:** `dsl_id STRING` | **Delta Table (Streaming)**<br/>- Typed columns for efficient queries<br/>- Filtered and cleansed data<br/>- Vendor-specific schema | `CLUSTER BY (time)`<br/><br/>Maintains time-based optimization for log analytics |
| **Gold** | **Map & Normalize** | Maps silver tables to OCSF-compliant schemas. Standardizes field names, data types, and structures across vendors. Includes OCSF `metadata` STRUCT with versioning and lineage tracking. Creates analytics-ready tables for security operations, threat hunting, and compliance reporting. | `activity_id INT`<br/>`activity_name STRING`<br/>`time TIMESTAMP`<br/>`src_endpoint STRUCT<...>`<br/>`dst_endpoint STRUCT<...>`<br/>`connection_info STRUCT<...>`<br/>`metadata STRUCT<...>`<br/>`observables ARRAY<STRUCT<...>>`<br/>`enrichments ARRAY<STRUCT<...>>`<br/>`severity STRING`<br/>`severity_id INT`<br/>`dsl_id STRING` | **Delta Table (Sink)**<br/>- OCSF-compliant schema<br/>- Cross-vendor normalization<br/>- Analytics-ready<br/>- Metadata tracking | `CLUSTER BY (time)`<br/><br/>Enables fast time-range queries for security investigations |

> **Note on Gold Layer Delta Sinks**: In Spark Declarative Pipeline (SDP) mode, gold tables must be Delta Sinks (not streaming tables) because multiple streams from different pipelines write to the same OCSF-compliant gold tables. Since SDP streaming tables are linked to each individual pipeline, Delta Sinks are required to support concurrent writes from multiple pipeline streams, enabling cross-vendor data aggregation in unified OCSF tables.

### Example Pipeline Outputs

The following table shows the bronze, silver, and gold table outputs for the example pipelines included in DSL Lite:

| Pipeline | Bronze (Ingest/Amend) | Silver (Parse/Structure) | Gold (Map/Normalize → OCSF) |
|----------|------------------------|--------------------------|----------------------------|
| **Cisco IOS** | `cisco_ios_bronze` | `cisco_ios_silver` | `authentication`, `authorize_session`, `network_activity`, `process_activity` |
| **Cloudflare Gateway DNS** | `cloudflare_gateway_dns_bronze` | `cloudflare_gateway_dns_silver` | `dns_activity` |
| **Zeek Conn** | `zeek_conn_bronze` | `zeek_conn_silver` | `network_activity` |

### Spark SQL Metadata Field Examples

DSL Lite uses Spark SQL transformations in the `bronze.preTransform` section to add metadata fields. Here are examples for JSON and Syslog formats:

> **Note**: The `host` field is optional and should only be included if your log source contains hostname or device identifier information. If not available, comment it out or omit it entirely.

#### JSON Example (Cloudflare Gateway DNS)
```yaml
bronze:
  preTransform:
    - "data"
    - "_metadata.file_path"  # Recommended
    - CAST(try_variant_get(data, '$.Datetime', 'STRING') AS TIMESTAMP) as time  # Required
    - CAST(time AS DATE) as date  # Optional: for simplified date-based queries
    - CAST(try_variant_get(data, '$.QueryName', 'STRING') AS STRING) as host  # Optional (if applicable): DNS query name
    - CAST('cloudflare' AS STRING) as source  # Recommended
    - CAST('gateway_dns' AS STRING) as sourcetype  # Recommended
    - CURRENT_TIMESTAMP() as processed_time  # Recommended
```
- `time`: *(Required)* Extracted from JSON field `$.Datetime`
- `date`: *(Optional)* Derived from `time` field using `CAST(time AS DATE)` for simplified date-based queries
- `host`: *(Optional, if applicable)* Extracted from JSON field `$.QueryName` (DNS query name) - only include if hostname data is available
- `file_path`: *(Recommended)* Auto Loader metadata `_metadata.file_path`
- `source`: *(Recommended)* Static value identifying the vendor
- `sourcetype`: *(Recommended)* Static value identifying the log type
- `processed_time`: *(Recommended)* Timestamp when the record was processed
- `dsl_id`: *(Auto-generated)* Unique identifier for each record, used for deduplication and data lineage tracking

#### Syslog Example (Cisco IOS)
```yaml
bronze:
  preTransform:
    - "*"
    - "_metadata.file_path"  # Recommended
    - TO_TIMESTAMP(REGEXP_EXTRACT(value, '(\\w+\\s+\\d+\\s+\\d+\\s+\\d+:\\d+:\\d+)', 1), 'MMM d yyyy HH:mm:ss') as time  # Required
    - CAST(time AS DATE) as date  # Optional: for simplified date-based queries
    # - REGEXP_EXTRACT(value, '^([\\w\\-\\.]+):', 1) as host  # Optional: device hostname (if present)
    - CAST('cisco' AS STRING) as source  # Recommended
    - CAST('ios' AS STRING) as sourcetype  # Recommended
    - CURRENT_TIMESTAMP() as processed_time  # Recommended
```
- `time`: *(Required)* Extracted from syslog timestamp using regex pattern
- `date`: *(Optional)* Derived from `time` field using `CAST(time AS DATE)` for simplified date-based queries
- `host`: *(Optional, if applicable)* Commented out - device hostname not present in sample logs, but can be extracted if available in your environment
- `file_path`: *(Recommended)* Auto Loader metadata `_metadata.file_path`
- `source`: *(Recommended)* Static value identifying the vendor
- `sourcetype`: *(Recommended)* Static value identifying the log type
- `processed_time`: *(Recommended)* Timestamp when the record was processed
- `dsl_id`: *(Auto-generated)* Unique identifier for each record, used for deduplication and data lineage tracking

### Data Flow Examples by Format

#### JSON / JSON Lines
```
Bronze (data VARIANT) → Silver (flatten data.field.nested) → Gold (map to OCSF)
```
- **Bronze**: `data` field stores entire JSON object + 7 Spark SQL metadata fields
- **Silver**: Extract with `data.user.name`, `data.network.src_ip` + 7 Spark SQL metadata fields
- **Gold**: Map to OCSF `src_endpoint.user.name`, `src_endpoint.ip` + populate OCSF `metadata` STRUCT

#### Syslog / Text
```
Bronze (value STRING) → Silver (REGEXP_EXTRACT from value) → Gold (map to OCSF)
```
- **Bronze**: `value` field stores full log line + 7 Spark SQL metadata fields
- **Silver**: Extract fields using regex: `REGEXP_EXTRACT(value, 'src=(\\S+)', 1) as source_ip` + 7 Spark SQL metadata fields
- **Gold**: Map extracted fields to OCSF schema + populate OCSF `metadata` STRUCT

#### CSV with Header
```
Bronze (data STRUCT w/ named fields) → Silver (cast & clean) → Gold (map to OCSF)
```
- **Bronze**: Auto Loader CSV format with `inferSchema=true`, stores as `data.column1`, `data.column2`, etc. + 7 Spark SQL metadata fields
- **Silver**: Cast and rename: `CAST(data.timestamp AS TIMESTAMP) as event_time`, clean/filter if needed + 7 Spark SQL metadata fields
- **Gold**: Map renamed fields to OCSF schema + populate OCSF `metadata` STRUCT

#### CSV without Header
```
Bronze (value STRING) → Silver (from_csv to parse) → Gold (map to OCSF)
```
- **Bronze**: Load as text, `value` field stores full CSV line + 7 Spark SQL metadata fields
- **Silver**: Parse with `from_csv(value, schema)` to extract typed columns + 7 Spark SQL metadata fields
- **Gold**: Map extracted fields to OCSF schema + populate OCSF `metadata` STRUCT

### OCSF Metadata Field Mapping

Gold layer tables include an OCSF `metadata` STRUCT that provides critical context about the event's origin, processing, and schema versioning. DSL Lite automatically populates these fields during the Gold transformation to ensure [OCSF 1.7.0 compliance](https://schema.ocsf.io/1.7.0/objects/metadata).

#### Metadata Field Mappings

| DSL Lite Field | OCSF Metadata Field | OCSF Requirement | Description | Example Value |
|----------------|---------------------|------------------|-------------|---------------|
| `source` | `metadata.log_provider` | Optional | The logging provider or service that logged the event | `"zeek"`, `"cisco"`, `"cloudflare"` |
| `sourcetype` | `metadata.log_name` | Recommended | The event log name, typically for the consumer of the event | `"conn"`, `"ios"`, `"gateway_dns"` |
| `processed_time` | `metadata.processed_time` | Optional | Timestamp when the event was processed by DSL Lite | `2026-02-03T14:30:00Z` |
| OCSF version | `metadata.version` | **Required** | The version of the OCSF schema used | `"1.7.0"` |
| Schema version | `metadata.log_version` | Optional | Custom schema version tracking for change management | `"zeek@conn:version@1.0"`, `"cisco@ios:version@1.0"`, `"cloudflare@gateway_dns:version@1.0"`  |
| Log format | `metadata.log_format` | Optional | The original format of the data | `"JSON"`, `"syslog"`, `"CSV"` |

#### Schema Version Tracking

The `metadata.log_version` field uses a custom format to track schema changes over time:

```
<source>@<sourcetype>:version@<version>
```

**Examples:**
- `"zeek@conn:version@1.0"` - Zeek connection logs, schema version 1.0
- `"cisco@ios:version@1.1"` - Cisco IOS logs, schema version 1.1
- `"cloudflare@gateway_dns:version@1.2"` - Cloudflare Gateway DNS logs, schema version 1.2

**Use Case:** If you update your OCSF mapping (e.g., add new enrichments or change field mappings), increment the schema version. This enables selective record deletion or reprocessing:

```sql
-- Delete records with old schema version before reprocessing
DELETE FROM network_activity 
WHERE metadata.log_version = 'zeek@conn:version@1.0';
```

#### Example OCSF Metadata Structure

```json
{
  "metadata": {
    "version": "1.7.0",
    "log_provider": "zeek",
    "log_name": "conn",
    "log_format": "JSON",
    "log_version": "zeek@conn:version@1.0",
    "processed_time": "2026-02-03T14:30:00.000Z",
    "product": {
      "name": "DSL Lite",
      "vendor_name": "Databricks"
    }
  }
}
```

### Performance Optimization Guidelines

1. **Use `CLUSTER BY (time)` for all layers**: Cybersecurity queries are overwhelmingly time-based
2. **Partition by date sparingly**: Only for very large datasets (TB+ per day) to avoid small file problems
3. **Liquid Clustering**: For multi-dimensional queries, use `CLUSTER BY (time, src_endpoint.ip)` in Gold
4. **Filter pushdown**: Apply `preFilter` and `filter` in YAML to reduce data volume early

## Project Structure

```
dsl_lite/
├── src/                          # All Python source code
│   ├── dsl.py                   # Core DSL Lite logic
│   ├── utils.py                 # Utility functions
│   ├── sdp_medallion.py         # Entry point for SDP pipelines
│   ├── sss_bronze.py            # Bronze layer task (SSS mode)
│   ├── sss_silver.py            # Silver layer task (SSS mode)
│   ├── sss_gold.py              # Gold (OCSF) layer task (SSS mode)
│   └── sss_medallion.py         # Combined Bronze→Silver→Gold task (SSS mode)
├── notebooks/                    # Databricks notebooks
│   └── create_ocsf_tables.py    # Setup notebook for OCSF tables
├── pipelines/                    # Configuration presets (Cisco, Zeek, Cloudflare, etc.)
├── ocsf_templates/              # OCSF mapping templates (21 standardized templates)
├── vault/                       # Maintenance utilities for template management
├── raw_logs/                    # Sample logs for testing
└── README.md                    # Documentation
```

---

## How to use

To deploy a new data streaming pipeline you need:

- **Databases**: Bronze, silver, and gold layers with OCSF-compliant tables (create using `notebooks/create_ocsf_tables.py`)
- **Preset configuration**: YAML files defining data transformations for your log source (located in `pipelines/` directory)
- **Input location(s)**: Configure data source paths in the preset's `autoloader.inputs` section (only required if not skipping bronze layer)

DSL Lite provides starter templates in the `ocsf_templates/` directory for common security log sources.

### Execute as Spark Declarative Pipeline (SDP)

> **Note**: Apache Spark™ includes **declarative pipelines** beginning in Spark 4.1 via the `pyspark.pipelines` module. Databricks Runtime extends these capabilities with additional APIs and integrations.

- Upload the `src` directory to your workspace.
- Create `source` and `source_type` folders (i.e. `cisco/ios`) under `pipelines` to your workspace.
- Create a Lakeflow Spark Declarative Pipeline and reference `src/sdp_medallion.py` as the entry point.
- Specify default catalogs and databases, plus the following required configurations:

  - `dsl_lite.config_file` (required) - should contain a full path to a configuration file that will be used to generate a pipeline.  Example: `/Workspace/Users/<user@email.com>/dsl_lite/pipelines/cisco/ios/preset.yaml`.
  - `dsl_lite.gold_catalog_name` (optional) - the name of UC catalog containing gold tables. Used as default if not specified per-table in YAML.
  - `dsl_lite.gold_database_name` (optional) - the name of UC database containing gold tables. Used as default if not specified per-table in YAML.
  - `dsl_lite.bronze_catalog_name` (optional) - the name of UC catalog containing bronze tables.
  - `dsl_lite.bronze_database_name` (optional) - the name of UC database containing bronze tables. Required if `dsl_lite.skip_bronze` is `false`. **Note:** Can be omitted if silver table YAML uses fully qualified `input: catalog.database.table` paths.
  - `dsl_lite.silver_catalog_name` (optional) - the name of UC catalog containing silver tables.
  - `dsl_lite.silver_database_name` (required) - the name of UC database containing silver tables. Always required for Gold layer processing. **Note:** Can be omitted if all gold tables use fully qualified `input: catalog.database.table` paths.
  - `dsl_lite.skip_bronze` (optional, default `false`) - Skip bronze ingestion and use existing bronze tables.
  - `dsl_lite.skip_silver` (optional, default `false`) - Skip silver transformation and use existing silver tables.

**Example configuration JSON (Full Pipeline):**
```json
{
  "configuration": {
    "dsl_lite.bronze_database_name": "bronze",
    "dsl_lite.silver_database_name": "silver",
    "dsl_lite.gold_database_name": "gold",
    "dsl_lite.config_file": "/Workspace/Users/user@email.com/dsl_lite/pipelines/cisco/ios/preset.yaml",
    "dsl_lite.gold_catalog_name": "dsl_lite"
  }
}
```

**Example configuration JSON (Gold Only - Skip Bronze/Silver):**
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
> **Note:** `dsl_lite.gold_database_name` is omitted in this example because all gold tables specify their own `catalog` and `database` in the YAML. If any table omits these, you must provide `dsl_lite.gold_database_name` (and optionally `dsl_lite.gold_catalog_name`) as defaults.

---

### Execute as Spark Structured Streaming (SSS) Job

- Upload the `src` directory to your workspace.
- Create `source` and `source_type` folders (e.g. `cisco/ios`) under `pipelines` to your workspace.
- Choose one of three execution approaches:

**Option 1: Multi-Task Job (Recommended for Production)**
- Create a job with 3 separate tasks, each referencing the appropriate notebook:
  - **Task 1 (Bronze)**: `src/sss_bronze.py`
  - **Task 2 (Silver)**: `src/sss_silver.py` (depends on Bronze)
  - **Task 3 (Gold)**: `src/sss_gold.py` (depends on Silver)
- **Benefits**: Better separation of concerns, easier to debug individual layers, can skip layers by removing tasks

**Option 2: Single-Task Medallion Job (Recommended for Simplicity)**
- Create a job with a single notebook task that executes all three layers sequentially:
  - **Single Task**: `src/sss_medallion.py`
- **Benefits**: Simpler job configuration, all layers in one place, built-in skip options for Bronze/Silver
- **Use Cases**: Development, testing, or when you want to run the full pipeline in a single task

**Task Parameters by Layer:**

**Bronze Task (`src/sss_bronze.py`):**
  - `bronze_database` (required) - the name of database containing bronze tables - could be specified as `catalog.database`. Bronze does not support per-table catalog/database configuration.
  - `preset_file` (required) - full path to configuration file. Example: `/Workspace/Users/<user@email.com>/dsl_lite/pipelines/cisco/ios/preset.yaml`.
  - `checkpoints_location` (required) - path to storage location (DBFS or Volume) for checkpoints. Each input source gets its own checkpoint subdirectory: `{checkpoints_location}/bronze-{sanitized_input_name}`.
  - `continuous` (optional, default `False`) - run continuously (`True`) or batch mode (`False`).

**Silver Task (`src/sss_silver.py`):**
  - `bronze_database` (required) - the name of database containing bronze tables (same as Bronze task). Required to read from bronze tables. **Note:** Can be omitted if silver table YAML uses fully qualified `input: catalog.database.table` paths.
  - `silver_database` (required) - the name of database containing silver tables - could be specified as `catalog.database`. Silver does not support per-table catalog/database configuration.
  - `preset_file` (required) - full path to configuration file (same as Bronze task).
  - `checkpoints_location` (required) - path to storage location for checkpoints (can be same or different from Bronze). Each silver table gets its own checkpoint subdirectory: `{checkpoints_location}/silver-{sanitized_table_name}`.
  - `continuous` (optional, default `False`) - run continuously (`True`) or batch mode (`False`).

**Gold Task (`src/sss_gold.py`):**
  - `silver_database` (required) - the name of database containing silver tables (same as Silver task). Required to read from silver tables. **Note:** Can be omitted if all gold tables use fully qualified `input: catalog.database.table` paths.
  - `gold_database` (optional) - the name of database containing gold tables - could be specified as `catalog.database`. Used as default if not specified per-table in YAML. **Required only if any table omits `database` in YAML.**
  - `preset_file` (required) - full path to configuration file (same as Bronze/Silver tasks).
  - `checkpoints_location` (required) - path to storage location for checkpoints (can be same or different from other tasks). Each gold table gets its own checkpoint subdirectory: `{checkpoints_location}/gold-{table_name}`.
  - `continuous` (optional, default `False`) - run continuously (`True`) or batch mode (`False`).

**Medallion Task (`src/sss_medallion.py`) - All Layers Combined:**
  - `bronze_database` (required if `skip_bronze=False`) - the name of database containing bronze tables - could be specified as `catalog.database`. **Note:** Can be omitted if silver table YAML uses fully qualified `input: catalog.database.table` paths.
  - `silver_database` (required if `skip_silver=False`) - the name of database containing silver tables - could be specified as `catalog.database`. **Note:** Can be omitted if all gold tables use fully qualified `input: catalog.database.table` paths.
  - `gold_database` (required) - the name of database containing gold tables - could be specified as `catalog.database`. Used as default if not specified per-table in YAML. **Note:** Can be omitted if all gold tables specify `database` in YAML or use fully qualified paths.
  - `skip_bronze` (optional, default `False`) - skip bronze ingestion and use existing bronze tables (`True`) or create new bronze tables (`False`).
  - `skip_silver` (optional, default `False`) - skip silver transformation and use existing silver tables (`True`) or create new silver tables (`False`).
  - `preset_file` (required) - full path to configuration file. Example: `/Workspace/Users/<user@email.com>/dsl_lite/pipelines/cisco/ios/preset.yaml`.
  - `checkpoints_location` (required) - path to storage location (DBFS or Volume) for checkpoints. Each layer gets its own checkpoint subdirectories: `{checkpoints_location}/bronze-{sanitized_input_name}`, `{checkpoints_location}/silver-{sanitized_table_name}`, `{checkpoints_location}/gold-{table_name}`.
  - `continuous` (optional, default `False`) - run continuously (`True`) or batch mode (`False`).

**Example Multi-Task Job Configuration JSON:**
```json
{
  "name": "DSL Lite Medallion Pipeline",
  "tasks": [
    {
      "task_key": "bronze",
      "notebook_task": {
        "notebook_path": "/Workspace/Users/user@email.com/dsl_lite/src/sss_bronze",
        "base_parameters": {
          "bronze_database": "dsl_lite.cisco",
          "preset_file": "/Workspace/Users/user@email.com/dsl_lite/pipelines/cisco/ios/preset.yaml",
          "checkpoints_location": "/Volumes/dsl_lite/checkpoints/bronze",
          "continuous": "False"
        }
      }
    },
    {
      "task_key": "silver",
      "depends_on": [{"task_key": "bronze"}],
      "notebook_task": {
        "notebook_path": "/Workspace/Users/user@email.com/dsl_lite/src/sss_silver",
        "base_parameters": {
          "bronze_database": "dsl_lite.cisco",
          "silver_database": "dsl_lite.cisco",
          "preset_file": "/Workspace/Users/user@email.com/dsl_lite/pipelines/cisco/ios/preset.yaml",
          "checkpoints_location": "/Volumes/dsl_lite/checkpoints/silver",
          "continuous": "False"
        }
      }
    },
    {
      "task_key": "gold",
      "depends_on": [{"task_key": "silver"}],
      "notebook_task": {
        "notebook_path": "/Workspace/Users/user@email.com/dsl_lite/src/sss_gold",
        "base_parameters": {
          "silver_database": "dsl_lite.cisco",
          "gold_database": "dsl_lite.ocsf",
          "preset_file": "/Workspace/Users/user@email.com/dsl_lite/pipelines/cisco/ios/preset.yaml",
          "checkpoints_location": "/Volumes/dsl_lite/checkpoints/gold",
          "continuous": "False"
        }
      }
    }
  ]
}
```

**Example Single-Task Medallion Job Configuration JSON:**
```json
{
  "name": "DSL Lite Medallion Pipeline (Combined)",
  "tasks": [
    {
      "task_key": "medallion",
      "notebook_task": {
        "notebook_path": "/Workspace/Users/user@email.com/dsl_lite/src/sss_medallion",
        "base_parameters": {
          "bronze_database": "dsl_lite.cisco",
          "silver_database": "dsl_lite.cisco",
          "gold_database": "dsl_lite.ocsf",
          "skip_bronze": "False",
          "skip_silver": "False",
          "preset_file": "/Workspace/Users/user@email.com/dsl_lite/pipelines/cisco/ios/preset.yaml",
          "checkpoints_location": "/Volumes/dsl_lite/checkpoints",
          "continuous": "False"
        }
      }
    }
  ]
}
```

**Example Single-Task Medallion Job (Gold Only - Skip Bronze/Silver):**
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

---

## Advanced Configuration

### Skipping Bronze/Silver Layers

> **Note:** This section covers skipping layers for both multi-task and single-task jobs. See also the consolidated guide below.

**With Multi-Task Jobs:**
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
- Example job configuration:

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
> **Note:** `gold_database` is omitted in this example because all gold tables specify their own `catalog` and `database` in the YAML. If any table omits these, you must provide `gold_database` as a fallback.

**Note:** The `sss_gold.py` notebook automatically maps existing Silver tables from your YAML's `silver.transform[].name` section, so no additional configuration is needed when skipping Silver.

**With Single-Task Medallion Job (`sss_medallion.py`):**
Skipping layers is done using the `skip_bronze` and `skip_silver` parameters:

**To Skip Bronze:**
- Set `skip_bronze: "True"` in job parameters
- Silver layer will read from existing Bronze tables (ensure `bronze_database` parameter points to existing tables)

**To Skip Silver:**
- Set `skip_silver: "True"` in job parameters
- Gold layer automatically maps existing Silver tables from YAML config
- Ensure Silver tables exist and match the names in `silver.transform[].name` in your YAML

**To Skip Both Bronze and Silver (Gold Only):**
- Set both `skip_bronze: "True"` and `skip_silver: "True"` in job parameters
- Gold layer will use existing Silver tables (mapped from YAML)
- See the "Gold Only" example in the Single-Task Medallion Job section above

---

### Per-Table Catalog/Database Configuration

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
  - **YAML `catalog`/`database` fields (Gold only):** Specify **where to write to** (output tables) - only supported for Gold tables
- **When creating tables** (not skipping), you still need database **parameters** (`bronze_database`, `silver_database`) to specify where to write output tables
- **When skipping layers**, database parameters can be omitted if all tables use fully qualified `input` paths
- **Bronze and Silver tables** don't support `catalog`/`database` fields in YAML (unlike Gold tables) - you must use parameters
- Useful for referencing tables from different catalogs/databases or outside the current pipeline

**How it works:**
- **For Gold Tables:**
  - **Input (where to read from):** If `input` contains a dot (`.`) → treated as fully qualified name, used directly. If `input` has no dot → looked up in `silver_tables` dictionary (constructed from `silver_database` parameter)
  - **Output (where to write to):** If `catalog` and/or `database` are specified in YAML → uses those values for the output table. If omitted → falls back to `gold_database` parameter

- **For Silver Tables:**
  - **Input (where to read from - YAML field):** If `input` is specified and contains a dot (`.`) → treated as fully qualified bronze table name, used directly. If `input` is omitted or has no dot → uses default `bronze_table_name` (constructed from `bronze_database` parameter)
  - **Output (where to write to - Job parameter):** Silver tables don't support `catalog`/`database` fields in YAML. Always uses `silver_database` **job parameter** (not a YAML field) to determine where to write output tables

- **For Bronze Tables:**
  - **Output (where to write to - Job parameter):** Bronze tables don't support `catalog`/`database` fields in YAML. Always uses `bronze_database` **job parameter** (not a YAML field) to determine where to write output tables

**End-to-End Comparison: Simple Input Names vs Fully Qualified Paths**

Here are complete examples showing both approaches:

**Approach 1: Using Simple Input Names (with Database Parameters)**

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

**Approach 2: Using Fully Qualified Paths (Best for Skipping Layers)**

> **Note:** Fully qualified paths are most useful when **skipping layers**. When creating all layers, you still need database parameters to specify where to write tables, so fully qualified paths in `input` fields don't provide much benefit unless you're reading from a different database than where you're writing.

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
  "silver_database": "prod_catalog.enriched_db",  // Where to write silver (different from bronze location)
  "preset_file": "/path/to/preset.yaml",
  "checkpoints_location": "/Volumes/checkpoints",
  "skip_bronze": "True",   // Skipping bronze - no bronze_database needed!
  "skip_silver": "False"
  // gold_database not needed - specified in YAML
}
```

**Result:** Silver reads from `prod_catalog.raw_db.cisco_ios_bronze` (existing) but writes to `prod_catalog.enriched_db.cisco_ios_silver` (new table).

**Use Case 2: Gold Only (Skipping Bronze/Silver) - No Database Parameters Needed**

**YAML (`preset.yaml`):**
```yaml
name: cisco_ios
description: "Cisco IOS logs"

# No autoloader or bronze sections needed

# No silver section needed when using fully qualified paths

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
  // No database parameters needed - all paths are fully qualified!
}
```

**When to Use Each Approach:**
- **Simple Input Names**: Best for standard pipelines where all tables are in the same catalog/database structure
- **Fully Qualified Paths**: Best for skipping layers, cross-database references, or when you want to avoid database parameters

**Resulting Tables:**
- Bronze: `my_catalog.bronze_db.cisco_ios_bronze` (if bronze_database was `my_catalog.bronze_db`)
- Silver: `my_catalog.silver_db.cisco_ios_silver` (reads from `my_catalog.bronze_db.cisco_ios_bronze`)
- Gold: `my_catalog.gold_db.authentication` (reads from `my_catalog.silver_db.cisco_ios_silver`)

---

**Skipping Layers Example (Gold Only with Fully Qualified Paths):**

**YAML (`preset.yaml`):**
```yaml
name: cisco_ios
description: "Cisco IOS logs"

# No autoloader or bronze sections needed

# No silver section needed when using fully qualified paths

gold:
  - name: authentication
    input: my_catalog.silver_db.cisco_ios_silver  # Fully qualified path
    catalog: my_catalog
    database: gold_db
    filter: facility IN ('AAA', 'SEC_LOGIN')
    fields:
      - name: time
        expr: CAST(timestamp AS TIMESTAMP)
```

**Job Parameters:**
```json
{
  "preset_file": "/path/to/preset.yaml",
  "checkpoints_location": "/Volumes/checkpoints",
  "skip_bronze": "True",
  "skip_silver": "True"
  // No database parameters needed!
}
```

**Configuration Requirements:**

**For SSS Mode (Spark Structured Streaming):**
- `gold_database` parameter is **optional** - only required if any table omits `database` in YAML (used as fallback)
- If **all** tables specify `database` in YAML → you can **omit** `gold_database` parameter
- If **any** table omits `database` in YAML → you **must** provide `gold_database` parameter as fallback
- Per-table `database` in YAML overrides the `gold_database` parameter
- Per-table `catalog` in YAML is optional (if omitted, table uses database only, no catalog)

**For SDP Mode (Spark Declarative Pipeline):**
- If **all** tables specify both `catalog` and `database` in YAML → you can **omit** `dsl_lite.gold_database_name` and `dsl_lite.gold_catalog_name` from config
- If **any** table omits `catalog` or `database` in YAML → you **must** provide `dsl_lite.gold_database_name` (and optionally `dsl_lite.gold_catalog_name`) as defaults
- Note: SDP requires both catalog and database to be specified (either per-table in YAML or via Spark conf defaults)

---

### Lookup Joins

DSL Lite supports joining bronze and silver tables with lookup tables or CSV files to enrich data with reference information (e.g., IP geolocation, user mappings, threat intelligence).

#### Key Features

- **Multiple lookup sources**: Delta tables, CSV, Parquet, JSON files
- **Stream-static joins**: Automatically handles streaming DataFrames with batch lookup tables
- **Column prefixing**: Avoid column name conflicts with `prefix` option
- **Broadcast joins**: Optimize small lookups with `broadcast: true`
- **Multiple join types**: left, inner, right, full
- **Data flow**: Lookup columns from bronze are available in silver and gold; lookup columns from silver are available in gold

#### Bronze Layer Lookup

Lookups applied in bronze are available to all downstream layers (silver and gold).

```yaml
bronze:
  name: firewall_logs_bronze
  preTransform:
    - "*"
    - "REGEXP_EXTRACT(value, 'src_ip=(\\S+)', 1) as src_ip"
  lookups:
    - name: ip_geolocation
      source:
        type: table                  # Options: "table" | "csv" | "parquet" | "json"
        path: security_lakehouse.geoip.ip_lookup  # Fully qualified table name
        # OR for files:
        # path: /Volumes/lookups/ip_geolocation.csv
        # format: csv
        # options:
        #   header: "true"
        #   inferSchema: "true"
      join:
        type: left                   # Options: "left" | "inner" | "right" | "full"
        "on":                        # Note: 'on' must be quoted in YAML to avoid being interpreted as boolean True
          - main.src_ip = lookup.ip_address  # Format: "main.<column> = lookup.<column>"
          # OR simple format (if column names match):
          # - ip                      # Joins on main.ip = lookup.ip
      select:                        # Optional: which columns to include from lookup
        - country_code
        - city
        - asn
      prefix: "src_geo_"             # Optional: prefix for lookup columns
      broadcast: true                 # Optional: use broadcast join for small lookups
```

#### Silver Layer Lookup

Lookups applied in silver are available to the gold layer.

```yaml
silver:
  transform:
    - name: auth_logs_silver
      lookups:
        - name: user_mapping
          source:
            type: csv
            path: /Volumes/lookups/employee_directory.csv
            format: csv
            options:
              header: "true"
          join:
            type: left
            "on":  # Note: 'on' must be quoted in YAML
              - main.username = lookup.email
          select:
            - department
            - manager
            - office_location
          prefix: "user_"
          broadcast: true             # Recommended for small CSV lookups
      fields:
        - name: user_department
          from: department            # Reference lookup column
```

#### Using Lookup Columns in Gold

Lookup columns from bronze or silver can be referenced in gold field expressions:

```yaml
gold:
  - name: network_activity
    input: firewall_logs_silver
    fields:
      - name: src_endpoint.ip
        from: src_ip
      - name: src_endpoint.location.country
        from: src_geo_country_code    # Reference bronze lookup column
      - name: src_endpoint.location.city
        from: src_geo_city             # Reference bronze lookup column
      - name: enrichments
        expr: |
          CASE
            WHEN src_geo_asn IS NOT NULL THEN
              ARRAY(
                NAMED_STRUCT('name', 'ASN', 'type', 'Network', 'value', CAST(src_geo_asn AS STRING))
              )
            ELSE NULL
          END
```

#### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `source.type` | Lookup source type: `table`, `csv`, `parquet`, `json`, `jsonl` | `table` |
| `source.path` | Fully qualified table name (`catalog.database.table`) or file path | Required |
| `source.format` | File format (required for file sources) | Same as `type` |
| `source.options` | File read options (e.g., `header: "true"`, `inferSchema: "true"`) | `{}` |
| `join.type` | Join type: `left`, `inner`, `right`, `full` | `left` |
| `join.on` | Join condition(s): `main.<column> = lookup.<column>` or simple column name. **Must be quoted as `"on"` in YAML** to avoid being interpreted as boolean `True` | Required |
| `select` | Columns to include from lookup (if omitted, all columns included) | All columns |
| `prefix` | Prefix for lookup columns to avoid conflicts | None |
| `broadcast` | Use broadcast join for small lookups (< 2GB) | `false` |

#### Best Practices

1. **Use `prefix`** to avoid column name conflicts between main DataFrame and lookup tables
2. **Set `broadcast: true`** for small lookups (< 2GB) to improve performance
3. **Bronze lookups** are more efficient when enrichment is needed in multiple downstream layers
4. **Silver lookups** are useful when enrichment depends on parsed/structured data
5. **Multiple lookups** are processed in order specified in YAML

---

### Development & Testing Tool

**DASL Preset Tool** provides an interactive development workflow for creating, testing, and iterating on preset configurations before deploying to production with DSL Lite.

- **Interactive Development**: Test preset transformations in real-time using sample log files
- **Rapid Iteration**: Quickly validate changes to YAML preset configurations
- **Preview & Debug**: Preview bronze, silver, and gold layer outputs before deployment
- **Production Deployment**: Once validated, deploy presets via DSL Lite

For more information, see the [DASL Preset Tool repository](https://github.com/grp-db/preset_tool).

---

## Key Features

- **Self-contained deployment**: No dependencies on external DSL infrastructure
- **OCSF-compliant**: Outputs data in Open Cybersecurity Schema Framework format
- **Multiple execution modes**: Spark Declarative Pipelines (SDP) or standalone Spark jobs
- **Flexible input sources**: Read from multiple locations, supports Databricks Volumes, S3, ADLS, etc.
- **Secret management**: Reference Databricks Secrets in configurations via `{{secrets/<scope>/<key>}}`
- **Streaming or batch**: Run continuously or in batch mode with `availableNow` trigger
- **High performance**: Optimized `dsl_id` generation (3x faster than UDF-based approach)

---

## Supported Data Sources

DSL Lite uses Databricks Auto Loader to ingest data from file-based sources:
- **Cloud Storage**: S3, ADLS Gen2, Google Cloud Storage
- **Databricks Volumes**: Unity Catalog volumes
- **DBFS**: Databricks File System
- **Log Formats**: JSON, JSON Lines, CSV, Parquet, text/syslog

Support for streaming sources (Kafka, Event Hubs, Kinesis) can be added based on customer requirements.

---

---

## License & Attribution

**Copyright © Databricks, Inc.**

This accelerator is developed and maintained by Databricks Field Engineering and Professional Services.

### Usage & Distribution

This accelerator is available to support customers and the broader community in building cybersecurity solutions on Databricks.

**Note**: This is a community-supported accelerator. For production support and customization services, please contact your Databricks account team or Professional Services.

### Support & Contributions

- **Issues & Questions**: Open an issue in the repository or contact your Databricks representative
- **Feature Requests**: Reach out to Databricks Field Engineering or Professional Services
- **Contributions**: Contributions are welcome - please coordinate with the Databricks team

---

**Built with ❤️ by Databricks Field Engineering & Professional Services**