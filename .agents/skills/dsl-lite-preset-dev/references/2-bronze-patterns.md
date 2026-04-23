# DSL Lite — Bronze Layer Patterns

Deep reference for bronze layer configuration.

---

## Standard 10-Column Bronze Schema

Every bronze `preTransform` must produce **exactly these 8 columns**. The DSL engine automatically appends `dsl_id` to make the final table 9 columns wide — consistent across every preset:

| # | Column | Type | Where it comes from |
|---|--------|------|---------------------|
| 1 | `record_id` | STRING | `md5(concat_ws('_', to_json(data), _metadata.file_name)) as record_id` (JSON) or `md5(concat_ws('_', value, _metadata.file_name)) as record_id` (text) |
| 2 | `source` | STRING | `CAST('<vendor>' AS STRING) as source` |
| 3 | `sourcetype` | STRING | `CAST('<product>' AS STRING) as sourcetype` |
| 4 | `time` | TIMESTAMP | Extracted from payload — see patterns below |
| 5 | `date` | DATE | `CAST(time AS DATE) as date` |
| 6 | `data` / `value` | VARIANT / STRING | `"data"` (JSON) or `"*"` (text) — raw payload |
| 7 | `_metadata` | STRUCT | `"_metadata"` — contains `file_name`, `file_path`, `file_size`, `file_modification_time` |
| 9 | `processed_time` | TIMESTAMP | `CURRENT_TIMESTAMP() as processed_time` |
| 10 | `dsl_id` | STRING | **Auto-injected by DSL engine** — do NOT add to preTransform |

Do not add extra columns (e.g. `host`, `query`, extracted fields) to bronze `preTransform` — put those in silver.

---

## loadAsSingleVariant Decision

| Format | loadAsSingleVariant | Data column |
|--------|--------------------|-----------  |
| JSON / JSONL | `true` | `data VARIANT` — entire record as Variant |
| Text / Syslog | omit | `value STRING` — raw line |
| CSV with header | omit (use `cloudFiles.header: true`) | named columns |
| CSV without header | omit | `_c0`, `_c1`, … |

**Never** set `loadAsSingleVariant: true` for text/syslog — the `value` column won't exist.

---

## Timestamp Extraction Patterns

| Source Format | Timestamp Pattern | Preset Expression |
|---------------|-------------------|-------------------|
| JSON ISO string | `"Datetime": "2024-01-15T12:00:00Z"` | `CAST(try_variant_get(data, '$.Datetime', 'STRING') AS TIMESTAMP)` |
| JSON timestamp type | `"ts": 1705312800.0` | `CAST(try_variant_get(data, '$.ts', 'TIMESTAMP') AS TIMESTAMP)` |
| JSON unix epoch (seconds, double) | `"ts": 1705312800.5` | `CAST(try_variant_get(data, '$.ts', 'DOUBLE') AS TIMESTAMP)` |
| JSON unix epoch (milliseconds, long) | `"timestamp": 1705312800123` | `CAST(try_variant_get(data, '$.timestamp', 'LONG') / 1000.0 AS TIMESTAMP)` |
| Syslog `MMM D YYYY HH:mm:ss` | `Jan  5 2024 12:00:00` | `TO_TIMESTAMP(REGEXP_EXTRACT(value, '(\\w+\\s+\\d+\\s+\\d+\\s+\\d+:\\d+:\\d+)', 1), 'MMM d yyyy HH:mm:ss')` |
| ISO 8601 in syslog | `2024-01-05T12:00:00` | `TO_TIMESTAMP(REGEXP_EXTRACT(value, '(\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2})', 1), 'yyyy-MM-dd''T''HH:mm:ss')` |
| CEF/RFC3164 syslog | `Jan 05 12:00:00` | `TO_TIMESTAMP(REGEXP_EXTRACT(value, '(\\w{3}\\s+\\d{1,2}\\s+\\d{2}:\\d{2}:\\d{2})', 1), 'MMM d HH:mm:ss')` |

**COALESCE for multiple timestamp candidates** (when a source has schema variation):
```yaml
- COALESCE(
    CAST(try_variant_get(data, '$.ContextTimeStamp', 'DOUBLE') AS TIMESTAMP),
    CAST(try_variant_get(data, '$.timestamp', 'TIMESTAMP') AS TIMESTAMP),
    CAST(try_variant_get(data, '$.ts', 'LONG') / 1000.0 AS TIMESTAMP),
    CURRENT_TIMESTAMP()
  ) as time
```

**Cisco IOS syslog** (complete bronze preTransform — 9-column standard):
```yaml
bronze:
  name: cisco_ios_bronze
  preTransform:
    -
      - md5(concat_ws('_', value, _metadata.file_name)) as record_id
      - CAST('cisco' AS STRING) AS source
      - CAST('ios' AS STRING) AS sourcetype
      - TO_TIMESTAMP(REGEXP_EXTRACT(value, '(\\w+\\s+\\d+\\s+\\d+\\s+\\d+:\\d+:\\d+)', 1), 'MMM d yyyy HH:mm:ss') as time
      - CAST(time AS DATE) as date
      - "*"
      - "_metadata"
      - CURRENT_TIMESTAMP() as processed_time
```

**Cloudflare Gateway DNS** (complete bronze preTransform — 9-column standard):
```yaml
bronze:
  name: cloudflare_gateway_dns_bronze
  loadAsSingleVariant: true
  preTransform:
    -
      - md5(concat_ws('_', to_json(data), _metadata.file_name)) as record_id
      - CAST('cloudflare' AS STRING) as source
      - CAST('gateway_dns' AS STRING) as sourcetype
      - CAST(try_variant_get(data, '$.Datetime', 'STRING') AS TIMESTAMP) as time
      - CAST(time AS DATE) as date
      - "data"
      - "_metadata"
      - CURRENT_TIMESTAMP() as processed_time
```

---

## Multi-Pass preTransform

`preTransform` is a **list of lists** — each inner list is one `selectExpr()` pass; the output feeds the next. Use when you need to explode an array before extracting timestamps.

```yaml
bronze:
  preTransform:
    -                                      # Pass 1: explode top-level array
      - explode(records) as data
    -                                      # Pass 2: extract from each record
      - "data"
      - try_variant_get(data, '$.time', 'TIMESTAMP') as time
      - CAST('vendor' AS STRING) AS source
      - CAST('product' AS STRING) AS sourcetype
      - CURRENT_TIMESTAMP() as processed_time
```

Pair this with `cloudFiles.schemaHints` when the top-level field is a typed array:
```yaml
autoloader:
  format: json
  cloudFiles:
    schemaHints: "records ARRAY<VARIANT>"
```

---

## Lookup Joins (Bronze)

Bronze lookups are stream-static joins. They run **after** `preTransform` and before silver.
Bronze lookup columns are available in both silver and gold.

**Order of operations:** `preTransform` → `dsl_id` auto-generated → `lookups` → `postTransform` → `drop`

```yaml
bronze:
  name: firewall_logs_bronze
  preTransform:
    -
      - "*"
      - REGEXP_EXTRACT(value, 'src_ip=(\\S+)', 1) as src_ip
  lookups:
    - name: ip_geolocation
      source:
        type: table                   # table | csv | parquet | json | jsonl
        path: security.geoip.ip_lookup
      join:
        type: left                    # left | inner | right | full
        "on":                         # MUST quote 'on' in YAML
          - main.src_ip = lookup.ip_address
          # Multiple conditions are ANDed:
          # - main.source = lookup.source
          # Simple (same column name in both tables):
          # - src_ip
      select:                         # optional — limit which lookup columns to include
        - country_code
        - city
        - asn
      prefix: "geo_"                 # optional — prepended to lookup column names
      broadcast: true                # optional — for small lookups <2GB
  postTransform:
    - "*"
    - "named_struct('country', geo_country_code, 'city', geo_city) as src_geo_location"
  drop:
    - geo_country_code
    - geo_city
```

**File-based lookups:**
```yaml
source:
  type: csv
  path: /Volumes/security/lookups/geoip.csv
  format: csv
  options:
    header: "true"
    inferSchema: "true"
```

---

## Auto-Generated Fields

The DSL engine automatically adds these to every bronze table:
- `dsl_id STRING` — unique identifier per row (hex timestamp + UUID fragment). Use for deduplication and lineage tracking. Do NOT define `dsl_id` manually in your preTransform.

---

## Common Bronze Anti-Patterns

| Anti-Pattern | Fix |
|--------------|-----|
| `loadAsSingleVariant: true` on text format | Remove — text always puts the line in `value` |
| Defining `dsl_id` in preTransform | Remove — the engine generates it automatically |
| Complex parsing in preTransform | Move regex/variant extraction to silver |
| Missing `"*"` or `"data"` as first select item | Columns will be dropped — always include it |
