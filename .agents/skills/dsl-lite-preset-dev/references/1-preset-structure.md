# DSL Lite — Complete Preset YAML Structure Reference

Full annotated reference for all preset.yaml options. Delete or comment sections you don't need.

---

```yaml
# ── Identity ───────────────────────────────────────────────────────────────────
# All four identity keys are REQUIRED — documentation + attribution.
name: <source>_<source_type>           # machine name, e.g. cisco_ios
title: "<Display Title>"               # human-readable, e.g. "Cisco IOS"
description: "<short description>"     # e.g. "Cisco IOS syslog events"
author: "<handle>"                     # attribution, e.g. "grp"


# ── Auto Loader ────────────────────────────────────────────────────────────────
autoloader:
  inputs:
    - /Volumes/<catalog>/<schema>/raw/<source>/<source_type>/   # CHANGE ME

  # Text / syslog ───────────────────────────────────────────────────────────────
  format: text
  cloudFiles:
    schemaHints: "value string"         # raw line stored in `value` column

  # JSON (one object per line) ──────────────────────────────────────────────────
  # format: json

  # CSV ─────────────────────────────────────────────────────────────────────────
  # format: csv
  # cloudFiles:
  #   header: true                       # first row is header

  # CSV without header (access columns as _c0, _c1, …) ─────────────────────────
  # format: csv


# ── Bronze ─────────────────────────────────────────────────────────────────────
bronze:
  name: <source>_<source_type>_bronze
  clusterBy: [time]             # always include — ensures time-ordered writes

  # JSON ONLY — keeps the entire JSON record as a VARIANT column named `data`
  # Omit for text/syslog (raw line → `value` STRING) and CSV
  # loadAsSingleVariant: true

  # preTransform is a list of lists.
  # Each inner list is one selectExpr() pass; output feeds the next pass.
  # Most presets need only one pass.
  preTransform:
    -
      - "*"                             # pass all Auto Loader columns forward
      # OR for JSON with loadAsSingleVariant:
      # - "data"

      - "_metadata.file_path"           # source file path for debugging

      # ── Timestamp extraction ──────────────────────────────────────────────────
      # Pick ONE of the patterns below; adjust to match your log's timestamp.

      # ISO 8601 in syslog text
      - TO_TIMESTAMP(REGEXP_EXTRACT(value, '(\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2})', 1), 'yyyy-MM-dd''T''HH:mm:ss') as time
      # Syslog MMM D YYYY HH:mm:ss
      # - TO_TIMESTAMP(REGEXP_EXTRACT(value, '(\\w+\\s+\\d+\\s+\\d+\\s+\\d+:\\d+:\\d+)', 1), 'MMM d yyyy HH:mm:ss') as time
      # JSON ISO string
      # - CAST(try_variant_get(data, '$.Datetime', 'STRING') AS TIMESTAMP) as time
      # JSON timestamp type (already a timestamp)
      # - CAST(try_variant_get(data, '$.ts', 'TIMESTAMP') AS TIMESTAMP) as time
      # JSON unix epoch (seconds as double)
      # - CAST(try_variant_get(data, '$.ts', 'DOUBLE') AS TIMESTAMP) as time
      # JSON unix epoch (milliseconds)
      # - CAST(try_variant_get(data, '$.ts', 'LONG') / 1000.0 AS TIMESTAMP) as time

      - CAST(time AS DATE) as date        # optional — for date-based queries
      # - REGEXP_EXTRACT(value, '^([\\w\\-\\.]+):', 1) as host  # optional hostname
      - CAST('<source>' AS STRING) AS source       # e.g. 'cisco'
      - CAST('<source_type>' AS STRING) AS sourcetype  # e.g. 'ios'
      - CURRENT_TIMESTAMP() as processed_time

  # Optional — stream-static lookups for enrichment (applied after preTransform)
  # lookups:
  #   - name: ip_geolocation
  #     source:
  #       type: table                   # Options: table | csv | parquet | json | jsonl
  #       path: catalog.schema.ip_lookup
  #       # For file sources:
  #       # path: /Volumes/lookups/geoip.csv
  #       # format: csv
  #       # options:
  #       #   header: "true"
  #     join:
  #       type: left                    # Options: left | inner | right | full
  #       "on":                         # MUST quote 'on' — unquoted 'on' = boolean True
  #         - main.src_ip = lookup.ip_address
  #         # Multiple conditions are ANDed:
  #         # - main.source = lookup.source
  #         # Simple (same column name in both):
  #         # - src_ip
  #     select:                         # optional — which lookup columns to include
  #       - country_code
  #       - city
  #     prefix: "geo_"                 # optional — prepended to all lookup column names
  #     broadcast: true                # optional — broadcast join for small lookups (<2GB)

  # Optional — runs after lookups; use to build structs from lookup columns
  # postTransform:
  #   - "*"
  #   - "named_struct('country', geo_country_code, 'city', geo_city) as location"

  # Optional — drop columns by name (e.g. after folding them into a struct)
  # drop:
  #   - geo_country_code
  #   - geo_city


# ── Silver ─────────────────────────────────────────────────────────────────────
silver:
  transform:
    - name: <source>_<source_type>_silver
      clusterBy: [time]         # always include — ensures time-ordered writes

      # Optional — row filter (applied before field extraction)
      # filter: facility IN ('AAA', 'SEC_LOGIN')

      # Optional — silver-level lookups (same syntax as bronze.lookups)
      # lookups: []

      fields:
        # ── Text / syslog ─────────────────────────────────────────────────────
        # Extract fields from the `value` STRING column using REGEXP_EXTRACT.
        # Use unquoted YAML or | block scalars for regexes (\\d, \\S, \\w, etc.)
        - name: field_one
          expr: REGEXP_EXTRACT(value, 'field_one=(\\S+)', 1)

        # ── JSON / VARIANT ────────────────────────────────────────────────────
        # Extract fields from the `data` VARIANT column using try_variant_get.
        # try_variant_get returns NULL on type mismatch (safe); avoid data:field::TYPE shorthand
        # - name: field_one
        #   expr: try_variant_get(data, '$.FieldOne', 'STRING')
        # - name: count
        #   expr: TRY_CAST(try_variant_get(data, '$.Count', 'STRING') AS INT)
        # - name: enabled
        #   expr: TRY_CAST(try_variant_get(data, '$.Enabled', 'STRING') AS BOOLEAN)
        # - name: tags
        #   expr: try_variant_get(data, '$.Tags', 'ARRAY<STRING>')
        # - name: rdata
        #   expr: from_json(try_variant_get(data, '$.RData', 'STRING'), 'ARRAY<MAP<STRING,STRING>>')
        # Keys with dots in the name (e.g. 'id.orig_h'):
        # - name: orig_host
        #   expr: CAST(data:['id.orig_h'] AS STRING)

        # ── Simple column reference (no transformation) ───────────────────────
        # - name: event_time
        #   from: time

        # ── Static literal value ──────────────────────────────────────────────
        # - name: log_type
        #   literal: "DNS Query"

      utils:
        unreferencedColumns:
          preserve: true              # pass unmapped columns downstream for raw_data/unmapped
          # omitColumns:              # drop specific columns
          #   - data:['id.orig_h']
          #   - _metadata

      # Optional — row filter applied after field extraction
      # postFilter: field IS NOT NULL


# ── Gold (OCSF) ────────────────────────────────────────────────────────────────
# One entry per OCSF table.  TIP: copy fields from ocsf_templates/<category>/<name>.yaml
# Available tables: network_activity, dns_activity, http_activity, ssh_activity,
#   authentication, authorize_session, user_access, account_change, group_management,
#   process_activity, file_activity, script_activity,
#   vulnerability_finding, data_security_finding, api_activity
gold:
  - name: <ocsf_table_name>
    input: <source>_<source_type>_silver
    # catalog: my_catalog            # optional — overrides bundle-level gold_catalog
    # database: my_database          # optional — overrides bundle-level gold_database
    # filter: field = 'value'        # optional — row filter before mapping
    # clusterBy: ["time", "field"]   # SSS mode ONLY (not supported in SDP)
    fields:
      - name: time                    # ALWAYS first — Delta clustering requires clustered cols in first 32
        from: time
      - name: category_uid
        expr: CAST(<N> AS INT)        # e.g. 4 for Network Activity
      - name: category_name
        literal: <Category Name>      # e.g. "Network Activity"
      - name: class_uid
        expr: CAST(<N> AS INT)        # e.g. 4003 for DNS Activity
      - name: class_name
        literal: <Class Name>
      - name: type_uid
        expr: CAST(class_uid * 100 + activity_id AS BIGINT)
      - name: type_name
        expr: "CONCAT('<Class Name>: ', activity_name)"
      - name: activity_id
        expr: CAST(<N> AS INT)
      - name: activity_name
        expr: CASE WHEN activity_id = 1 THEN 'Query' ELSE 'Unknown' END
      - name: activity
        expr: CASE WHEN activity_id = 1 THEN 'Query' ELSE 'Unknown' END
      - name: severity_id
        expr: CAST(1 AS INT)          # 0=Unknown 1=Info 2=Low 3=Med 4=High 5=Critical 6=Fatal 99=Other
      - name: severity
        literal: Informational
      - name: time
        from: time
      - name: timezone_offset
        expr: CAST(NULL AS INT)
      - name: status_id
        expr: CAST(1 AS INT)          # 0=Unknown 1=Success 2=Failure 99=Other
      - name: status
        literal: Success
      # Optional
      # - name: status_code
      #   expr: CAST(rcode AS STRING)
      # - name: status_detail
      #   from: description
      # - name: message
      #   expr: "CONCAT('Event: ', event_name, ' from ', src_ip)"
      # - name: action_id
      #   expr: CAST(1 AS INT)        # 0=Unknown 1=Allowed 2=Denied 99=Other
      # - name: action
      #   literal: Allowed

      # ── Metadata (required) ─────────────────────────────────────────────────
      - name: metadata.version
        literal: "1.7.0"
      - name: metadata.product.name
        literal: <Product Name>
      - name: metadata.product.vendor_name
        literal: <Vendor Name>
      - name: metadata.log_provider
        literal: <source>             # MUST match preset's source value exactly
      - name: metadata.log_name
        literal: <source_type>        # MUST match preset's sourcetype value exactly
      - name: metadata.log_format
        literal: JSON                 # or syslog, CSV
      - name: metadata.log_version
        literal: "<source>@<source_type>:version@1.0"
      - name: metadata.processed_time
        expr: CURRENT_TIMESTAMP()
      - name: metadata.logged_time
        from: time

      # ── Data preservation (recommended) ────────────────────────────────────
      # For text/syslog:
      - name: raw_data
        expr: CAST(to_json(named_struct('payload', value, 'source', source, 'sourcetype', sourcetype)) AS VARIANT)
      # For JSON sources (use data instead of value):
      # - name: raw_data
      #   expr: CAST(to_json(named_struct('payload', data, 'source', source, 'sourcetype', sourcetype)) AS VARIANT)

      - name: unmapped
        expr: |
          CAST(to_json(named_struct(
            'field_one', field_one,
            'field_two', field_two
          )) AS VARIANT)
```
