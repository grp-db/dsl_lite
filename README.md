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

## Cyber Medallion Architecture Best Practices

DSL Lite implements a three-layer medallion architecture optimized for cybersecurity data pipelines. Each layer serves a specific purpose in the data transformation journey from raw logs to OCSF-compliant analytics-ready tables.

### Common Input Formats

- **JSON / JSON Lines**: Semi-structured events with nested fields
- **CSV**: With headers (Auto Loader CSV format) or without headers (text format with `from_csv` in Silver)
- **Syslog**: RFC 3164/5424 text-based log messages

### Layer-by-Layer Architecture

| Layer | Step | Description | Schema Example | Output | Performance |
|-------|------|-------------|----------------|--------|-------------|
| **Bronze** | **Ingest & Amend** | Raw data ingestion with minimal transformation. Preserves original data in `data` (VARIANT for JSON/CSV with headers) or `value` (STRING for syslog/text/CSV without headers). Spark SQL adds metadata tags for downstream processing. | `data VARIANT` **OR** `value STRING`<br/><br/>**+ 7 Spark SQL metadata fields:**<br/>`time TIMESTAMP` *(required)*<br/>`date DATE` *(optional)*<br/>`host STRING` *(optional, if applicable)*<br/>`source STRING` *(recommended)*<br/>`sourcetype STRING` *(recommended)*<br/>`processed_time TIMESTAMP` *(recommended)*<br/>`file_path STRING` *(recommended)*<br/><br/>**+ DSL Lite ID:**<br/>`dsl_id STRING` (unique identifier) | **Delta Table (Streaming)**<br/>- Auto Loader for incremental ingestion<br/>- Supports schema evolution<br/>- Raw data preservation | `CLUSTER BY (time)`<br/><br/>Optimizes time-based queries and improves compression |
| **Silver** | **Parse & Structure** | Flattens nested JSON from `data` field, extracts structured fields from `value` using regex patterns, or parses CSV with `from_csv()`. Converts unstructured logs into typed, queryable columns. Applies business logic, filters, and temporary fields. | **JSON:** Extracted from `data` VARIANT<br/>`source_ip STRING`<br/>`dest_ip STRING`<br/>`port INT`<br/>`protocol STRING`<br/>`action STRING`<br/>`bytes_in BIGINT`<br/>`bytes_out BIGINT`<br/>`duration DOUBLE`<br/>`user STRING`<br/><br/>**Syslog:** Extracted from `value` STRING<br/>`severity STRING`<br/>`facility STRING`<br/>`process STRING`<br/>`pid INT`<br/>`message STRING`<br/><br/>**+ 7 Spark SQL metadata fields**<br/>**+ DSL Lite ID:** `dsl_id STRING` | **Delta Table (Streaming)**<br/>- Typed columns for efficient queries<br/>- Filtered and cleansed data<br/>- Vendor-specific schema | `CLUSTER BY (time)`<br/><br/>Maintains time-based optimization for log analytics |
| **Gold** | **Map & Normalize** | Maps silver tables to OCSF-compliant schemas. Standardizes field names, data types, and structures across vendors. Includes OCSF `metadata` STRUCT with versioning and lineage tracking. Creates analytics-ready tables for security operations, threat hunting, and compliance reporting. | `activity_id INT`<br/>`activity_name STRING`<br/>`time TIMESTAMP`<br/>`src_endpoint STRUCT<...>`<br/>`dst_endpoint STRUCT<...>`<br/>`connection_info STRUCT<...>`<br/>`metadata STRUCT<...>`<br/>`observables ARRAY<STRUCT<...>>`<br/>`enrichments ARRAY<STRUCT<...>>`<br/>`severity STRING`<br/>`severity_id INT`<br/>`dsl_id STRING` | **Delta Table (Streaming)**<br/>- OCSF-compliant schema<br/>- Cross-vendor normalization<br/>- Analytics-ready<br/>- Metadata tracking | `CLUSTER BY (time)`<br/><br/>Enables fast time-range queries for security investigations |

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
    - CAST('cisco' AS STRING) AS source  # Recommended
    - CAST('ios' AS STRING) AS sourcetype  # Recommended
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
Bronze (data VARIANT w/ named fields) → Silver (cast & clean) → Gold (map to OCSF)
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
| Schema version | `metadata.log_version` | Optional | Custom schema version tracking for change management | `"zeek@conn:version@1.0"` |
| Log format | `metadata.log_format` | Optional | The original format of the data | `"JSON"`, `"syslog"`, `"CSV"` |

#### Schema Version Tracking

The `metadata.log_version` field uses a custom format to track schema changes over time:

```
<source>@<sourcetype>:version@<version>
```

**Examples:**
- `"zeek@conn:version@1.0"` - Zeek connection logs, schema version 1.0
- `"cisco@ios:version@1.1"` - Cisco IOS logs, schema version 1.1
- `"cloudflare@gateway_dns:version@1.0"` - Cloudflare Gateway DNS logs, schema version 1.2

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
│   ├── dsl_sdp.py               # Entry point for Spark Declarative Pipelines
│   ├── dsl_spark.py             # Entry point for Spark jobs
│   ├── dsl.py                   # Core DSL Lite logic
│   └── utils.py                 # Utility functions
├── notebooks/                    # Databricks notebooks
│   └── create_ocsf_tables.py    # Setup notebook for OCSF tables
├── pipelines/                    # Configuration presets (Cisco, Zeek, Cloudflare, etc.)
├── ocsf_templates/              # OCSF mapping templates
├── raw_logs/                    # Sample logs for testing
└── README.md                    # Documentation
```

## How to use

To deploy a new data streaming pipeline you need:

- **Databases**: Bronze, silver, and gold layers with OCSF-compliant tables (create using `notebooks/create_ocsf_tables.py`)
- **Preset configuration**: YAML files defining data transformations for your log source (located in `pipelines/` directory)
- **Input location(s)**: Configure data source paths in the preset's `autoloader.inputs` section

DSL Lite provides starter templates in the `ocsf_templates/` directory for common security log sources.

### Execute as Spark Declarative Pipeline (SDP)

> **Note**: Apache Spark™ includes **declarative pipelines** beginning in Spark 4.1 via the `pyspark.pipelines` module. Databricks Runtime extends these capabilities with additional APIs and integrations.

- Upload the `src` directory containing `dsl_sdp.py`, `dsl.py` and `utils.py` to your workspace.
- Create `source` and `source_type` folders (i.e. `cisco/ios`) under `pipelines` to your workspace.
- Create a Lakeflow Spark Declarative Pipeline and specify default catalogs and databases, plus the following required configurations:

  - `dsl_lite.config_file` (required) - should contain a full path to a configuration file that will be used to generate a pipeline.  Example: `/Workspace/Users/<user@email.com>/dsl_lite/pipelines/cisco/ios/preset.yaml`.
  - `dsl_lite.gold_catalog_name` (required) - the name of UC catalog containing gold tables.
  - `dsl_lite.gold_database_name` (required) - the name of UC database containing gold tables.
  - `dsl_lite.bronze_catalog_name` (optional) - the name of UC catalog containing bronze tables.
  - `dsl_lite.bronze_database_name` (required) - the name of UC database containing bronze tables.
  - `dsl_lite.silver_catalog_name` (optional) - the name of UC catalog containing silver tables.
  - `dsl_lite.silver_database_name` (required) - the name of UC database containing silver tables.

**Example configuration JSON:**
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

### Execute as Spark (Python) job

- Upload the `src` directory containing `dsl_spark.py`, `dsl.py` and `utils.py` to your workspace.
- Create `source` and `source_type` folders (e.g. `cisco/ios`) under `pipelines` to your workspace.
- Create a job with a notebook task referring `src/dsl_spark.py` and with following parameters:

  - `preset_file` (required) - should contain a full path to a configuration file that will be used to process data.  Example: `/Workspace/Users/<user@email.com>/dsl_lite/pipelines/cisco/ios/preset.yaml`.
  - `bronze_database` (required) - the name of database containing bronze tables - could be specified as `catalog.database`.
  - `silver_database` (required) - the name of database containing silver tables - could be specified as `catalog.database`.
  - `gold_database` (required) - the name of database containing gold tables - could be specified as `catalog.database`.
  - `checkpoints_location` (required) - the path to storage location (DBFS or Volume) to store checkpoints for specific job.
  - `continuous` (optional, default `False`) - if job should run continuously (`True`) or not (`False`).

**Example configuration JSON:**
```json
{
  "preset_file": "/Workspace/Users/user@email.com/dsl_lite/pipelines/cisco/ios/preset.yaml",
  "bronze_database": "dsl_lite.cisco",
  "silver_database": "dsl_lite.cisco",
  "gold_database": "dsl_lite.ocsf",
  "checkpoints_location": "/Volumes/dsl_lite/pipelines/checkpoints/cisco-ios",
  "continuous": "False"
}
```

## Key Features

- **Self-contained deployment**: No dependencies on external DSL infrastructure
- **OCSF-compliant**: Outputs data in Open Cybersecurity Schema Framework format
- **Multiple execution modes**: Spark Declarative Pipelines (SDP) or standalone Spark jobs
- **Flexible input sources**: Read from multiple locations, supports Databricks Volumes, S3, ADLS, etc.
- **Secret management**: Reference Databricks Secrets in configurations via `{{secrets/<scope>/<key>}}`
- **Streaming or batch**: Run continuously or in batch mode with `availableNow` trigger
- **High performance**: Optimized `dsl_id` generation (3x faster than UDF-based approach)

## Supported Data Sources

DSL Lite uses Databricks Auto Loader to ingest data from file-based sources:
- **Cloud Storage**: S3, ADLS Gen2, Google Cloud Storage
- **Databricks Volumes**: Unity Catalog volumes
- **DBFS**: Databricks File System
- **Log Formats**: JSON, JSON Lines, CSV, Parquet, text/syslog

Support for streaming sources (Kafka, Event Hubs, Kinesis) can be added based on customer requirements.

---

## License & Attribution

**Copyright © Databricks, Inc.**

This accelerator is developed and maintained by Databricks Field Engineering and Professional Services.

### Usage & Distribution

This accelerator is available to support customers and the broader community in building cybersecurity solutions on the Databricks.

**Note**: This is a community-supported accelerator. For production support and customization services, please contact your Databricks account team or Professional Services.

### Support & Contributions

- **Issues & Questions**: Open an issue in the repository or contact your Databricks representative
- **Feature Requests**: Reach out to Databricks Field Engineering or Professional Services
- **Contributions**: Contributions are welcome - please coordinate with the Databricks team

---

**Built with ❤️ by Databricks Field Engineering & Professional Services**