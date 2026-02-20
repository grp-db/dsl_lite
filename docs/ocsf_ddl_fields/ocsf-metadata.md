# OCSF Metadata Struct Reference

The **metadata** top-level field appears on all OCSF event tables. It holds event provenance: product info, timestamps, correlation IDs, and log context. Use this reference when mapping pipeline or vendor fields into `metadata` in YAML or Spark.

## Struct shape

| Field | Type | Description |
|-------|------|-------------|
| `correlation_uid` | STRING | Correlation ID to link related events (e.g. same session or request). |
| `event_code` | STRING | Vendor or product event code. |
| `log_level` | STRING | Log level (e.g. INFO, WARN, ERROR). |
| `log_name` | STRING | Name of the log or channel. |
| `log_provider` | STRING | Provider of the log (e.g. vendor or system name). |
| `log_format` | STRING | Format of the original log (e.g. JSON, CEF, LEEF). |
| `log_version` | STRING | Version of the log format or schema. |
| `logged_time` | TIMESTAMP | When the event was logged (ingestion/write time). |
| `modified_time` | TIMESTAMP | When the record was last modified. |
| `original_time` | STRING | Original event time as reported by the source (often string). |
| `processed_time` | TIMESTAMP | When the event was processed (e.g. normalized or enriched). |
| **`product`** | STRUCT | Product/vendor info (see below). |
| `tags` | VARIANT | Arbitrary tags or labels (array or map). |
| `tenant_uid` | STRING | Tenant or organization identifier (multi-tenant). |
| `uid` | STRING | Unique identifier for this event record. |
| `version` | STRING | OCSF or schema version (e.g. 1.7.0). |

## Nested: `product`

| Field | Type | Description |
|-------|------|-------------|
| `name` | STRING | Product name (e.g. Cisco IOS, Zeek, Cloudflare). |
| `vendor_name` | STRING | Vendor or vendor product family. |
| `version` | STRING | Product or agent version. |

## Spark DDL

```sql
STRUCT<
  correlation_uid: STRING,
  event_code: STRING,
  log_level: STRING,
  log_name: STRING,
  log_provider: STRING,
  log_format: STRING,
  log_version: STRING,
  logged_time: TIMESTAMP,
  modified_time: TIMESTAMP,
  original_time: STRING,
  processed_time: TIMESTAMP,
  product: STRUCT<
    name: STRING,
    vendor_name: STRING,
    version: STRING
  >,
  tags: VARIANT,
  tenant_uid: STRING,
  uid: STRING,
  version: STRING
>
```

## Timestamp usage

| Field | Typical use |
|-------|-------------|
| `time` (top-level) | Canonical event occurrence time; use for querying and analytics. |
| `original_time` | Raw timestamp from source (string); preserve for audit. |
| `logged_time` | When the event was written to the log. |
| `processed_time` | When the pipeline or normalizer handled the event. |
| `modified_time` | Last update to the record (e.g. enrichment). |

## Variants

- **kernel_extension_activity** uses the same metadata shape but adds `profiles: ARRAY<STRING>`. Other tables use the struct above without `profiles`.

## Where it’s used

Every OCSF table in this repo has a **`metadata`** column with this shape (or the kernel variant). It is a [common field](../ocsf_event_categories/network_activity/network_activity.md) for YAML mappings across categories.
