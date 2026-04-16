# DSL Lite — Lookup Joins Reference

Stream-static joins that enrich raw logs with reference data (geolocation, user directories, threat intel).

---

## Key Features

- **Multiple lookup sources**: Delta tables, CSV, Parquet, JSON files
- **Stream-static joins**: Automatically handles streaming DataFrames with batch lookup tables
- **Column prefixing**: Avoid column name conflicts with `prefix` option
- **Broadcast joins**: Optimize small lookups with `broadcast: true`
- **Multiple join types**: left, inner, right, full
- **Data flow**: Bronze lookup columns → available in silver and gold; Silver lookup columns → available in gold

---

## Configuration Reference

| Option | Description | Default |
|--------|-------------|---------|
| `source.type` | `table` \| `csv` \| `parquet` \| `json` \| `jsonl` | `table` |
| `source.path` | Fully qualified table name (`catalog.database.table`) or volume path | Required |
| `source.format` | File format (required for file sources) | Same as `type` |
| `source.options` | Spark reader options (`header`, `inferSchema`, etc.) | `{}` |
| `join.type` | `left` \| `inner` \| `right` \| `full` | `left` |
| `join.on` | Join conditions — **must be quoted as `"on"` in YAML** | Required |
| `select` | Columns to include from lookup (omit = all columns) | All columns |
| `prefix` | String prepended to all lookup column names | None |
| `broadcast` | Broadcast join for small lookups (< 2GB) | `false` |

> **YAML gotcha**: Always quote `on` as `"on"` in YAML — unquoted `on` is parsed as boolean `True`.

---

## Bronze Layer Lookups

Bronze lookups run after `preTransform` and before silver. Columns are available throughout bronze, silver, and gold.

**Order of operations:** `preTransform` → `dsl_id` (auto) → `lookups` → `postTransform` → `drop`

### Delta Table Lookup

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
        type: table
        path: security_lakehouse.geoip.ip_lookup   # fully qualified UC table
      join:
        type: left
        "on":
          - main.src_ip = lookup.ip_address
          # Multiple conditions are ANDed together:
          # - main.source = lookup.source
          # Simple form (same column name in both tables):
          # - src_ip
      select:
        - country_code
        - city
        - asn
      prefix: "src_geo_"
      broadcast: true
  postTransform:
    - "*"
    - "named_struct('country', src_geo_country_code, 'city', src_geo_city, 'asn', src_geo_asn) as src_geo_location"
  drop:
    - src_geo_country_code
    - src_geo_city
    - src_geo_asn
```

### CSV File Lookup

```yaml
lookups:
  - name: threat_intel
    source:
      type: csv
      path: /Volumes/security/lookups/threat_feeds.csv
      format: csv
      options:
        header: "true"
        inferSchema: "true"
    join:
      type: left
      "on":
        - main.dst_ip = lookup.indicator
    select: [threat_type, severity, feed_name]
    prefix: "threat_"
    broadcast: true
```

---

## Silver Layer Lookups

Silver lookups are useful when the enrichment key is only available after silver parsing.
Silver lookup columns are available in gold.

```yaml
silver:
  transform:
    - name: auth_logs_silver
      lookups:
        - name: user_directory
          source:
            type: csv
            path: /Volumes/security/lookups/employees.csv
            format: csv
            options:
              header: "true"
          join:
            type: left
            "on":
              - main.username = lookup.email
          select: [department, manager, office_location]
          prefix: "user_"
          broadcast: true
      fields:
        - name: user_department
          from: user_department   # reference with prefix
        - name: user_manager
          from: user_manager
```

---

## Using Lookup Columns in Gold

Lookup columns from bronze or silver are available by name in gold `from` and `expr`:

```yaml
gold:
  - name: network_activity
    input: firewall_logs_silver
    fields:
      - name: src_endpoint.ip
        from: src_ip
      - name: src_endpoint.location.country
        from: src_geo_country_code      # bronze lookup column
      - name: src_endpoint.location.city
        from: src_geo_city              # bronze lookup column
      - name: enrichments
        expr: |
          CASE
            WHEN src_geo_asn IS NOT NULL THEN
              ARRAY(NAMED_STRUCT('name', 'ASN', 'type', 'Network', 'value', CAST(src_geo_asn AS STRING)))
            ELSE NULL
          END
```

---

## Multiple Lookups

Multiple lookups on the same table are processed in order:

```yaml
bronze:
  lookups:
    - name: src_geoip
      source:
        type: table
        path: security.geoip.ip_lookup
      join:
        type: left
        "on":
          - main.src_ip = lookup.ip
      select: [country_code, city]
      prefix: "src_geo_"
      broadcast: true
    - name: dst_geoip
      source:
        type: table
        path: security.geoip.ip_lookup
      join:
        type: left
        "on":
          - main.dst_ip = lookup.ip
      select: [country_code, city]
      prefix: "dst_geo_"
      broadcast: true
```

---

## Best Practices

1. **Always use `prefix`** — prevents name conflicts between main DataFrame and lookup tables
2. **Set `broadcast: true` for small lookups** (< 2GB) — significant performance improvement for stream-static joins
3. **Bronze lookups are more efficient** when enrichment is needed in multiple downstream layers
4. **Silver lookups** when the enrichment key is only available after silver parsing (e.g., after REGEXP_EXTRACT)
5. **Use `select`** to limit which lookup columns are included — avoids pulling in unnecessary data
6. **Prefer Delta tables** over CSV for production lookups — better performance and schema management
7. **Use `postTransform` + `drop`** after bronze lookups to build structs from prefixed columns and clean up
