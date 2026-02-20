# OCSF Gold Layer – Reusable Spark SQL Expressions

**Blueprint** for OCSF gold mappings: standard CASE WHEN patterns for IDs/names and named_struct for nested fields. Use in pipeline YAML `gold[].fields[]` with `name` + `expr`, `literal`, or `from`. Nested structs can be built from **dotted names** (e.g. `metadata.version`) or a single `expr` with `named_struct`. Class- or source-specific edge cases (e.g. status_detail logic) → see table docs and preset YAMLs.

---

## 1. CASE WHEN templates (IDs and names)

Replace `<…_CONDITION>` with your source logic. Result types: INT for `*_id`, STRING for names.

### action_id (0=Unknown, 1=Allowed, 2=Denied, 99=Other)

```sql
CAST(CASE
  WHEN <ALLOWED_CONDITION>  THEN 1
  WHEN <DENIED_CONDITION>   THEN 2
  ELSE 99
END AS INT)
```

### action (string)

```sql
CASE
  WHEN <ALLOWED_CONDITION> THEN 'Allowed'
  WHEN <DENIED_CONDITION>  THEN 'Denied'
  ELSE 'Other'
END
```

### status_id (0=Unknown, 1=Success, 2=Failure, 99=Other)

```sql
CAST(CASE
  WHEN <SUCCESS_CONDITION> THEN 1
  WHEN <FAILURE_CONDITION> THEN 2
  ELSE 99
END AS INT)
```

### status (string)

```sql
CASE
  WHEN <SUCCESS_CONDITION> THEN 'Success'
  WHEN <FAILURE_CONDITION> THEN 'Failure'
  ELSE 'Other'
END
```

### severity_id (0–6, 99)

```sql
CAST(CASE
  WHEN <FATAL_CONDITION>         THEN 6
  WHEN <CRITICAL_CONDITION>      THEN 5
  WHEN <HIGH_CONDITION>         THEN 4
  WHEN <MEDIUM_CONDITION>        THEN 3
  WHEN <LOW_CONDITION>           THEN 2
  WHEN <INFORMATIONAL_CONDITION> THEN 1
  ELSE 99
END AS INT)
```

### severity (string)

```sql
CASE
  WHEN <FATAL_CONDITION>         THEN 'Fatal'
  WHEN <CRITICAL_CONDITION>      THEN 'Critical'
  WHEN <HIGH_CONDITION>         THEN 'High'
  WHEN <MEDIUM_CONDITION>        THEN 'Medium'
  WHEN <LOW_CONDITION>           THEN 'Low'
  WHEN <INFORMATIONAL_CONDITION> THEN 'Informational'
  ELSE 'Other'
END
```

### disposition_id (0=Unknown, 1=Allowed, 2=Blocked, …)

```sql
CAST(CASE
  WHEN <ALLOWED_CONDITION>  THEN 1
  WHEN <BLOCKED_CONDITION>  THEN 2
  ELSE 0
END AS INT)
```

### disposition (string)

```sql
CASE
  WHEN <ALLOWED_CONDITION> THEN 'Allowed'
  WHEN <BLOCKED_CONDITION> THEN 'Blocked'
  ELSE 'Unknown'
END
```

### Syslog severity (0–7) → OCSF severity_id / severity

Common mapping when the source has a numeric severity (e.g. Cisco syslog 0–7):

```sql
-- severity_id
CASE
  WHEN CAST(severity AS INT) = 0 THEN CAST(6 AS INT)
  WHEN CAST(severity AS INT) IN (1, 2) THEN CAST(5 AS INT)
  WHEN CAST(severity AS INT) = 3 THEN CAST(4 AS INT)
  WHEN CAST(severity AS INT) = 4 THEN CAST(3 AS INT)
  WHEN CAST(severity AS INT) = 5 THEN CAST(2 AS INT)
  WHEN CAST(severity AS INT) IN (6, 7) THEN CAST(1 AS INT)
  ELSE CAST(99 AS INT)
END
```

```sql
-- severity (name)
CASE
  WHEN CAST(severity AS INT) = 0 THEN 'Fatal'
  WHEN CAST(severity AS INT) IN (1, 2) THEN 'Critical'
  WHEN CAST(severity AS INT) = 3 THEN 'High'
  WHEN CAST(severity AS INT) = 4 THEN 'Medium'
  WHEN CAST(severity AS INT) = 5 THEN 'Low'
  WHEN CAST(severity AS INT) IN (6, 7) THEN 'Informational'
  ELSE 'Other'
END
```

**status / status_id / status_code / status_detail:** Logic varies by event class (e.g. connection state vs rcode). Use the generic §1 status/status_id templates with your conditions, or copy from the preset that matches your class: Zeek conn → `pipelines/zeek/conn/preset.yaml`, Cloudflare DNS → `pipelines/cloudflare/gateway_dns/preset.yaml`.

---

## 2. named_struct – one expr per struct

Use for top-level structs (`raw_data`, `unmapped`) or when you prefer one expr over dotted names. Dotted names (e.g. `metadata.product.name`) also work; pick what fits.

### metadata (with nested product)

Replace placeholders with your columns/literals. Full shape: [ocsf-metadata](../ocsf_ddl_fields/ocsf-metadata.md).

```sql
named_struct(
  'version', '1.7.0',
  'product', named_struct('name', '<PRODUCT_NAME>', 'vendor_name', '<VENDOR>', 'version', '<VERSION>'),
  'log_provider', '<LOG_PROVIDER>',
  'log_name', '<LOG_NAME>',
  'log_format', '<LOG_FORMAT>',
  'log_version', '<LOG_VERSION>',
  'processed_time', current_timestamp(),
  'logged_time', time,
  'event_code', <EVENT_CODE_COL>,
  'uid', <UID_COL>,
  'correlation_uid', CAST(NULL AS STRING),
  'log_level', CAST(NULL AS STRING),
  'modified_time', CAST(NULL AS TIMESTAMP),
  'original_time', CAST(NULL AS STRING),
  'tenant_uid', CAST(NULL AS STRING),
  'tags', CAST(NULL AS VARIANT)
) AS metadata
```

### user (has_mfa, name, type, type_id, uid)

```sql
named_struct(
  'has_mfa', COALESCE(<HAS_MFA_COL>, FALSE),
  'name', <USERNAME_COL>,
  'type', COALESCE(<USER_TYPE_COL>, 'Unknown'),
  'type_id', CAST(0 AS INT),
  'uid', COALESCE(<USER_UID_COL>, CAST(NULL AS STRING))
) AS user
```

### service (name, uid)

```sql
named_struct(
  'name', '<SERVICE_NAME>',
  'uid', COALESCE(<SERVICE_UID_COL>, CAST(NULL AS STRING))
) AS service
```

### src_endpoint

```sql
named_struct(
  'ip', <SRC_IP_COL>,
  'port', TRY_CAST(<SRC_PORT_COL> AS INT),
  'hostname', CAST(NULL AS STRING),
  'domain', CAST(NULL AS STRING),
  'uid', CAST(NULL AS STRING),
  'location', CAST(NULL AS STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>),
  'mac', CAST(NULL AS STRING),
  'vpc_uid', CAST(NULL AS STRING),
  'zone', CAST(NULL AS STRING)
) AS src_endpoint
```
Fill `location` with a nested named_struct when GeoIP (or similar) is available. See [ocsf-endpoint](../ocsf_ddl_fields/ocsf-endpoint.md).

### raw_data (VARIANT)

```sql
CAST(to_json(named_struct('value', value, 'source', source, 'sourcetype', sourcetype)) AS VARIANT) AS raw_data
```

Adjust keys to your silver columns.

### unmapped (VARIANT)

```sql
CAST(
  to_json(
    named_struct(
      'seq_no', seq_no,
      'facility', facility,
      'severity', severity,
      'mnemonic', mnemonic,
      'timestamp', timestamp
    )
  )
AS VARIANT) AS unmapped
```

Replace keys/values with your silver columns.

### observables (one element)

```sql
named_struct('name', '<OBS_NAME>', 'type', '<OBS_TYPE>', 'value', <VALUE_COL>)
```
Wrap in `array(...)` for the full observables array.

---

## 3. type_uid

`type_uid = class_uid * 100 + activity_id`:

```sql
CAST(class_uid * 100 + activity_id AS BIGINT) AS type_uid
```

---

## 4. Bold (common) columns – field logic by category

Table docs mark **bold** columns as common per category; include them in gold. Use `name` + `from` / `literal` / `expr`. Patterns: §1–3 above; class-specific logic → presets.

### Network Activity (network_activity, dns_activity, http_activity)

| Gold field | Reusable logic |
|------------|----------------|
| `action` | §1 action (CASE WHEN) |
| `action_id` | §1 action_id |
| `activity_id` | Source-specific CASE WHEN; values in [ocsf-ids](../ocsf_ddl_fields/ocsf-ids.md) |
| `activity_name` | `from: activity_name` or derive from activity_id |
| `category_name` | `literal: Network Activity` |
| `category_uid` | `expr: CAST('4' AS INT)` |
| `class_name` | `literal: Network Activity` or DNS Activity / HTTP Activity |
| `class_uid` | `expr: CAST('4001' AS INT)` (4002 http, 4003 dns) |
| `connection_info` | Dotted fields or named_struct; see [ocsf-connection-info](../ocsf_ddl_fields/ocsf-connection-info.md) |
| `disposition` | §1 disposition |
| `disposition_id` | §1 disposition_id |
| `dst_endpoint` | Dotted (e.g. `dst_endpoint.ip`, `dst_endpoint.port`) or §2 src_endpoint shape; [ocsf-endpoint](../ocsf_ddl_fields/ocsf-endpoint.md) |
| `enrichments` | Array of struct (data, desc, name, value); [ocsf-enrichments-observables](../ocsf_ddl_fields/ocsf-enrichments-observables.md) |
| `message` | `from: message` or `from: description` |
| `metadata` | Dotted (e.g. `metadata.version`, `metadata.product.name`) or §2 metadata; [ocsf-metadata](../ocsf_ddl_fields/ocsf-metadata.md) |
| `observables` | §2 Single observables element / array |
| `policy` | Dotted or named_struct (is_applied, name, uid, version) |
| `raw_data` | §2 raw_data |
| `severity` | §1 severity or Syslog 0–7 mapping |
| `severity_id` | §1 severity_id or Syslog 0–7 mapping |
| `src_endpoint` | Dotted or §2 src_endpoint |
| `status` | §1 status (conditions by class; see presets) |
| `status_id` | §1 status_id |
| `status_code` | `from:` vendor code (e.g. conn_state, rcode) |
| `status_detail` | `from:` or class-specific; see presets |
| `time` | `from: time` |
| `timezone_offset` | `expr: CAST(NULL AS INT)` or `from:` |
| `traffic` | Dotted or named_struct; [ocsf-traffic](../ocsf_ddl_fields/ocsf-traffic.md) |
| `type_name` | `expr: "CONCAT('Network Activity: ', activity_name)"` (adjust for DNS/HTTP) |
| `type_uid` | §3 type_uid |
| `unmapped` | §2 unmapped |

### Identity & Access Management (authentication, authorize_session)

| Gold field | Reusable logic |
|------------|----------------|
| `action` | §1 action |
| `action_id` | §1 action_id |
| `activity_id` | Source-specific; [ocsf-ids](../ocsf_ddl_fields/ocsf-ids.md) (auth 300201/300202…, authorize 300399…) |
| `activity_name` | `from: activity_name` or CASE from activity_id |
| `actor` | Dotted or named_struct; [ocsf-iam-common-structs](../ocsf_ddl_fields/ocsf-iam-common-structs.md) |
| `category_name` | `literal: Identity & Access Management` |
| `category_uid` | `expr: CAST('3' AS INT)` |
| `class_name` | `literal: Authentication` or `Authorize Session` |
| `class_uid` | `expr: CAST('3002' AS INT)` (auth) or `CAST('3003' AS INT)` (authorize) |
| `cloud` | Dotted or named_struct; [ocsf-cloud](../ocsf_ddl_fields/ocsf-cloud.md) |
| `dst_endpoint` | Dotted or §2 src_endpoint shape |
| `enrichments` | Array of struct; [ocsf-enrichments-observables](../ocsf_ddl_fields/ocsf-enrichments-observables.md) |
| `message` | `from: message` or `from: description` |
| `metadata` | Dotted or §2 metadata |
| `observables` | §2 observables |
| `raw_data` | §2 raw_data |
| `service` | §2 service or dotted; [ocsf-iam-common-structs](../ocsf_ddl_fields/ocsf-iam-common-structs.md) |
| `session` | Dotted or named_struct; [ocsf-iam-common-structs](../ocsf_ddl_fields/ocsf-iam-common-structs.md) |
| `severity` | §1 severity or Syslog 0–7 |
| `severity_id` | §1 severity_id or Syslog 0–7 |
| `src_endpoint` | Dotted or §2 src_endpoint |
| `status` | §1 status |
| `status_id` | §1 status_id |
| `status_code` / `status_detail` | `from:` as needed |
| `time` | `from: time` |
| `timezone_offset` | `expr: CAST(NULL AS INT)` or `from:` |
| `type_name` | `expr: "CONCAT('Authentication: ', activity_name)"` (or Authorize Session) |
| `type_uid` | §3 type_uid |
| `unmapped` | §2 unmapped |
| `user` | §2 user or dotted |

### System Activity (process_activity)

| Gold field | Reusable logic |
|------------|----------------|
| `action` | §1 action |
| `action_id` | §1 action_id |
| `activity_id` | Source-specific; [ocsf-ids](../ocsf_ddl_fields/ocsf-ids.md) (e.g. 100701 Launch, 100702 Terminate) |
| `activity_name` | `from: activity_name` or derive from activity_id |
| `category_name` | `literal: System Activity` |
| `category_uid` | `expr: CAST('1' AS INT)` |
| `class_name` | `literal: Process Activity` |
| `class_uid` | `expr: CAST('1007' AS INT)` |
| `disposition` | §1 disposition |
| `disposition_id` | §1 disposition_id |
| `message` | `from: message` or `from: description` |
| `metadata` | Dotted or §2 metadata |
| `observables` | §2 observables |
| `raw_data` | §2 raw_data |
| `severity` | §1 severity or Syslog 0–7 |
| `severity_id` | §1 severity_id or Syslog 0–7 |
| `status` | §1 status |
| `status_id` | §1 status_id |
| `status_code` / `status_detail` | `from:` as needed |
| `time` | `from: time` |
| `timezone_offset` | `expr: CAST(NULL AS INT)` or `from:` |
| `type_name` | `expr: "CONCAT('Process Activity: ', activity_name)"` |
| `type_uid` | §3 type_uid |
| `unmapped` | §2 unmapped |

---

**Where:** `gold[].fields[]` with `name` + `expr` / `literal` / `from`. Struct shapes: [ocsf-metadata](../ocsf_ddl_fields/ocsf-metadata.md), [ocsf-endpoint](../ocsf_ddl_fields/ocsf-endpoint.md), [ocsf-iam-common-structs](../ocsf_ddl_fields/ocsf-iam-common-structs.md).
