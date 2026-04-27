# DSL Lite — Silver Layer Patterns

Deep reference for silver field extraction, type handling, and routing.

---

## Field Specification Types

| Type | Syntax | When to Use |
|------|--------|-------------|
| `expr` | `expr: <Spark SQL>` | Any computation, extraction, casting |
| `from` | `from: <column>` | Copy a column as-is (no transformation) |
| `literal` | `literal: <value>` | Static constant value |

---

## JSON / VARIANT Extraction

Use `try_variant_get` for safe extraction from the `data` VARIANT column.
**Never use `data:field::TYPE` for numeric/boolean/timestamp** — it throws on type mismatch.
`data:field::STRING` is safe (everything can be cast to string) but `try_variant_get` is preferred for consistency.

**Naming rule: `name:` must exactly match the JSON key — preserve case, do not rename or snake_case.** Gold handles all renaming to OCSF field paths. Using the original key name keeps silver a faithful representation of the source and makes gold mappings self-evident.

```yaml
# String — name matches JSON key exactly
- name: QueryName
  expr: try_variant_get(data, '$.QueryName', 'STRING')

# Integer — MUST use try_variant_get or TRY_CAST
- name: SrcPort
  expr: TRY_CAST(try_variant_get(data, '$.SrcPort', 'STRING') AS INT)
# OR
- name: SrcPort
  expr: try_variant_get(data, '$.SrcPort', 'INT')

# Boolean
- name: IsResponseCached
  expr: TRY_CAST(try_variant_get(data, '$.IsResponseCached', 'STRING') AS BOOLEAN)

# Long / BigInt
- name: BytesSent
  expr: TRY_CAST(try_variant_get(data, '$.BytesSent', 'STRING') AS BIGINT)

# ARRAY of strings
- name: ResolvedIPs
  expr: try_variant_get(data, '$.ResolvedIPs', 'ARRAY<STRING>')

# ARRAY of ints
- name: CategoryIDs
  expr: try_variant_get(data, '$.CategoryIDs', 'ARRAY<INT>')

# Nested JSON string → parse as ARRAY<MAP>
- name: RData
  expr: from_json(try_variant_get(data, '$.RData', 'STRING'), 'ARRAY<MAP<STRING,STRING>>')

# Keys with dots in the name — use backtick-quoted name
- name: "`id.orig_h`"
  expr: CAST(data:['id.orig_h'] AS STRING)
```

---

## Text / Syslog REGEXP_EXTRACT

Extract fields from the `value` STRING column using Spark SQL `REGEXP_EXTRACT`.

**Naming rule: choose descriptive snake_case names that reflect what the regex captures.** There is no source key to preserve — name fields by their semantic meaning (e.g. `src_ip`, `facility`, `mnemonic`, `severity`).

```yaml
# Single capture group
- name: severity
  expr: REGEXP_EXTRACT(value, 'severity=(\\S+)', 1)

# Cisco IOS syslog format: seq# timestamp %FACILITY-SEV-MNEMONIC: message
- name: seq_no
  expr: REGEXP_EXTRACT(value, '^(\\d+):\\s+(\\w+\\s+\\d+\\s+\\d+\\s+\\d+:\\d+:\\d+):\\s+%(\\w+)-(\\d+)-(\\w+):\\s(.+)$', 1)
- name: facility
  expr: REGEXP_EXTRACT(value, '^(\\d+):\\s+(\\w+\\s+\\d+\\s+\\d+\\s+\\d+:\\d+:\\d+):\\s+%(\\w+)-(\\d+)-(\\w+):\\s(.+)$', 3)
- name: sev_num
  expr: REGEXP_EXTRACT(value, '^(\\d+):\\s+(\\w+\\s+\\d+\\s+\\d+\\s+\\d+:\\d+:\\d+):\\s+%(\\w+)-(\\d+)-(\\w+):\\s(.+)$', 4)
- name: mnemonic
  expr: REGEXP_EXTRACT(value, '^(\\d+):\\s+(\\w+\\s+\\d+\\s+\\d+\\s+\\d+:\\d+:\\d+):\\s+%(\\w+)-(\\d+)-(\\w+):\\s(.+)$', 5)
- name: description
  expr: REGEXP_EXTRACT(value, '^(\\d+):\\s+(\\w+\\s+\\d+\\s+\\d+\\s+\\d+:\\d+:\\d+):\\s+%(\\w+)-(\\d+)-(\\w+):\\s(.+)$', 6)

# IP address
- name: src_ip
  expr: REGEXP_EXTRACT(value, 'src_ip=(\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3})', 1)

# Optional field (with NULLIF to convert empty match to NULL)
- name: host_name
  expr: NULLIF(REGEXP_EXTRACT(value, 'hostname=(\\S+)', 1), '')
```

---

## REGEXP_EXTRACT Gotchas

### Double Backslashes in YAML

Spark SQL `REGEXP_EXTRACT` uses Java regex. YAML must escape backslashes. The rule:

| YAML context | Write | Spark SQL sees | Regex interprets |
|---|---|---|---|
| Unquoted string | `\\d` | `\\d` | `\d` (digit) ✓ |
| `\|` block scalar | `\\d` | `\\d` | `\d` (digit) ✓ |
| Double-quoted `"..."` | `\\\\d` | `\\d` | `\d` (digit) ✓ |

**Use unquoted YAML or `|` block scalars for all regex patterns.** Avoid double-quoted strings for regex — the quadruple-backslash requirement is error-prone.

```yaml
# GOOD — unquoted string
- name: src_ip
  expr: REGEXP_EXTRACT(value, 'src=(\\d+\\.\\d+\\.\\d+\\.\\d+)', 1)

# GOOD — block scalar (for complex or multi-line regex)
- name: src_ip
  expr: |
    REGEXP_EXTRACT(value, 'src=(\\d+\\.\\d+\\.\\d+\\.\\d+)', 1)

# BAD — double-quoted requires 4 backslashes
- name: src_ip
  expr: "REGEXP_EXTRACT(value, 'src=(\\\\d+\\\\.\\\\d+\\\\.\\\\d+\\\\.\\\\d+)', 1)"
```

The same applies to `filter:` expressions containing `RLIKE`:
```yaml
# GOOD
filter: mnemonic RLIKE '^(LOGIN|LOGOUT)$'
filter: value RLIKE 'org\\.(add_member|remove_member)'

# BAD — double-quoted
filter: "mnemonic RLIKE 'org\\.(add_member)'"  # dot unescaped
```

### REGEXP_EXTRACT Returns Empty String on No Match

`REGEXP_EXTRACT` returns `""` (not NULL) when the pattern doesn't match. This breaks `COALESCE`:

```yaml
# BAD — COALESCE stops at "" (non-null) even though pattern didn't match
expr: COALESCE(REGEXP_EXTRACT(value, 'pattern1=(\\S+)', 1), REGEXP_EXTRACT(value, 'pattern2=(\\S+)', 1))

# GOOD — NULLIF converts "" to NULL, COALESCE tries the next pattern
expr: COALESCE(
    NULLIF(REGEXP_EXTRACT(value, 'pattern1=(\\S+)', 1), ''),
    NULLIF(REGEXP_EXTRACT(value, 'pattern2=(\\S+)', 1), ''))
```

---

## TRY_CAST vs CAST

| Use | When |
|-----|------|
| `TRY_CAST(expr AS type)` | String → numeric, boolean, timestamp (returns NULL on failure) |
| `CAST(literal AS type)` | Literal values like `CAST(6 AS INT)` — always safe |
| `CAST(int_col AS STRING)` | Integer/numeric → string — always safe |

```yaml
# GOOD — string from regex to INT (might be empty/invalid)
- name: src_port
  expr: TRY_CAST(REGEXP_EXTRACT(value, 'port=(\\d+)', 1) AS INT)

# GOOD — JSON string field to INT
- name: count
  expr: TRY_CAST(try_variant_get(data, '$.Count', 'STRING') AS INT)

# GOOD — literal to typed value
- name: category_uid
  expr: CAST(4 AS INT)

# BAD — CAST on untrusted string input (throws on malformed data)
- name: src_port
  expr: CAST(REGEXP_EXTRACT(value, 'port=(\\d+)', 1) AS INT)
```

---

## Multiple Silver Transforms

When a source contains heterogeneous event types that map to different OCSF classes, use
`filter` to route events to separate silver tables. Each silver table feeds a different gold table.

```yaml
silver:
  transform:
    - name: cisco_ios_auth
      filter: (facility IN ('AAA', 'SEC_LOGIN') AND mnemonic LIKE 'LOGIN%') OR (facility = 'SYS' AND mnemonic = 'LOGOUT')
      fields:
        - name: user_name
          expr: REGEXP_EXTRACT(description, 'user:\\s*(\\w+)', 1)
        # ... auth-specific fields

    - name: cisco_ios_network
      filter: facility IN ('LINK', 'LINEPROTO', 'ETHCNTR')
      fields:
        - name: interface_name
          expr: REGEXP_EXTRACT(description, 'Interface\\s+([^,]+)', 1)
        # ... network-specific fields

    - name: cisco_ios_process
      filter: facility IN ('SYS', 'CPU', 'MEM', 'ENV')
      fields:
        # ... process-specific fields
```

Alternatively, a single silver table can feed multiple gold tables — apply `filter` at the gold
level instead:
```yaml
gold:
  - name: authentication
    input: cisco_ios_silver
    filter: (facility IN ('AAA', 'SEC_LOGIN') AND mnemonic LIKE 'LOGIN%') OR (facility = 'SYS' AND mnemonic = 'LOGOUT')
    fields: [...]
  - name: network_activity
    input: cisco_ios_silver
    filter: facility IN ('LINK', 'LINEPROTO')
    fields: [...]
```

**When to use multiple silver tables**: when different event types have very different field sets
(avoids NULL-heavy rows). When to filter at gold: when the silver extraction is the same for all
event types and you just need different OCSF classifications.

---

## Preserving Unreferenced Columns

```yaml
utils:
  unreferencedColumns:
    preserve: true          # all non-extracted columns pass through
    omitColumns:            # optionally drop specific columns
      - data:['id.orig_h']
      - _metadata
      - processed_time
```

With `preserve: true`, any column not explicitly listed in `fields` is passed through as-is.
These preserved columns are available in gold for `raw_data` and `unmapped` expressions.

Without this, only fields explicitly listed in `fields` appear in the silver table.

---

## Silver Lookup Joins

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
          select: [department, manager]
          prefix: "dir_"
          broadcast: true
      fields:
        - name: user_dept
          from: dir_department
```
