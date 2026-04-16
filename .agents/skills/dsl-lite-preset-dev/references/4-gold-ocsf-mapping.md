# DSL Lite — Gold Layer / OCSF Mapping Reference

---

## OCSF Table Catalog

| Table | class_uid | category_uid | Category |
|-------|-----------|--------------|----------|
| `network_activity` | 4001 | 4 | Network Activity |
| `http_activity` | 4002 | 4 | Network Activity |
| `dns_activity` | 4003 | 4 | Network Activity |
| `dhcp_activity` | 4004 | 4 | Network Activity |
| `ssh_activity` | 4007 | 4 | Network Activity |
| `authentication` | 3002 | 3 | Identity & Access Management |
| `authorize_session` | 3003 | 3 | Identity & Access Management |
| `user_access` | 3003 | 3 | Identity & Access Management |
| `account_change` | 3001 | 3 | Identity & Access Management |
| `group_management` | 3006 | 3 | Identity & Access Management |
| `process_activity` | 1007 | 1 | System Activity |
| `file_activity` | 1001 | 1 | System Activity |
| `script_activity` | 1008 | 1 | System Activity |
| `vulnerability_finding` | 2002 | 2 | Findings |
| `data_security_finding` | 2006 | 2 | Findings |
| `api_activity` | 3005 | 3 | Identity & Access Management |

**Ready-made field lists** for each table: `ocsf_templates/<category>/<table_name>.yaml`

---

## Required Base Fields (Every Gold Table)

```yaml
# ── Classification ─────────────────────────────────────────────────────────────
- name: category_uid
  expr: CAST(<N> AS INT)              # see catalog above
- name: category_name
  literal: <Category Name>            # e.g. "Network Activity"
- name: class_uid
  expr: CAST(<N> AS INT)              # see catalog above
- name: class_name
  literal: <Class Name>               # e.g. "DNS Activity"
- name: type_uid
  expr: CAST(class_uid * 100 + activity_id AS BIGINT)
- name: type_name
  expr: "CONCAT('<Class Name>: ', activity_name)"

# ── Activity ──────────────────────────────────────────────────────────────────
- name: activity_id
  expr: CAST(<N> AS INT)
- name: activity_name
  expr: |
    CASE
      WHEN activity_id = 1 THEN 'Open'
      WHEN activity_id = 2 THEN 'Close'
      ELSE 'Unknown'
    END
- name: activity
  expr: |
    CASE
      WHEN activity_id = 1 THEN 'Open'
      WHEN activity_id = 2 THEN 'Close'
      ELSE 'Unknown'
    END

# ── Severity ──────────────────────────────────────────────────────────────────
- name: severity_id
  expr: CAST(1 AS INT)
- name: severity
  literal: Informational

# ── Status ───────────────────────────────────────────────────────────────────
- name: status_id
  expr: CAST(1 AS INT)
- name: status
  literal: Success

# ── Time ──────────────────────────────────────────────────────────────────────
- name: time
  from: time
- name: timezone_offset
  expr: CAST(NULL AS INT)

# ── Metadata (required) ──────────────────────────────────────────────────────
- name: metadata.version
  literal: "1.7.0"
- name: metadata.product.name
  literal: <Product Name>
- name: metadata.product.vendor_name
  literal: <Vendor Name>
- name: metadata.log_provider
  literal: <source>           # MUST match preset's source value exactly
- name: metadata.log_name
  literal: <source_type>      # MUST match preset's sourcetype value exactly
- name: metadata.log_format
  literal: JSON               # or: syslog, CSV
- name: metadata.log_version
  literal: "<source>@<source_type>:version@1.0"
- name: metadata.processed_time
  expr: CURRENT_TIMESTAMP()
- name: metadata.logged_time
  from: time

# ── Data preservation ────────────────────────────────────────────────────────
- name: raw_data
  expr: CAST(to_json(named_struct('payload', value, 'source', source, 'sourcetype', sourcetype)) AS VARIANT)
  # For JSON sources use `data` instead of `value`
- name: unmapped
  expr: |
    to_variant_object(named_struct(
      'vendor_field_1', field_1,
      'vendor_field_2', field_2
    ))
```

---

## OCSF Enum Values

### severity_id
| ID | Name |
|----|------|
| 0 | Unknown |
| 1 | Informational |
| 2 | Low |
| 3 | Medium |
| 4 | High |
| 5 | Critical |
| 6 | Fatal |
| 99 | Other |

**Cisco IOS syslog severity mapping** (IOS 0–7 → OCSF):
```yaml
- name: severity_id
  expr: |
    CASE
      WHEN CAST(severity AS INT) = 0 THEN CAST(6 AS INT)   -- Emergency → Fatal
      WHEN CAST(severity AS INT) = 1 THEN CAST(5 AS INT)   -- Alert → Critical
      WHEN CAST(severity AS INT) = 2 THEN CAST(5 AS INT)   -- Critical → Critical
      WHEN CAST(severity AS INT) = 3 THEN CAST(4 AS INT)   -- Error → High
      WHEN CAST(severity AS INT) = 4 THEN CAST(3 AS INT)   -- Warning → Medium
      WHEN CAST(severity AS INT) = 5 THEN CAST(2 AS INT)   -- Notice → Low
      WHEN CAST(severity AS INT) = 6 THEN CAST(1 AS INT)   -- Informational → Informational
      WHEN CAST(severity AS INT) = 7 THEN CAST(1 AS INT)   -- Debug → Informational
      ELSE CAST(99 AS INT)
    END
```

### status_id
| ID | Name |
|----|------|
| 0 | Unknown |
| 1 | Success |
| 2 | Failure |
| 99 | Other |

### action_id (security decisions)
| ID | Name |
|----|------|
| 0 | Unknown |
| 1 | Allowed |
| 2 | Denied |
| 99 | Other |

### disposition_id (security findings)
| ID | Name |
|----|------|
| 0 | Unknown |
| 1 | Allowed |
| 2 | Blocked |
| 3 | Quarantined |
| 4 | Isolated |
| 5 | Deleted |
| 10 | Detected |
| 17 | Logged |

### connection_info.direction_id
| ID | Name |
|----|------|
| 0 | Unknown |
| 1 | Inbound |
| 2 | Outbound |
| 3 | Lateral |
| 99 | Other |

---

## Endpoint Namespacing by Category

| Gold Table Category | Endpoint Fields | Host Fields |
|--------------------|----------------|-------------|
| Network Activity (4xxx) | `src_endpoint.*`, `dst_endpoint.*` | — |
| System Activity (1xxx) | — | `device.*` |
| IAM (3xxx) | `src_endpoint.*` (optional) | — |

---

## Network Activity Fields

For `network_activity`, `dns_activity`, `http_activity`, `ssh_activity`:

```yaml
# Source endpoint
- name: src_endpoint.ip
  from: src_ip
- name: src_endpoint.port
  from: src_port
- name: src_endpoint.mac
  from: src_mac
- name: src_endpoint.hostname
  from: src_hostname
- name: src_endpoint.location.country
  from: country_code
- name: src_endpoint.location.city
  from: city_name

# Destination endpoint
- name: dst_endpoint.ip
  from: dst_ip
- name: dst_endpoint.port
  from: dst_port

# Connection info
- name: connection_info.uid
  from: connection_id
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
- name: connection_info.direction_id
  expr: CAST(0 AS INT)    # 0=Unknown 1=Inbound 2=Outbound 3=Lateral

# Traffic bytes
- name: traffic.bytes_in
  from: bytes_received
- name: traffic.bytes_out
  from: bytes_sent
```

---

## Authentication Fields

```yaml
- name: user.name
  expr: REGEXP_EXTRACT(description, 'user:\\s*(\\w+)', 1)
- name: user.uid
  from: user_id
- name: src_endpoint.ip
  from: src_ip
- name: auth_protocol
  literal: Unknown
- name: auth_protocol_id
  expr: CAST(0 AS INT)
- name: is_remote
  expr: CAST(src_ip IS NOT NULL AS BOOLEAN)
```

---

## DNS Activity Fields

```yaml
- name: query.hostname
  from: query_name
- name: query.type
  from: query_type_name
- name: query.class
  literal: IN
- name: query.opcode
  literal: Query
- name: query.opcode_id
  expr: CAST(0 AS INT)
- name: rcode_id
  from: rcode
- name: rcode
  expr: |
    CASE
      WHEN RCode = 0 THEN 'NoError'
      WHEN RCode = 1 THEN 'FormError'
      WHEN RCode = 2 THEN 'ServError'
      WHEN RCode = 3 THEN 'NXDomain'
      WHEN RCode = 5 THEN 'Refused'
      ELSE 'Other'
    END

# DNS answers array (for sources with parallel answer arrays)
- name: answers
  expr: |
    TRANSFORM(arrays_zip(answer_ips, answer_ttls),
      x -> NAMED_STRUCT('rdata', x.answer_ips, 'ttl', TRY_CAST(x.answer_ttls AS INT)))

# DNS answers array (from ResourceRecordsJSON array of maps)
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
```

---

## System Activity Fields

For `process_activity`, `file_activity`, `script_activity` — use `device.*` not `endpoint.*`:

```yaml
- name: device.ip
  from: agent_ip
- name: device.uid
  from: device_id
- name: device.name
  from: hostname

# For process_activity
- name: process.name
  from: process_name
- name: process.pid
  from: process_id
- name: actor.user.name
  from: user_name

# For file_activity
- name: file.name
  from: file_name
- name: file.path
  from: file_path
```

---

## Observables

Include security-relevant fields that analysts would search or pivot on. Typically 2–5 per table.

```yaml
- name: observables
  expr: |
    concat(
      ARRAY(NAMED_STRUCT('name', 'src_endpoint.ip', 'type', 'IP Address', 'value', SrcIP)),
      COALESCE(
        TRANSFORM(
          FILTER(ResolvedIPs, x -> x IS NOT NULL),
          x -> NAMED_STRUCT('name', 'dst_endpoint.ip', 'type', 'IP Address', 'value', x)
        ),
        ARRAY()
      )
    )
```

Common observable types (OCSF standard names):

| Type | Typical Fields |
|------|---------------|
| `IP Address` | `src_endpoint.ip`, `dst_endpoint.ip` |
| `Port` | `src_endpoint.port`, `dst_endpoint.port` |
| `Hostname` | `src_endpoint.hostname`, `query.hostname` |
| `User Name` | `user.name`, `actor.user.name` |
| `URL String` | `http_request.url` |
| `Hash` | file hashes |
| `Process Name` | `process.name` |
| `HTTP User-Agent` | `http_request.user_agent` |
| `File Name` | `file.name` |
| `MAC Address` | `src_endpoint.mac` |
| `Email Address` | email fields |

---

## Enrichments

For security gateway fields (firewalls, DNS with threat intel, WAFs):

```yaml
- name: enrichments
  expr: |
    CASE
      WHEN (MatchedCategoryNames IS NOT NULL AND size(MatchedCategoryNames) > 0) OR
           (MatchedIndicatorFeedNames IS NOT NULL AND size(MatchedIndicatorFeedNames) > 0)
      THEN concat(
        COALESCE(
          TRANSFORM(
            FILTER(MatchedCategoryNames, x -> x IS NOT NULL),
            x -> NAMED_STRUCT('name', 'Matched Category', 'value', x,
                              'data', CAST(NULL AS VARIANT), 'desc', CAST(NULL AS STRING))
          ),
          ARRAY()
        ),
        COALESCE(
          TRANSFORM(
            FILTER(MatchedIndicatorFeedNames, x -> x IS NOT NULL),
            x -> NAMED_STRUCT('name', 'Matched Threat Feed', 'value', x,
                              'data', CAST(NULL AS VARIANT), 'desc', CAST(NULL AS STRING))
          ),
          ARRAY()
        )
      )
      ELSE NULL
    END
```

---

## Policy Fields (Firewalls / Security Controls)

```yaml
- name: policy.name
  from: policy_name
- name: policy.uid
  from: policy_id
- name: policy.is_applied
  expr: CAST(policy_id IS NOT NULL AS BOOLEAN)
```

---

## Additional Metadata Fields

```yaml
- name: metadata.uid
  from: event_id             # unique event identifier
- name: metadata.correlation_uid
  from: session_id           # for correlating related events
- name: metadata.event_code
  from: mnemonic             # vendor event code
- name: metadata.tenant_uid
  from: account_id           # multi-tenant identifier
- name: metadata.tags
  expr: CAST(NULL AS VARIANT)
```

---

## Multiple Gold Tables from One Silver

One silver table can map to multiple OCSF tables — each with its own filter:

```yaml
gold:
  - name: authentication
    input: cisco_ios_silver
    filter: (facility IN ('AAA', 'SEC_LOGIN') AND mnemonic LIKE 'LOGIN%') OR (facility = 'SYS' AND mnemonic = 'LOGOUT')
    fields: [...]

  - name: authorize_session
    input: cisco_ios_silver
    filter: mnemonic IN ('EXEC_FAILED', 'CLI_DENIED', 'ACCESS_DENIED')
    fields: [...]

  - name: network_activity
    input: cisco_ios_silver
    filter: facility IN ('LINK', 'LINEPROTO', 'ETHCNTR')
    fields: [...]
```

---

## SDP vs SSS Notes

- **`clusterBy`** — only supported in SSS mode. In SDP mode, run after pipeline creation:
  ```sql
  ALTER TABLE <catalog>.<database>.<table_name> CLUSTER BY (time, src_endpoint.ip)
  ```
- **Gold table writes** — in SDP mode, gold tables are Delta Sinks (not streaming tables), which allows multiple pipelines to write to the same OCSF table.
