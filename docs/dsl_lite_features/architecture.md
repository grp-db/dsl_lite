# DSL Lite — Architecture Reference

DSL Lite implements a three-layer medallion architecture optimized for cybersecurity data pipelines. Each layer serves a specific purpose in the data transformation journey from raw logs to OCSF-compliant analytics-ready tables.

---

## Common Input Formats

- **JSON / JSON Lines**: Semi-structured events with nested fields
- **CSV**: With headers (Auto Loader CSV format) or without headers (text format with `from_csv` in Silver)
- **Syslog**: RFC 3164/5424 text-based log messages

---

## Layer-by-Layer Architecture

| Layer | Step | Description | Schema Example | Output | Performance |
|-------|------|-------------|----------------|--------|-------------|
| **Bronze** | **Ingest & Amend** | Raw data ingestion with minimal transformation. Preserves original data in `data` (VARIANT for JSON, STRUCT for CSV with headers) or `value` (STRING for syslog/text/CSV without headers). Spark SQL adds metadata tags for downstream processing. | `data VARIANT/STRUCT` **OR** `value STRING`<br/><br/>**+ 7 Spark SQL metadata fields:**<br/>`time TIMESTAMP` *(required)*<br/>`date DATE` *(optional)*<br/>`host STRING` *(optional, if applicable)*<br/>`source STRING` *(recommended)*<br/>`sourcetype STRING` *(recommended)*<br/>`processed_time TIMESTAMP` *(recommended)*<br/>`file_path STRING` *(recommended)*<br/><br/>**+ DSL Lite ID:**<br/>`dsl_id STRING` (unique identifier) | **Delta Table (Streaming)**<br/>- Auto Loader for incremental ingestion<br/>- Supports schema evolution<br/>- Raw data preservation | `CLUSTER BY (time)`<br/><br/>Optimizes time-based queries and improves compression |
| **Silver** | **Parse & Structure** | Flattens nested JSON from `data` field, extracts structured fields from `value` using regex patterns, or parses CSV with `from_csv()`. Converts unstructured logs into typed, queryable columns. Applies business logic, filters, and temporary fields. | **JSON:** Extracted from `data` VARIANT<br/>`source_ip STRING`<br/>`dest_ip STRING`<br/>`port INT`<br/>`protocol STRING`<br/>`action STRING`<br/>`bytes_in BIGINT`<br/>`bytes_out BIGINT`<br/>`duration DOUBLE`<br/>`user STRING`<br/><br/>**Syslog:** Extracted from `value` STRING<br/>`severity STRING`<br/>`facility STRING`<br/>`process STRING`<br/>`pid INT`<br/>`message STRING`<br/><br/>**+ 7 Spark SQL metadata fields**<br/>**+ DSL Lite ID:** `dsl_id STRING` | **Delta Table (Streaming)**<br/>- Typed columns for efficient queries<br/>- Filtered and cleansed data<br/>- Vendor-specific schema | `CLUSTER BY (time)`<br/><br/>Maintains time-based optimization for log analytics |
| **Gold** | **Map & Normalize** | Maps silver tables to OCSF-compliant schemas. Standardizes field names, data types, and structures across vendors. Includes OCSF `metadata` STRUCT with versioning and lineage tracking. Creates analytics-ready tables for security operations, threat hunting, and compliance reporting. | `activity_id INT`<br/>`activity_name STRING`<br/>`time TIMESTAMP`<br/>`src_endpoint STRUCT<...>`<br/>`dst_endpoint STRUCT<...>`<br/>`connection_info STRUCT<...>`<br/>`metadata STRUCT<...>`<br/>`observables ARRAY<STRUCT<...>>`<br/>`enrichments ARRAY<STRUCT<...>>`<br/>`severity STRING`<br/>`severity_id INT`<br/>`dsl_id STRING` | **Delta Table (Sink)**<br/>- OCSF-compliant schema<br/>- Cross-vendor normalization<br/>- Analytics-ready<br/>- Metadata tracking | `CLUSTER BY (time)`<br/><br/>Enables fast time-range queries for security investigations |

> **Note on Gold Layer Delta Sinks**: In Spark Declarative Pipeline (SDP) mode, gold tables must be Delta Sinks (not streaming tables) because multiple streams from different pipelines write to the same OCSF-compliant gold tables. Since SDP streaming tables are linked to each individual pipeline, Delta Sinks are required to support concurrent writes from multiple pipeline streams, enabling cross-vendor data aggregation in unified OCSF tables.

---

## Example Pipeline Graph

The following screenshot shows an example pipeline graph (bronze → silver → gold) as rendered in Databricks when using DSL Lite with a preset such as GitHub Audit Logs:

![Example pipeline graph (bronze, silver, gold)](../../images/pipeline_graph.png)

*Figure: Example DSL Lite pipeline graph showing Auto Loader (bronze), silver transform, and multiple OCSF gold table sinks.*

---

## Example Pipeline Outputs

| Pipeline | Bronze (Ingest/Amend) | Silver (Parse/Structure) | Gold (Map/Normalize → OCSF) |
|----------|------------------------|--------------------------|----------------------------|
| **Cisco IOS** | `cisco_ios_bronze` | `cisco_ios_silver` | `authentication`, `authorize_session`, `network_activity`, `process_activity` |
| **Cloudflare Gateway DNS** | `cloudflare_gateway_dns_bronze` | `cloudflare_gateway_dns_silver` | `dns_activity` |
| **GitHub Audit Logs** | `github_audit_logs_bronze` | `github_audit_logs_silver` | `account_change`, `authentication`, `authorize_session`, `user_access`, `group_management` |
| **Zeek Conn** | `zeek_conn_bronze` | `zeek_conn_silver` | `network_activity` |
| **AWS VPC Flow Logs** | `aws_vpc_flowlogs_bronze` | `aws_vpc_flowlogs_silver` | `network_activity` |

---

## Spark SQL Metadata Field Examples

DSL Lite uses Spark SQL transformations in the `bronze.preTransform` section to add metadata fields. Here are examples for JSON and Syslog formats:

> **Note**: The `host` field is optional and should only be included if your log source contains hostname or device identifier information. If not available, comment it out or omit it entirely.

### JSON Example (Cloudflare Gateway DNS)

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
- `host`: *(Optional, if applicable)* Extracted from JSON field `$.QueryName` — only include if hostname data is available
- `file_path`: *(Recommended)* Auto Loader metadata `_metadata.file_path`
- `source`: *(Recommended)* Static value identifying the vendor
- `sourcetype`: *(Recommended)* Static value identifying the log type
- `processed_time`: *(Recommended)* Timestamp when the record was processed
- `dsl_id`: *(Auto-generated)* Unique identifier for each record, used for deduplication and data lineage tracking

### Syslog Example (Cisco IOS)

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
- `host`: *(Optional, if applicable)* Commented out — device hostname not present in sample logs, but can be extracted if available
- `file_path`: *(Recommended)* Auto Loader metadata `_metadata.file_path`
- `source`: *(Recommended)* Static value identifying the vendor
- `sourcetype`: *(Recommended)* Static value identifying the log type
- `processed_time`: *(Recommended)* Timestamp when the record was processed
- `dsl_id`: *(Auto-generated)* Unique identifier for each record, used for deduplication and data lineage tracking

---

## Data Flow Examples by Format

### JSON / JSON Lines
```
Bronze (data VARIANT) → Silver (flatten data.field.nested) → Gold (map to OCSF)
```
- **Bronze**: `data` field stores entire JSON object + 7 Spark SQL metadata fields
- **Silver**: Extract with `data.user.name`, `data.network.src_ip` + 7 Spark SQL metadata fields
- **Gold**: Map to OCSF `src_endpoint.user.name`, `src_endpoint.ip` + populate OCSF `metadata` STRUCT

### Syslog / Text
```
Bronze (value STRING) → Silver (REGEXP_EXTRACT from value) → Gold (map to OCSF)
```
- **Bronze**: `value` field stores full log line + 7 Spark SQL metadata fields
- **Silver**: Extract fields using regex: `REGEXP_EXTRACT(value, 'src=(\\S+)', 1) as source_ip` + 7 Spark SQL metadata fields
- **Gold**: Map extracted fields to OCSF schema + populate OCSF `metadata` STRUCT

### CSV with Header
```
Bronze (data STRUCT w/ named fields) → Silver (cast & clean) → Gold (map to OCSF)
```
- **Bronze**: Auto Loader CSV format with `inferSchema=true`, stores as `data.column1`, `data.column2`, etc. + 7 Spark SQL metadata fields
- **Silver**: Cast and rename: `CAST(data.timestamp AS TIMESTAMP) as event_time`, clean/filter if needed + 7 Spark SQL metadata fields
- **Gold**: Map renamed fields to OCSF schema + populate OCSF `metadata` STRUCT

### CSV without Header
```
Bronze (value STRING) → Silver (from_csv to parse) → Gold (map to OCSF)
```
- **Bronze**: Load as text, `value` field stores full CSV line + 7 Spark SQL metadata fields
- **Silver**: Parse with `from_csv(value, schema)` to extract typed columns + 7 Spark SQL metadata fields
- **Gold**: Map extracted fields to OCSF schema + populate OCSF `metadata` STRUCT

---

## OCSF Metadata Field Mapping

Gold layer tables include an OCSF `metadata` STRUCT that provides critical context about the event's origin, processing, and schema versioning. DSL Lite automatically populates these fields during the Gold transformation to ensure [OCSF 1.7.0 compliance](https://schema.ocsf.io/1.7.0/objects/metadata).

### Metadata Field Mappings

| DSL Lite Field | OCSF Metadata Field | OCSF Requirement | Description | Example Value |
|----------------|---------------------|------------------|-------------|---------------|
| `source` | `metadata.log_provider` | Optional | The logging provider or service that logged the event | `"zeek"`, `"cisco"`, `"cloudflare"`, `"github"`, `"aws"` |
| `sourcetype` | `metadata.log_name` | Recommended | The event log name, typically for the consumer of the event | `"conn"`, `"ios"`, `"gateway_dns"`, `"audit_logs"`, `"vpc_flowlogs"` |
| `processed_time` | `metadata.processed_time` | Optional | Timestamp when the event was processed by DSL Lite | `2026-02-03T14:30:00Z` |
| OCSF version | `metadata.version` | **Required** | The version of the OCSF schema used | `"1.7.0"` |
| Schema version | `metadata.log_version` | Optional | Custom schema version tracking for change management | `"zeek@conn:version@1.0"`, `"cisco@ios:version@1.0"` |
| Log format | `metadata.log_format` | Optional | The original format of the data | `"JSON"`, `"syslog"`, `"CSV"`, `"TEXT"` |

### Schema Version Tracking

The `metadata.log_version` field uses a custom format to track schema changes over time:

```
<source>@<sourcetype>:version@<version>
```

**Examples:**
- `"zeek@conn:version@1.0"` — Zeek connection logs, schema version 1.0
- `"cisco@ios:version@1.1"` — Cisco IOS logs, schema version 1.1
- `"cloudflare@gateway_dns:version@1.2"` — Cloudflare Gateway DNS logs, schema version 1.2
- `"github@audit_logs:version@1.0"` — GitHub audit logs, schema version 1.0
- `"aws@vpc_flowlogs:version@1.0"` — AWS VPC Flow Logs, schema version 1.0

**Use Case:** When you update your OCSF mapping (e.g., add new enrichments or change field mappings), increment the schema version. This enables selective record deletion or reprocessing. See [Advanced Configuration — Checkpoint Resets](advanced-configuration.md#checkpoint-resets-in-sdp-spark-declarative-pipeline) for the full workflow.

### Example OCSF Metadata Structure

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

---

## Performance Optimization Guidelines

1. **Use `CLUSTER BY (time)` for all layers**: Cybersecurity queries are overwhelmingly time-based
2. **Partition by date sparingly**: Only for very large datasets (TB+ per day) to avoid small file problems
3. **Liquid Clustering**: For multi-dimensional queries, use `CLUSTER BY (time, src_endpoint.ip)` in Gold
4. **Filter pushdown**: Apply `preFilter` and `filter` in YAML to reduce data volume early
