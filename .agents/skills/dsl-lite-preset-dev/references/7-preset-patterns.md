# DSL Lite — Advanced Preset Patterns

Detailed patterns and edge cases found across DSL Lite presets. Read the relevant section when
working on a specific type of preset or encountering an unfamiliar pattern.

## Table of Contents

1. [Bronze: Multi-Pass preTransform](#bronze-multi-pass-pretransform)
2. [Bronze: Timestamp Extraction Patterns](#bronze-timestamp-extraction-patterns)
3. [Bronze: loadAsSingleVariant Decision](#bronze-loadassinglevariant-decision)
4. [Silver: Complex Type Extraction](#silver-complex-type-extraction)
5. [Silver: Defensive Guards](#silver-defensive-guards)
6. [Silver: Naming Conventions](#silver-naming-conventions)
7. [Silver: Metadata Forwarded from Silver](#silver-metadata-forwarded-from-silver)
8. [Gold: activity_id and type_uid Patterns](#gold-activity_id-and-type_uid-patterns)
9. [Gold: Network-Specific Fields](#gold-network-specific-fields)
10. [Gold: DNS-Specific Fields](#gold-dns-specific-fields)
11. [Gold: System Activity Fields](#gold-system-activity-fields)
12. [Gold: Security Gateway Fields](#gold-security-gateway-fields)
13. [Gold: unmapped Field](#gold-unmapped-field)
14. [Gold: Schema Completeness with CAST(NULL)](#gold-schema-completeness-with-castnull)
15. [Gold: Multiple Tables from One Silver](#gold-multiple-tables-from-one-silver)
16. [Gold: Useful SQL Functions](#gold-useful-sql-functions)

---

## Bronze: Multi-Pass preTransform

`preTransform` is a list of lists — each inner list is a `selectExpr` pass, with its output
feeding the next pass. Use multi-pass when you need to explode or reshape before extracting
timestamps:

```yaml
bronze:
  preTransform:
    -                                      # pass 1: explode top-level array
      - explode(records) as data
    -                                      # pass 2: extract from exploded records
      - CAST('vendor' AS STRING) AS source
      - CAST('logtype' AS STRING) AS sourcetype
      - try_variant_get(data, '$.time', 'TIMESTAMP') as time
      - "data"
      # Engine auto-injects: _metadata, record_id, date, processed_time, dsl_id
```

Requires `cloudFiles.schemaHints: "records ARRAY<VARIANT>"` in autoloader so the top-level
records field is correctly typed before the explode.

---

## Bronze: Timestamp Extraction Patterns

Different source formats require different timestamp extraction approaches:

| Pattern | When to Use | Example Source |
|---------|-------------|----------------|
| `CAST(try_variant_get(data, '$.ts', 'TIMESTAMP') AS TIMESTAMP)` | JSON ISO/RFC timestamp field | Zeek |
| `CAST(try_variant_get(data, '$.Datetime', 'STRING') AS TIMESTAMP)` | JSON string timestamp | Cloudflare |
| `CAST(try_variant_get(data, '$.ts', 'DOUBLE') AS TIMESTAMP)` | JSON unix epoch (seconds as float) | Zeek alt |
| `CAST(try_variant_get(data, '$.ts', 'LONG') / 1000.0 AS TIMESTAMP)` | JSON unix epoch milliseconds | Various |
| `TO_TIMESTAMP(REGEXP_EXTRACT(value, '(\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2})', 1), 'yyyy-MM-dd''T''HH:mm:ss')` | ISO 8601 in syslog | Cisco IOS |
| `TO_TIMESTAMP(REGEXP_EXTRACT(value, '(\\w+ +\\d+ +\\d{4} +\\d+:\\d+:\\d+)', 1), 'MMM d yyyy HH:mm:ss')` | Syslog `MMM D YYYY HH:mm:ss` | Cisco |
| `TO_TIMESTAMP(field_name, 'yyyy-MM-dd HH:mm:ss')` | CSV with custom format string | Umbrella CSV |

**Multi-field COALESCE** — when a source has multiple possible timestamp fields or formats:

```yaml
- COALESCE(
    CAST(try_variant_get(data, '$.Timestamp', 'STRING') AS TIMESTAMP),
    CAST(try_variant_get(data, '$.ts', 'DOUBLE') AS TIMESTAMP),
    CURRENT_TIMESTAMP()
  ) as time
```

Always include `CURRENT_TIMESTAMP()` as the final fallback so rows are never dropped due to
timestamp parse failure.

---

## Bronze: loadAsSingleVariant Decision

| Source format | Setting | Raw data column |
|---------------|---------|----------------|
| JSON (one object per line) | `loadAsSingleVariant: true` | `data` (VARIANT) |
| Text / syslog | Omit entirely | `value` (STRING) |
| CSV | Omit; use `format: csv` | Individual columns per header |
| JSON array (top-level) | Omit; use `schemaHints` + explode in preTransform | `data` (VARIANT after explode) |

When using `loadAsSingleVariant: true`, reference fields with `try_variant_get(data, '$.field', 'TYPE')`.

When working with text/syslog, use `REGEXP_EXTRACT(value, 'pattern', group)`.

**Never** mix the two — if you write `try_variant_get(value, ...)` on a syslog preset or
`REGEXP_EXTRACT(data, ...)` on a JSON preset, the pipeline will fail.

---

## Silver: Complex Type Extraction

Beyond basic scalar `try_variant_get`, silver can extract complex types:

```yaml
# ARRAY of scalars
- name: resolved_ips
  expr: try_variant_get(data, '$.ResolvedIPs', 'ARRAY<STRING>')

# Nested parse: extract JSON string then parse with from_json
- name: rdata_records
  expr: from_json(try_variant_get(data, '$.RData', 'STRING'), 'ARRAY<MAP<STRING,STRING>>')

# MAP extraction
- name: metadata_map
  expr: try_variant_get(data, '$.Metadata', 'MAP<STRING,STRING>')

# STRUCT cast (alternative for known schemas)
- name: geo_data
  expr: TRY_CAST(data:geoip AS STRUCT<country: STRING, city: STRING, lat: FLOAT>)

# Keys with dots in the name — use bracket syntax
- name: orig_host
  expr: CAST(data:['id.orig_h'] AS STRING)

# Nested object extraction (note path separator is '.')
- name: category_name
  expr: try_variant_get(data, '$.categories[0].name', 'STRING')
```

**REGEXP_EXTRACT in silver** (text sources — extract from already-parsed silver if simpler than
doing it in bronze):

```yaml
- name: facility
  expr: REGEXP_EXTRACT(value, '^%(\\w+)-(\\d+)-(\\w+)', 3)
- name: mnemonic
  expr: REGEXP_EXTRACT(value, '^%(\\w+)-(\\d+)-(\\w+)', 3)
```

Double-backslash rule: in unquoted YAML or `|` block scalars, write `\\d` not `\\\\d`. Avoid
double-quoted YAML strings for regex — they require quadruple backslashes.

---

## Silver: Defensive Guards

Add `filter: data IS NOT NULL` to silver transforms to guard against null rows from
malformed or empty files (common with JSON autoloader):

```yaml
silver:
  transform:
    - name: vendor_events_silver
      filter: data IS NOT NULL
      fields: [...]
```

For text sources, guard against empty lines:
```yaml
filter: value IS NOT NULL AND LENGTH(TRIM(value)) > 0
```

---

## Silver: Naming Conventions

- Use **snake_case** for silver column names: `src_ip`, `dst_port`, `event_type`
- Avoid naming a silver column `source` — it conflicts with the bronze reserved column that
  holds the preset's `source` value. Rename the vendor field (e.g., use `src` or `origin`)
- Use **TRY_CAST** for all string → numeric/boolean/timestamp conversions. Use plain **CAST**
  only for literals (`CAST(6 AS INT)`) or guaranteed-safe conversions (INT → STRING)
- Wrap `REGEXP_EXTRACT` with `NULLIF(..., '')` when the result is used in a COALESCE —
  `REGEXP_EXTRACT` returns `""` not NULL on no-match:
  ```yaml
  expr: NULLIF(REGEXP_EXTRACT(value, 'field=(\\S+)', 1), '')
  ```

---

## Silver: Metadata Forwarded from Silver

For presets with multiple gold tables (one silver → several OCSF tables), compute shared metadata
fields once in silver and forward the entire `metadata` struct to each gold table:

```yaml
# Silver: compute metadata fields once
silver:
  transform:
    - name: vendor_silver
      fields:
        - name: metadata.event_code
          from: mnemonic
        - name: metadata.log_provider
          literal: vendor_source
        - name: metadata.log_name
          literal: vendor_sourcetype
        - name: metadata.product.name
          literal: "Product Name"
        - name: metadata.product.vendor_name
          literal: "Vendor Name"
        - name: metadata.log_format
          literal: JSON
        - name: metadata.log_version
          literal: "vendor_source@vendor_sourcetype:version@1.0"
        - name: metadata.processed_time
          expr: CURRENT_TIMESTAMP()
        - name: metadata.logged_time
          from: time
        - name: metadata.version
          literal: "1.7.0"

# Gold: forward the entire struct — no need to repeat in each table
gold:
  - name: authentication
    input: vendor_silver
    fields:
      - name: metadata
        from: metadata   # forward entire struct
      # ... other fields
  - name: network_activity
    input: vendor_silver
    fields:
      - name: metadata
        from: metadata
      # ... other fields
```

This avoids repeating the same 10+ metadata lines in every gold table block.

---

## Gold: activity_id and type_uid Patterns

Every gold table requires `activity_id`, `activity_name`, `type_uid`, and `type_name`.

**Static activity** (source has only one type of event):
```yaml
- name: activity_id
  expr: CAST(1 AS INT)
- name: activity_name
  literal: Open
- name: type_uid
  expr: CAST(class_uid * 100 + activity_id AS BIGINT)
- name: type_name
  expr: CONCAT('Network Activity: ', activity_name)
```

**Dynamic activity** (map vendor action to OCSF activity_id):
```yaml
- name: activity_id
  expr: |
    CAST(CASE
      WHEN event_type = 'connect' THEN 1
      WHEN event_type = 'disconnect' THEN 2
      WHEN event_type = 'send' THEN 3
      ELSE 99
    END AS INT)
- name: activity_name
  expr: |
    CASE
      WHEN activity_id = 1 THEN 'Open'
      WHEN activity_id = 2 THEN 'Close'
      WHEN activity_id = 3 THEN 'Send'
      ELSE 'Other'
    END
- name: type_uid
  expr: CAST(4001 * 100 + activity_id AS BIGINT)
- name: type_name
  expr: CONCAT('Network Activity: ', activity_name)
```

> Use hard-coded class_uid (e.g. `4001`) in `type_uid` expr — `class_uid` column may not be
> available in expr context.

---

## Gold: Network-Specific Fields

For `network_activity`, `http_activity`, `dns_activity`:

```yaml
# Protocol name and number
- name: connection_info.protocol_name
  expr: LOWER(protocol)
- name: connection_info.protocol_num
  expr: |
    CAST(CASE
      WHEN LOWER(protocol) = 'tcp' THEN 6
      WHEN LOWER(protocol) = 'udp' THEN 17
      WHEN LOWER(protocol) = 'icmp' THEN 1
      ELSE NULL
    END AS INT)

# IP version detection
- name: connection_info.protocol_ver_id
  expr: |
    CAST(CASE
      WHEN src_ip LIKE '%:%' THEN 6   -- IPv6 contains colons
      WHEN src_ip IS NOT NULL THEN 4   -- IPv4
      ELSE NULL
    END AS INT)

# Connection direction (when vendor doesn't provide it)
- name: connection_info.direction_id
  expr: CAST(0 AS INT)    # 0=Unknown when not available

# Cloud context (for cloud-sourced logs)
- name: cloud.provider
  literal: aws
- name: cloud.region
  from: aws_region
- name: cloud.account.uid
  from: account_id
```

---

## Gold: DNS-Specific Fields

For `dns_activity` gold tables:

```yaml
# DNS response code mapping
- name: rcode_id
  expr: |
    CAST(CASE
      WHEN RCode = 0 THEN 0   -- NoError
      WHEN RCode = 1 THEN 1   -- FormError
      WHEN RCode = 2 THEN 2   -- ServError
      WHEN RCode = 3 THEN 3   -- NXDomain
      WHEN RCode = 5 THEN 5   -- Refused
      ELSE 99
    END AS INT)
- name: rcode
  expr: |
    CASE
      WHEN rcode_id = 0 THEN 'NoError'
      WHEN rcode_id = 3 THEN 'NXDomain'
      WHEN rcode_id = 5 THEN 'Refused'
      ELSE 'Other'
    END

# DNS answers — Pattern 1: parallel arrays (answers and TTLs as separate arrays)
- name: answers
  expr: |
    TRANSFORM(arrays_zip(answer_ips, answer_ttls),
      x -> NAMED_STRUCT('rdata', x.answer_ips, 'ttl', TRY_CAST(x.answer_ttls AS INT)))

# DNS answers — Pattern 2: ResourceRecordsJSON (array of maps)
- name: answers
  expr: |
    CASE
      WHEN ResourceRecordsJSON IS NOT NULL AND size(ResourceRecordsJSON) > 0 THEN
        TRANSFORM(ResourceRecordsJSON,
          rr -> NAMED_STRUCT(
            'class', CAST(rr['class'] AS STRING),
            'type', CAST(rr['type'] AS STRING),
            'rdata', CAST(rr['rdata'] AS STRING),
            'ttl', TRY_CAST(rr['ttl'] AS INT),
            'packet_uid', CAST(NULL AS INT),
            'flag_ids', CAST(NULL AS ARRAY<INT>),
            'flags', CAST(NULL AS ARRAY<STRING>)
          ))
      ELSE NULL
    END

# DNS answers — Pattern 3: semicolon-delimited IP strings
- name: answers
  expr: |
    CONCAT(
      TRANSFORM(array_remove(SPLIT(COALESCE(ipv4_answers, ''), ';'), ''),
        x -> NAMED_STRUCT('class', 'IN', 'type', 'A', 'rdata', x,
                          'ttl', CAST(NULL AS INT))),
      TRANSFORM(array_remove(SPLIT(COALESCE(cname_answers, ''), ';'), ''),
        x -> NAMED_STRUCT('class', 'IN', 'type', 'CNAME', 'rdata', x,
                          'ttl', CAST(NULL AS INT)))
    )
```

---

## Gold: System Activity Fields

For `process_activity`, `file_activity`, `script_activity` — use `device.*` instead of
`src_endpoint.*`/`dst_endpoint.*` to describe the host:

```yaml
- name: device.hostname
  from: hostname
- name: device.ip
  from: agent_ip
- name: device.uid
  from: device_id

# File hashes (for file_activity and process_activity)
- name: file.hashes
  expr: |
    CASE WHEN sha256 IS NOT NULL THEN
      ARRAY(NAMED_STRUCT('algorithm_id', CAST(3 AS INT), 'algorithm', 'SHA-256', 'value', sha256))
    ELSE
      CAST(NULL AS ARRAY<STRUCT<algorithm_id: INT, algorithm: STRING, value: STRING>>)
    END

# Process tree (for process_activity)
- name: process.name
  from: process_name
- name: process.pid
  expr: TRY_CAST(pid AS INT)
- name: process.cmd_line
  from: cmd_line
- name: process.parent_process.name
  from: parent_process_name
- name: process.parent_process.pid
  expr: TRY_CAST(parent_pid AS INT)
- name: actor.user.name
  from: user_name
```

---

## Gold: Security Gateway Fields

For firewalls, WAFs, and security controls that make allow/deny decisions:

```yaml
# Policy that triggered the action
- name: policy.name
  from: rule_name
- name: policy.uid
  from: rule_id
- name: policy.is_applied
  expr: CAST(rule_id IS NOT NULL AS BOOLEAN)

# Action taken by the security control
- name: action_id
  expr: |
    CAST(CASE
      WHEN action = 'allow' THEN 1
      WHEN action IN ('block', 'deny', 'drop') THEN 2
      ELSE 0
    END AS INT)
- name: action
  expr: |
    CASE
      WHEN action_id = 1 THEN 'Allowed'
      WHEN action_id = 2 THEN 'Denied'
      ELSE 'Unknown'
    END

# Disposition (outcome) — use alongside action for richer classification
- name: disposition_id
  expr: |
    CAST(CASE
      WHEN action = 'allow' THEN 1     -- Allowed
      WHEN action = 'block' THEN 2     -- Blocked
      WHEN action = 'monitor' THEN 17  -- Logged
      WHEN action = 'alert' THEN 19    -- Alert
      ELSE 0
    END AS INT)

# Enrichments from threat intel or category matching
- name: enrichments
  expr: |
    CASE
      WHEN category IS NOT NULL OR threat_feed IS NOT NULL THEN
        FILTER(ARRAY(
          CASE WHEN category IS NOT NULL THEN
            NAMED_STRUCT('name', 'Matched Category', 'desc', CAST(NULL AS STRING),
                         'data', CAST(NULL AS VARIANT), 'value', category)
          ELSE NULL END,
          CASE WHEN threat_feed IS NOT NULL THEN
            NAMED_STRUCT('name', 'Matched Threat Feed', 'desc', CAST(NULL AS STRING),
                         'data', CAST(NULL AS VARIANT), 'value', threat_feed)
          ELSE NULL END
        ), x -> x IS NOT NULL)
      ELSE NULL
    END
```

---

## Gold: unmapped Field

Capture vendor-specific fields that don't have an OCSF equivalent. Only include fields that have
security or operational value — don't dump every column.

**Preferred pattern** — `to_variant_object`:

```yaml
- name: unmapped
  expr: |
    to_variant_object(named_struct(
      'vendor_field_1', vendor_field_1,
      'vendor_field_2', vendor_field_2,
      'vendor_field_3', vendor_field_3
    ))
```

**Alternative** — JSON serialization (older pattern, still works):

```yaml
- name: unmapped
  expr: |
    CAST(to_json(named_struct(
      'vendor_field_1', vendor_field_1,
      'vendor_field_2', vendor_field_2
    )) AS VARIANT)
```

`to_variant_object` is preferred: it produces a native VARIANT without a JSON round-trip and
avoids quoting edge cases with special characters in field values.

---

## Gold: Schema Completeness with CAST(NULL)

Use `CAST(NULL AS type)` when a column must exist in the schema but has no data from this source.
This ensures tables written by multiple pipelines maintain consistent schemas.

```yaml
# Scalar nulls
- name: connection_info.direction_id
  expr: CAST(NULL AS INT)
- name: dst_endpoint.instance_uid
  expr: CAST(NULL AS STRING)
- name: metadata.tags
  expr: CAST(NULL AS VARIANT)
- name: timezone_offset
  expr: CAST(NULL AS INT)

# Struct null (when the entire struct is unavailable)
- name: dst_endpoint.location
  expr: |
    named_struct(
      'city', CAST(NULL AS STRING),
      'continent', CAST(NULL AS STRING),
      'country', CAST(NULL AS STRING),
      'lat', CAST(NULL AS FLOAT),
      'long', CAST(NULL AS FLOAT),
      'postal_code', CAST(NULL AS STRING)
    )

# Array null
- name: file.hashes
  expr: CAST(NULL AS ARRAY<STRUCT<algorithm_id: INT, algorithm: STRING, value: STRING>>)
```

Only add CAST(NULL) fields when schema consistency across multiple presets writing to the same
gold table is required. For standalone presets, omit fields that have no data.

---

## Gold: Multiple Tables from One Silver

One silver table can produce multiple OCSF gold tables — each with its own `filter`:

```yaml
gold:
  - name: authentication
    input: cisco_ios_silver
    filter: (facility IN ('AAA', 'SEC_LOGIN') AND mnemonic LIKE 'LOGIN%') OR (facility = 'SYS' AND mnemonic = 'LOGOUT')
    fields:
      - name: category_uid
        expr: CAST(3 AS INT)
      # ... authentication fields

  - name: authorize_session
    input: cisco_ios_silver
    filter: mnemonic IN ('EXEC_FAILED', 'CLI_DENIED', 'ACCESS_DENIED')
    fields:
      - name: category_uid
        expr: CAST(3 AS INT)
      # ... authorize_session fields

  - name: network_activity
    input: cisco_ios_silver
    filter: facility IN ('LINK', 'LINEPROTO', 'ETHCNTR')
    fields:
      - name: category_uid
        expr: CAST(4 AS INT)
      # ... network_activity fields
```

All filter conditions use silver column names. Rows not matching any filter are silently dropped
(no error, no dead-letter). If a row should map to exactly one table, make filters mutually
exclusive.

---

## Gold: Useful SQL Functions

Common Spark SQL functions used across presets:

| Function | Purpose | Example |
|----------|---------|---------|
| `CONCAT_WS(' ', a, b)` | Null-safe string join | `CONCAT_WS(': ', class_name, activity_name)` |
| `ELEMENT_AT(array, 1)` | Get array element by 1-based index | `ELEMENT_AT(resolved_ips, 1)` |
| `array_remove(array, '')` | Remove empty strings from array | After `SPLIT(field, ';')` |
| `arrays_zip(a, b)` | Zip parallel arrays into array of structs | DNS answers + TTLs |
| `from_json(str, schema)` | Parse JSON string to typed struct/array | After `try_variant_get(..., 'STRING')` |
| `from_csv(str, schema)` | Parse CSV string to struct | CSV embedded in JSON fields |
| `TRANSFORM(array, x -> ...)` | Map function over array | Building DNS answers array |
| `FILTER(array, x -> ...)` | Filter array elements | Remove NULL enrichments |
| `NAMED_STRUCT('k', v, ...)` | Build struct inline | Observables, enrichments |
| `COALESCE(a, b, c)` | First non-null value | Multi-field timestamp fallback |
| `NULLIF(expr, '')` | Convert empty string to NULL | After REGEXP_EXTRACT |
| `LOWER(str)` | Lowercase string | Protocol names in connection_info |
| `TRY_CAST(x AS T)` | Safe cast — returns NULL on failure | String → INT/BOOLEAN/TIMESTAMP |
| `REGEXP_EXTRACT(str, pat, grp)` | Extract regex capture group | Syslog field parsing |
| `CURRENT_TIMESTAMP()` | Pipeline processing time | `metadata.processed_time` |
| `size(array)` | Array length | Guard before TRANSFORM |
