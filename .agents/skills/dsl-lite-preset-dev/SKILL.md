---
name: dsl-lite-preset-dev
description: >
  Develop, modify, and improve DSL Lite data ingestion presets — YAML-based declarative ETL
  pipelines that transform raw security logs through Bronze/Silver/Gold layers into
  OCSF-normalized tables. Use when working with preset.yaml files, adding gold tables, mapping
  events to OCSF classes, adding lookup joins, creating new data sources, or modifying any file
  under pipelines/. Also use when the user mentions presets, data ingestion, OCSF mapping, gold
  tables, silver transforms, bronze layer, or preset.yaml.
---

# DSL Lite Preset Development

## What Is a Preset

A preset is a declarative YAML ETL recipe that defines how raw security logs are ingested and
normalized through three medallion layers into OCSF-compliant tables. Presets live at:

```
pipelines/<source>/<source_type>/preset.yaml
```

For example: `pipelines/cloudflare/gateway_dns/preset.yaml`

The DSL engine reads this YAML and drives Spark Structured Streaming (SSS) or Spark Declarative
Pipelines (SDP) — no Python changes required.

---

## Information Sources (consult in this order)

1. **Existing presets** in `pipelines/` — study similar data sources for patterns
2. **Sample data** in `raw_logs/<source>/<source_type>/` — understand the raw format
3. **OCSF templates** in `ocsf_templates/` — ready-made field lists for all 21 event classes
4. **Preset template** at `pipelines/templates/preset.yaml` — annotated starter template
5. **Architecture doc** at `docs/dsl_lite_features/architecture.md` — layer schemas, data flow
6. **Reference files** bundled with this skill (see below)

---

## Preset YAML Structure

Every preset begins with an identity block — all four keys (`name`, `title`, `description`,
`author`) are required for documentation and attribution.

```yaml
name: <source>_<source_type>           # e.g. cisco_ios
title: "<Display Title>"               # human-readable, e.g. "Cisco IOS"
description: "<short description>"     # e.g. "Cisco IOS syslog events"
author: "<initials>"                   # placeholder — fill in your initials before committing

autoloader:
  inputs:
    - /Volumes/<catalog>/<schema>/raw/<source>/<source_type>/
  format: text | json | csv | parquet
  cloudFiles:                           # text/syslog only
    schemaHints: "value string"

bronze:
  name: <source>_<source_type>_bronze
  # loadAsSingleVariant: true           # JSON or CSV-with-header only
  preTransform:
    -
      - CAST('<source>' AS STRING) AS source
      - CAST('<source_type>' AS STRING) AS sourcetype
      - <timestamp_expr> as time
      - "value"                         # or "data" for JSON/CSV-with-header (loadAsSingleVariant: true)
      # Engine auto-injects: _metadata, record_id, date, processed_time, dsl_id
      # dsl_id is auto-injected by the engine (10th column)
  lookups: []                           # optional enrichment joins
  postTransform: []                     # optional — runs after lookups
  drop: []                              # optional — remove columns by name

silver:
  transform:
    - name: <source>_<source_type>_silver
      filter: <optional predicate>
      fields:
        - name: field_name
          expr: <Spark SQL expression>  # or `from: <column>` or `literal: <value>`
      utils:
        unreferencedColumns:
          preserve: true

gold:
  - name: <ocsf_table_name>            # e.g. network_activity, authentication, dns_activity
    input: <source>_<source_type>_silver
    filter: <optional predicate>
    fields:
      - name: category_uid
        expr: CAST(<N> AS INT)
      # ... OCSF fields
```

See [references/1-preset-structure.md](references/1-preset-structure.md) for the complete annotated structure.

---

## Bronze Layer

The bronze layer does **minimal transformation** — primarily extracting a timestamp and tagging the source. Original data is preserved in `data` (VARIANT, for JSON) or `value` (STRING, for text/syslog).

**`preTransform` requires exactly 4 columns** — source, sourcetype, time, and the payload column. The DSL engine auto-injects `_metadata`, `record_id`, `date`, `processed_time`, and `dsl_id`. See [references/2-bronze-patterns.md](references/2-bronze-patterns.md) for the full schema table.

**Do NOT declare `record_id`, `date`, `_metadata`, `processed_time`, or `dsl_id` in preTransform** — the engine injects them automatically. Duplicates cause pipeline failures.

**JSON source** — use `loadAsSingleVariant: true`:
```yaml
bronze:
  name: vendor_product_bronze
  loadAsSingleVariant: true
  preTransform:
    -
      - CAST('vendor' AS STRING) AS source
      - CAST('product' AS STRING) AS sourcetype
      - CAST(try_variant_get(data, '$.Datetime', 'STRING') AS TIMESTAMP) as time
      - "data"
```

**Text/syslog source** — omit `loadAsSingleVariant`, use `format: text`:
```yaml
autoloader:
  format: text
  cloudFiles:
    schemaHints: "value string"
bronze:
  name: vendor_product_bronze
  preTransform:
    -
      - CAST('vendor' AS STRING) AS source
      - CAST('product' AS STRING) AS sourcetype
      - TO_TIMESTAMP(REGEXP_EXTRACT(value, '(\\w+\\s+\\d+\\s+\\d+\\s+\\d+:\\d+:\\d+)', 1), 'MMM d yyyy HH:mm:ss') as time
      - "value"
```

See [references/2-bronze-patterns.md](references/2-bronze-patterns.md) for timestamp patterns, multi-pass preTransform, and lookup joins.

---

## Silver Layer

Silver extracts structured fields from `data` (JSON VARIANT) or `value` (text/syslog STRING).

**JSON field extraction** — use `try_variant_get` (safe, returns NULL on type mismatch). **The silver `name:` must exactly match the JSON key — preserve case, do not snake_case or rename.** Gold is responsible for renaming to OCSF field paths.
```yaml
- name: QueryName
  expr: try_variant_get(data, '$.QueryName', 'STRING')
- name: SrcPort
  expr: TRY_CAST(try_variant_get(data, '$.SrcPort', 'STRING') AS INT)
```

**Text/syslog extraction** — use `REGEXP_EXTRACT` from `value`. Name fields descriptively in snake_case — there is no source key to preserve, so choose names by semantic meaning (`src_ip`, `facility`, `mnemonic`, etc.):
```yaml
- name: facility
  expr: REGEXP_EXTRACT(value, '^\\d+:\\s+\\w+\\s+\\d+\\s+\\d+\\s+\\d+:\\d+:\\d+:\\s+%(\\w+)', 1)
```

Always use `utils.unreferencedColumns.preserve: true` to pass unmapped columns to gold for `unmapped`/`raw_data`.

**Do NOT re-declare bronze columns in silver `fields:`** — `preserve: true` carries all bronze columns forward automatically. Listing `time`, `date`, `source`, `sourcetype`, `processed_time`, `_metadata`, `record_id`, `dsl_id`, `data`, or `value` in silver produces duplicate columns. Silver `fields:` should contain only columns that are *extracted or derived* from the bronze payload (e.g. parsed fields from `data`/`value`).

See [references/3-silver-patterns.md](references/3-silver-patterns.md) for extraction patterns, type casting rules, REGEXP_EXTRACT gotchas, and multiple-transform routing.

---

## Gold Layer (OCSF Mapping)

Gold maps silver columns to OCSF-compliant field paths. Dot notation builds nested structs automatically (e.g., `src_endpoint.ip` produces the OCSF endpoint struct).

Every gold table requires:
- Base classification fields: `category_uid`, `category_name`, `class_uid`, `class_name`, `type_uid`, `type_name`
- Activity: `activity_id`, `activity_name`
- Severity: `severity_id`, `severity`
- Status: `status_id`, `status`
- Timestamp: `time`, `timezone_offset`
- Metadata block: `metadata.version`, `metadata.product.*`, `metadata.log_provider`, `metadata.log_name`
- Data preservation: `raw_data`, `unmapped`

**TIP**: Copy the fields block from `ocsf_templates/<category>/<table_name>.yaml` instead of writing from scratch — all 21 OCSF event classes have ready-made templates.

See [references/4-gold-ocsf-mapping.md](references/4-gold-ocsf-mapping.md) for the full OCSF table catalog, required fields, enum values, and common patterns.

---

## Lookup Joins

DSL Lite supports stream-static joins at bronze or silver to enrich data with reference tables (IP geolocation, user directories, threat intelligence).

```yaml
bronze:
  lookups:
    - name: ip_geo
      source:
        type: table
        path: security_lakehouse.geoip.ip_lookup
      join:
        type: left
        "on":                           # MUST quote 'on' in YAML
          - main.src_ip = lookup.ip_address
      select: [country_code, city]
      prefix: "geo_"
      broadcast: true
```

See [references/5-lookup-joins.md](references/5-lookup-joins.md) for the full configuration reference.

---

## Reference Files

| File | Contents |
|------|----------|
| [references/1-preset-structure.md](references/1-preset-structure.md) | Complete annotated YAML structure with all options |
| [references/2-bronze-patterns.md](references/2-bronze-patterns.md) | Timestamp patterns, multi-pass preTransform, lookup order of ops |
| [references/3-silver-patterns.md](references/3-silver-patterns.md) | try_variant_get, REGEXP_EXTRACT, TRY_CAST rules, multiple transforms |
| [references/4-gold-ocsf-mapping.md](references/4-gold-ocsf-mapping.md) | OCSF table catalog, required fields, enum values, endpoint patterns |
| [references/5-lookup-joins.md](references/5-lookup-joins.md) | Bronze/silver lookup joins, broadcast, postTransform |
| [references/6-gold-tables.md](references/6-gold-tables.md) | Per-table field listings and struct schemas for all 22 OCSF tables |
| [references/7-preset-patterns.md](references/7-preset-patterns.md) | Advanced patterns: multi-pass transforms, DNS answers, security gateway, unmapped, SQL functions |

---

## Development Workflow

1. **Understand the data** — inspect sample files in `raw_logs/` or vendor documentation
2. **Choose OCSF tables** — determine which gold tables fit the event types
3. **Read ocsf_templates/** — get exact field names and types for target tables
4. **Study similar presets** — find existing presets in `pipelines/` for the same format (JSON/text)
5. **Write autoloader + bronze** — configure ingest format and timestamp extraction
6. **Write silver** — extract all fields needed for gold mapping
7. **Write gold** — map silver columns to OCSF using dot-path notation
8. **Add raw_data + unmapped** — preserve original payload and vendor-specific fields
9. **Test with preset_explorer** — use `notebooks/explorer/preset_explorer.py` to iterate without deploying

---

## Critical Rules

- **Identity block is required on every preset** — `name`, `title`, `description`, and `author` must all appear at the top of `preset.yaml`. Attribution (`author`) is not optional.
- **`loadAsSingleVariant: true`** — JSON or CSV-with-header sources. Stores the entire record as VARIANT in `data`; silver uses `try_variant_get`. For CSV: keys are the header column names — useful when the column set is user-configurable (e.g. AWS VPC Flow Logs v2–v10). Never use for text/syslog — the `value` column won't exist.
- **`"on"` must be quoted** in YAML — unquoted `on` is parsed as boolean `True`
- **Double backslashes in regex** — YAML unquoted strings and `|` block scalars: `\\d`, `\\S`, `\\w`. Avoid double-quoted YAML strings for regex (requires `\\\\d`)
- **`TRY_CAST` for string→type conversions** — returns NULL on failure; use plain `CAST` only for safe conversions (literals, int→string)
- **`try_variant_get` over `data:field::TYPE`** — shorthand `::TYPE` fails on type mismatch; `try_variant_get` returns NULL
- **`to_variant_object()` for `unmapped`** — preferred over `CAST(to_json(...) AS VARIANT)`: produces native VARIANT without JSON round-trip
- **`clusterBy: [time]` on every bronze and silver** — always set explicitly, e.g. `bronze.clusterBy: [time]` and `silver.transform[N].clusterBy: [time]`. Both default to `["time"]` internally but always make it explicit for clarity.
- **`time` must be the first field in every gold table** — Delta liquid clustering requires clustered columns to be within the first 32 columns. Putting `time` first guarantees `ALTER TABLE ... CLUSTER BY (time)` always succeeds without needing `ALTER TABLE ... ALTER COLUMN` to reposition it first.
- **`clusterBy` is SSS mode only** — in SDP mode, run `ALTER TABLE ... CLUSTER BY (time, field)` after pipeline creation
- **`metadata.log_provider` must always be a `literal`** — never use `from: source`. Hardcode the vendor name (e.g. `literal: okta`, `literal: github`). The `source` column is the same value but using a literal makes the intent clear and avoids column dependency.
- **`metadata.log_name` must always be a `literal`** — never use `from: sourcetype`. Hardcode the source type (e.g. `literal: system_log`, `literal: gateway_dns`).
- **Gold table names must match OCSF class names** — check `ocsf_templates/` for the exact name
