# DSL Lite — Lookup Joins

DSL Lite supports joining bronze and silver tables with lookup tables or CSV files to enrich data with reference information (e.g., IP geolocation, user mappings, threat intelligence).

---

## Key Features

- **Multiple lookup sources**: Delta tables, CSV, Parquet, JSON files
- **Stream-static joins**: Automatically handles streaming DataFrames with batch lookup tables
- **Column prefixing**: Avoid column name conflicts with `prefix` option
- **Broadcast joins**: Optimize small lookups with `broadcast: true`
- **Multiple join types**: left, inner, right, full
- **Data flow**: Lookup columns from bronze are available in silver and gold; lookup columns from silver are available in gold

---

## Bronze Layer Lookup

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
          # For two (or more) columns, list multiple conditions (ANDed together):
          # - main.source = lookup.source
          # - main.sourcetype = lookup.sourcetype
          # Or simple: - source   and   - sourcetype
      select:                        # Optional: which columns to include from lookup
        - country_code
        - city
        - asn
      prefix: "src_geo_"             # Optional: prefix for lookup columns
      broadcast: true                # Optional: use broadcast join for small lookups
  # Optional: transform after lookups (e.g. build a struct from lookup columns)
  postTransform:
    - "*"   # Keep all columns
    - "named_struct('country', src_geo_country_code, 'city', src_geo_city) as src_geo_location"
```

**Bronze order of operations:** `preTransform` → `dsl_id` → lookups → `postTransform` → `drop`. Use `postTransform` to add expressions that use lookup columns (e.g. `named_struct`). Include `"*"` first to keep existing columns, then add new expressions. Use **`drop`** to remove columns by name (e.g. after folding lookup columns into a struct):

```yaml
bronze:
  postTransform:
    - "*"
    - "named_struct('country', src_geo_country_code, 'city', src_geo_city) as src_geo_location"
  drop:
    - src_geo_country_code
    - src_geo_city
```

---

## Silver Layer Lookup

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

---

## Using Lookup Columns in Gold

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

---

## Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `source.type` | Lookup source type: `table`, `csv`, `parquet`, `json`, `jsonl` | `table` |
| `source.path` | Fully qualified table name (`catalog.database.table`) or file path | Required |
| `source.format` | File format (required for file sources) | Same as `type` |
| `source.options` | File read options (e.g., `header: "true"`, `inferSchema: "true"`) | `{}` |
| `join.type` | Join type: `left`, `inner`, `right`, `full` | `left` |
| `join.on` | List of join condition(s); multiple conditions are ANDed. Use `main.<col> = lookup.<col>` or a single column name (same name in both). **Must be quoted as `"on"` in YAML** to avoid being interpreted as boolean `True`. | Required |
| `select` | Columns to include from lookup (if omitted, all columns included) | All columns |
| `prefix` | Prefix for lookup columns to avoid conflicts | None |
| `broadcast` | Use broadcast join for small lookups (< 2GB) | `false` |

---

## Best Practices

1. **Use `prefix`** to avoid column name conflicts between main DataFrame and lookup tables
2. **Set `broadcast: true`** for small lookups (< 2GB) to improve performance
3. **Bronze lookups** are more efficient when enrichment is needed in multiple downstream layers
4. **Silver lookups** are useful when enrichment depends on parsed/structured data
5. **Multiple lookups** are processed in order specified in YAML
