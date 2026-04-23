# DSL Lite — Gold Table Field Reference

**OCSF Version: 1.7.0** — All table schemas, class_uid values, category_uid values, and enum IDs
in this document correspond to OCSF 1.7.0. The DDL source of truth is `notebooks/ddl/create_ocsf_tables.py`.
Always set `metadata.version: "1.7.0"` in every gold table.

Per-table field listings for all supported OCSF event classes. Each section shows the dot-path
field names used in the gold `fields:` block (DSL Lite auto-builds nested structs from dot-paths).
The OCSF templates at `ocsf_templates/<category>/<table>.yaml` are the authoritative copy-paste
source; use this file for quick field lookup and struct schema reference.

---

## Quick Reference

| Table | class_uid | category_uid | Category |
|-------|-----------|--------------|----------|
| `network_activity` | 4001 | 4 | Network Activity |
| `http_activity` | 4002 | 4 | Network Activity |
| `dns_activity` | 4003 | 4 | Network Activity |
| `dhcp_activity` | 4004 | 4 | Network Activity |
| `email_activity` | 4009 | 4 | Network Activity |
| `ssh_activity` | 4007 | 4 | Network Activity |
| `authentication` | 3002 | 3 | Identity & Access Management |
| `authorize_session` | 3003 | 3 | Identity & Access Management |
| `user_access` | 3003 | 3 | Identity & Access Management |
| `account_change` | 3001 | 3 | Identity & Access Management |
| `group_management` | 3006 | 3 | Identity & Access Management |
| `entity_management` | 3004 | 3 | Identity & Access Management |
| `process_activity` | 1007 | 1 | System Activity |
| `file_activity` | 1001 | 1 | System Activity |
| `script_activity` | 1008 | 1 | System Activity |
| `kernel_extension_activity` | 1003 | 1 | System Activity |
| `scheduled_job_activity` | 1006 | 1 | System Activity |
| `vulnerability_finding` | 2002 | 2 | Findings |
| `data_security_finding` | 2006 | 2 | Findings |
| `detection_finding` | 2004 | 2 | Findings |
| `api_activity` | 6003 | 6 | Application Activity |
| `datastore_activity` | 6005 | 6 | Application Activity |

---

## Common Structs (Shared Across Tables)

### endpoint (src_endpoint / dst_endpoint)
Used in Network Activity and IAM tables.

| Dot-path | Type | Description |
|----------|------|-------------|
| `src_endpoint.ip` | STRING | IPv4 or IPv6 address |
| `src_endpoint.port` | INT | Port number |
| `src_endpoint.hostname` | STRING | Hostname |
| `src_endpoint.domain` | STRING | Domain name |
| `src_endpoint.mac` | STRING | MAC address |
| `src_endpoint.name` | STRING | Endpoint name |
| `src_endpoint.uid` | STRING | Endpoint unique ID |
| `src_endpoint.svc_name` | STRING | Service name (e.g. `dns`, `http`) |
| `src_endpoint.type` | STRING | Endpoint type name |
| `src_endpoint.type_id` | INT | Endpoint type ID |
| `src_endpoint.vpc_uid` | STRING | VPC/network segment ID |
| `src_endpoint.zone` | STRING | Availability zone |
| `src_endpoint.location.city` | STRING | City |
| `src_endpoint.location.country` | STRING | Country code or name |
| `src_endpoint.location.continent` | STRING | Continent |
| `src_endpoint.location.lat` | FLOAT | Latitude |
| `src_endpoint.location.long` | FLOAT | Longitude |
| `src_endpoint.location.postal_code` | STRING | Postal code |
| `src_endpoint.location.region` | STRING | State or region |

> Replace `src_` with `dst_` for the destination endpoint — same field set.

### metadata
Required on every OCSF table.

| Dot-path | Type | Description |
|----------|------|-------------|
| `metadata.version` | STRING | OCSF schema version — always `"1.7.0"` |
| `metadata.product.name` | STRING | Product name (e.g. `"Cisco IOS"`) |
| `metadata.product.vendor_name` | STRING | Vendor name |
| `metadata.product.version` | STRING | Product/agent version |
| `metadata.log_provider` | STRING | Must match preset `source` value |
| `metadata.log_name` | STRING | Must match preset `sourcetype` value |
| `metadata.log_format` | STRING | `JSON`, `syslog`, `CSV` |
| `metadata.log_version` | STRING | `"<source>@<sourcetype>:version@1.0"` |
| `metadata.logged_time` | TIMESTAMP | When event was logged — map to `time` |
| `metadata.processed_time` | TIMESTAMP | `CURRENT_TIMESTAMP()` |
| `metadata.uid` | STRING | Unique event ID from vendor |
| `metadata.event_code` | STRING | Vendor event code/mnemonic |
| `metadata.correlation_uid` | STRING | Session or request ID for correlation |
| `metadata.tenant_uid` | STRING | Multi-tenant account ID |
| `metadata.original_time` | STRING | Raw timestamp string from source |
| `metadata.tags` | VARIANT | Arbitrary tags — `CAST(NULL AS VARIANT)` if unused |

### connection_info
Network Activity tables only.

| Dot-path | Type | Description |
|----------|------|-------------|
| `connection_info.uid` | STRING | Connection unique ID (session/conn_uid) |
| `connection_info.protocol_name` | STRING | Protocol name: `tcp`, `udp`, `icmp`, `http` |
| `connection_info.protocol_num` | INT | IANA number: 6=TCP, 17=UDP, 1=ICMP |
| `connection_info.protocol_ver` | STRING | Protocol version string |
| `connection_info.protocol_ver_id` | INT | IP version: 4 or 6 |
| `connection_info.direction` | STRING | Direction name: `Inbound`, `Outbound` |
| `connection_info.direction_id` | INT | 0=Unknown, 1=Inbound, 2=Outbound, 3=Lateral |
| `connection_info.flag_history` | STRING | TCP flag history |

### traffic
Network Activity tables only.

| Dot-path | Type | Description |
|----------|------|-------------|
| `traffic.bytes` | BIGINT | Total bytes |
| `traffic.bytes_in` | BIGINT | Bytes received (response) |
| `traffic.bytes_out` | BIGINT | Bytes sent (request) |
| `traffic.bytes_missed` | BIGINT | Bytes not captured |
| `traffic.packets` | BIGINT | Total packets |
| `traffic.packets_in` | BIGINT | Packets received |
| `traffic.packets_out` | BIGINT | Packets sent |

### user
IAM tables (`authentication`, `authorize_session`, etc.).

| Dot-path | Type | Description |
|----------|------|-------------|
| `user.full_name` | STRING | Full display name (e.g. "Jane Doe") |
| `user.name` | STRING | Username or login name (e.g. email or UPN) |
| `user.uid` | STRING | User unique identifier |
| `user.type` | STRING | User type name (e.g. `human`, `service`) |
| `user.type_id` | INT | User type ID |
| `user.has_mfa` | BOOLEAN | Whether user has MFA enabled |

### session
IAM tables.

| Dot-path | Type | Description |
|----------|------|-------------|
| `session.uid` | STRING | Session unique identifier |
| `session.uuid` | STRING | Session UUID |
| `session.uid_alt` | STRING | Alternate session UID |
| `session.created_time` | TIMESTAMP | Session creation time |
| `session.expiration_time` | TIMESTAMP | Session expiration time |
| `session.is_mfa` | BOOLEAN | MFA used for session |
| `session.is_remote` | BOOLEAN | Remote session flag |
| `session.is_vpn` | BOOLEAN | VPN session flag |
| `session.issuer` | STRING | Token/session issuer |
| `session.terminal` | STRING | Terminal or client identifier |
| `session.credential_uid` | STRING | Credential or token ID |

### enrichments / observables
Present on virtually every table.

```yaml
# enrichments — ARRAY<STRUCT<data: VARIANT, desc: STRING, name: STRING, value: STRING>>
- name: enrichments
  expr: |
    FILTER(ARRAY(
      CASE WHEN field IS NOT NULL THEN
        NAMED_STRUCT('name', 'source_name', 'desc', CAST(NULL AS STRING),
                     'data', CAST(NULL AS VARIANT), 'value', CAST(field AS STRING))
      ELSE NULL END
    ), x -> x IS NOT NULL)

# observables — ARRAY<STRUCT<name: STRING, type: STRING, value: STRING>>
- name: observables
  expr: |
    ARRAY(
      NAMED_STRUCT('name', 'src_endpoint.ip', 'type', 'IP Address', 'value', src_ip),
      NAMED_STRUCT('name', 'user.name', 'type', 'User Name', 'value', username)
    )
```

Common observable types: `IP Address`, `Port`, `Hostname`, `User Name`, `URL String`,
`Hash`, `Process Name`, `HTTP User-Agent`, `File Name`, `MAC Address`, `Email Address`.

### cloud
Optional — when events originate from or relate to a cloud provider.

| Dot-path | Type | Description |
|----------|------|-------------|
| `cloud.provider` | STRING | `aws`, `azure`, `gcp`, `oci` |
| `cloud.region` | STRING | Region: `us-east-1`, `westus2` |
| `cloud.zone` | STRING | Availability zone |
| `cloud.project_uid` | STRING | GCP project ID / Azure subscription ID |
| `cloud.cloud_partition` | STRING | AWS partition: `aws`, `aws-cn`, `aws-us-gov` |
| `cloud.account.name` | STRING | Account display name |
| `cloud.account.uid` | STRING | Account ID |

---

## Network Activity Category (category_uid: 4)

### network_activity (class_uid: 4001)

Core fields:

| Field | Type | Notes |
|-------|------|-------|
| `activity_id` | INT | 1=Open, 2=Close, 3=Refuse, 4=Fail, 5=Traffic, 6=Scan, 7=Probe, 99=Other |
| `activity_name` | STRING | Human-readable activity name |
| `category_name` | STRING | `"Network Activity"` |
| `category_uid` | INT | `CAST(4 AS INT)` |
| `class_name` | STRING | `"Network Activity"` |
| `class_uid` | INT | `CAST(4001 AS INT)` |
| `severity_id` | INT | 0–6 (see enum table) |
| `severity` | STRING | Severity name |
| `time` | TIMESTAMP | Event timestamp — required |
| `timezone_offset` | INT | Minutes from UTC — `CAST(NULL AS INT)` if unknown |
| `type_uid` | BIGINT | `CAST(class_uid * 100 + activity_id AS BIGINT)` |
| `type_name` | STRING | `CONCAT('Network Activity: ', activity_name)` |
| `status_id` | INT | 0=Unknown, 1=Success, 2=Failure, 99=Other |
| `status` | STRING | Status name |
| `status_code` | STRING | Vendor status code |
| `status_detail` | STRING | Status details |
| `action_id` | INT | 0=Unknown, 1=Allowed, 2=Denied, 99=Other |
| `action` | STRING | Action name |
| `disposition_id` | INT | 0=Unknown, 1=Allowed, 2=Blocked, 10=Detected, 17=Logged |
| `disposition` | STRING | Disposition name |
| `start_time` | TIMESTAMP | Connection start time |
| `end_time` | TIMESTAMP | Connection end time |
| `message` | STRING | Human-readable description |
| `raw_data` | VARIANT | `CAST(to_json(named_struct('payload', value, ...)) AS VARIANT)` |
| `unmapped` | VARIANT | Vendor-specific fields not in OCSF |

Plus all fields from: `src_endpoint.*`, `dst_endpoint.*`, `connection_info.*`, `traffic.*`,
`metadata.*`, `enrichments`, `observables`, `cloud.*`, `policy.*`.

> Template: `ocsf_templates/network_activity/network_activity.yaml`

---

### http_activity (class_uid: 4002)

Core fields same as `network_activity` plus:

| Field | Type | Notes |
|-------|------|-------|
| `class_name` | STRING | `"HTTP Activity"` |
| `class_uid` | INT | `CAST(4002 AS INT)` |
| `activity_id` | INT | 1=Request, 2=Response, 3=Upload, 4=Download, 5=Send, 6=Receive, 99=Other |
| `http_request.http_method` | STRING | `GET`, `POST`, `PUT`, `DELETE`, etc. |
| `http_request.url` | STRING | Full URL or path |
| `http_request.version` | STRING | `HTTP/1.1`, `HTTP/2` |
| `http_request.user_agent` | STRING | User-Agent header |
| `http_request.referrer` | STRING | Referrer URL |
| `http_request.length` | BIGINT | Request size in bytes |
| `http_response.code` | INT | HTTP status code: 200, 404, 500 |
| `http_response.status` | STRING | Status message |
| `http_response.length` | BIGINT | Response size in bytes |
| `http_response.latency` | INT | Response time in milliseconds |
| `http_response.content_type` | STRING | Content-Type header |
| `app_name` | STRING | Application name |

> Template: `ocsf_templates/network_activity/http_activity.yaml`

---

### dns_activity (class_uid: 4003)

Core fields same as `network_activity` plus:

| Field | Type | Notes |
|-------|------|-------|
| `class_name` | STRING | `"DNS Activity"` |
| `class_uid` | INT | `CAST(4003 AS INT)` |
| `activity_id` | INT | 1=Query, 2=Response, 6=Traffic |
| `query.hostname` | STRING | FQDN being queried |
| `query.type` | STRING | Record type: `A`, `AAAA`, `CNAME`, `MX`, `TXT` |
| `query.class` | STRING | `"IN"` (almost always literal) |
| `query.opcode` | STRING | `"Query"` (literal) |
| `query.opcode_id` | INT | `CAST(0 AS INT)` |
| `rcode_id` | INT | 0=NoError, 1=FormError, 2=ServError, 3=NXDomain, 5=Refused |
| `rcode` | STRING | Response code name |
| `answers` | ARRAY | DNS answer records — see patterns in ref 7 |
| `app_name` | STRING | Application or resolver name |

> Template: `ocsf_templates/network_activity/dns_activity.yaml`

---

### ssh_activity (class_uid: 4007)

Core fields same as `network_activity` plus:

| Field | Type | Notes |
|-------|------|-------|
| `class_name` | STRING | `"SSH Activity"` |
| `class_uid` | INT | `CAST(4007 AS INT)` |
| `activity_id` | INT | 1=Open, 2=Close, 3=Send, 4=Receive |
| `auth_type` | STRING | SSH auth type name: `publickey`, `password`, `keyboard-interactive` |
| `auth_type_id` | INT | 0=Unknown, 1=Password, 2=Public Key, 99=Other |
| `app_name` | STRING | Application name |
| `protocol_ver` | STRING | SSH protocol version string |

> Note: ssh_activity uses `auth_type`/`auth_type_id` (not `auth_protocol`). User info is nested under `actor.user.*`.

> Template: `ocsf_templates/network_activity/ssh_activity.yaml`

---

### dhcp_activity (class_uid: 4004)

| Field | Type | Notes |
|-------|------|-------|
| `class_name` | STRING | `"DHCP Activity"` |
| `class_uid` | INT | `CAST(4004 AS INT)` |
| `activity_id` | INT | 1=Assign, 2=Release, 3=Renew, etc. |
| `src_endpoint.ip` | STRING | Assigned IP address |
| `src_endpoint.mac` | STRING | Client MAC address |
| `src_endpoint.hostname` | STRING | Client hostname |
| `dst_endpoint.ip` | STRING | DHCP server IP |
| `lease_dur` | INT | Lease duration in seconds |
| `transaction_uid` | STRING | DHCP transaction ID |

> Template: `ocsf_templates/network_activity/dhcp_activity.yaml`

---

## Identity & Access Management Category (category_uid: 3)

### authentication (class_uid: 3002)

| Field | Type | Notes |
|-------|------|-------|
| `activity_id` | INT | 1=Logon, 2=Logoff, 3=Authentication Ticket, 4=Service Ticket, 99=Other |
| `activity_name` | STRING | `"Logon"`, `"Logoff"`, etc. |
| `category_name` | STRING | `"Identity & Access Management"` |
| `category_uid` | INT | `CAST(3 AS INT)` |
| `class_name` | STRING | `"Authentication"` |
| `class_uid` | INT | `CAST(3002 AS INT)` |
| `auth_protocol` | STRING | `NTLM`, `Kerberos`, `SAML`, `OAuth`, `Basic` |
| `auth_protocol_id` | INT | 0=Unknown, 1=NTLM, 2=Kerberos, 5=SAML, 6=OAuth, 99=Other |
| `is_mfa` | BOOLEAN | Whether MFA was used |
| `is_remote` | BOOLEAN | Whether login was remote |
| `logon_type` | STRING | `Interactive`, `Network`, `RemoteInteractive` |
| `logon_type_id` | INT | 2=Interactive, 3=Network, 10=RemoteInteractive, 99=Other |
| `action_id` | INT | 0=Unknown, 1=Allowed, 2=Denied, 99=Other |
| `action` | STRING | Action name |
| `disposition_id` | INT | 1=Allowed, 2=Blocked |
| `disposition` | STRING | Disposition name |
| `status_id` | INT | 1=Success, 2=Failure |
| `status` | STRING | `"Success"` or `"Failure"` |
| `status_code` | STRING | Vendor status code |
| `status_detail` | STRING | Failure reason |
| `message` | STRING | Human-readable description |

Plus: `user.*`, `session.*`, `src_endpoint.*`, `dst_endpoint.*`, `service.*`,
`actor.*`, `metadata.*`, `enrichments`, `observables`, `cloud.*`.

> Template: `ocsf_templates/identity_access_management/authentication.yaml`

---

### authorize_session (class_uid: 3003)

| Field | Type | Notes |
|-------|------|-------|
| `activity_id` | INT | 1=Assign Privileges, 2=Revoke Privileges, 99=Other |
| `category_name` | STRING | `"Identity & Access Management"` |
| `category_uid` | INT | `CAST(3 AS INT)` |
| `class_name` | STRING | `"Authorize Session"` |
| `class_uid` | INT | `CAST(3003 AS INT)` |
| `action_id` | INT | 1=Allowed, 2=Denied |
| `action` | STRING | Action name |
| `disposition_id` | INT | 1=Allowed, 2=Blocked |
| `disposition` | STRING | Disposition name |
| `status_id` | INT | 1=Success, 2=Failure |
| `status` | STRING | Status name |
| `status_code` | STRING | Vendor status code |
| `status_detail` | STRING | Status details |

Plus: `user.*`, `session.*`, `src_endpoint.*`, `dst_endpoint.*`, `service.*`,
`actor.*`, `policy.*`, `metadata.*`, `enrichments`, `observables`.

> Template: `ocsf_templates/identity_access_management/authorize_session.yaml`

---

### account_change (class_uid: 3001)

| Field | Type | Notes |
|-------|------|-------|
| `activity_id` | INT | 1=Create, 2=Enable, 3=Password Change, 4=Password Reset, 5=Disable, 6=Delete, 7=Attach Policy, 8=Detach Policy, 9=Lock, 10=MFA Enable, 11=MFA Disable, 99=Other |
| `category_name` | STRING | `"Identity & Access Management"` |
| `category_uid` | INT | `CAST(3 AS INT)` |
| `class_name` | STRING | `"Account Change"` |
| `class_uid` | INT | `CAST(3001 AS INT)` |
| `user.name` | STRING | Target user (account being changed) |
| `user.uid` | STRING | Target user ID |
| `user_result.name` | STRING | New username after change |
| `actor.user.name` | STRING | User who made the change |

Plus: `src_endpoint.*`, `metadata.*`, `enrichments`, `observables`, `cloud.*`.

> Template: `ocsf_templates/identity_access_management/account_change.yaml`

---

### group_management (class_uid: 3006)

| Field | Type | Notes |
|-------|------|-------|
| `activity_id` | INT | 1=Create, 2=Update, 3=Delete, 4=Add User, 5=Remove User |
| `category_name` | STRING | `"Identity & Access Management"` |
| `category_uid` | INT | `CAST(3 AS INT)` |
| `class_name` | STRING | `"Group Management"` |
| `class_uid` | INT | `CAST(3006 AS INT)` |
| `group.name` | STRING | Group name |
| `group.uid` | STRING | Group unique ID |
| `user.name` | STRING | User added/removed (if applicable) |
| `actor.user.name` | STRING | User who performed the action |

> Template: `ocsf_templates/identity_access_management/group_management.yaml`

---

## System Activity Category (category_uid: 1)

> **Key difference**: System activity uses `device.*` instead of `src_endpoint.*`/`dst_endpoint.*`.

### process_activity (class_uid: 1007)

| Field | Type | Notes |
|-------|------|-------|
| `activity_id` | INT | 1=Launch, 2=Terminate, 3=Open, 4=Inject, 5=Set User ID |
| `category_name` | STRING | `"System Activity"` |
| `category_uid` | INT | `CAST(1 AS INT)` |
| `class_name` | STRING | `"Process Activity"` |
| `class_uid` | INT | `CAST(1007 AS INT)` |
| `process.name` | STRING | Process name |
| `process.pid` | INT | Process ID |
| `process.uid` | STRING | Process unique ID |
| `process.cmd_line` | STRING | Command line |
| `process.file.path` | STRING | Executable path |
| `process.file.name` | STRING | Executable name |
| `process.file.hashes` | ARRAY | Hash objects: `ARRAY(NAMED_STRUCT('algorithm_id', CAST(3 AS INT), 'algorithm', 'SHA-256', 'value', sha256))` |
| `process.parent_process.name` | STRING | Parent process name |
| `process.parent_process.pid` | INT | Parent PID |
| `process.parent_process.cmd_line` | STRING | Parent command line |
| `process.user.name` | STRING | Process owner username |
| `process.user.uid` | STRING | Process owner user ID |
| `process.session.uid` | STRING | Session ID |
| `actor.process.name` | STRING | Injector/actor process name |
| `actor.process.pid` | INT | Injector/actor PID |
| `actor.user.name` | STRING | Actor username |
| `device.hostname` | STRING | Device hostname |
| `device.ip` | STRING | Device IP address |
| `device.uid` | STRING | Device unique ID |
| `exit_code` | INT | Process exit code |
| `injection_type` | STRING | Injection type name |
| `injection_type_id` | INT | 0=Unknown, 1=Remote Thread, 2=Memory Mapped, 99=Other |
| `status_id` | INT | 1=Success, 2=Failure |

> Template: `ocsf_templates/system_activity/process_activity.yaml`

---

### file_activity (class_uid: 1001)

| Field | Type | Notes |
|-------|------|-------|
| `activity_id` | INT | 1=Create, 2=Read, 3=Write, 4=Rename, 5=Delete, 6=Mount, 7=Unmount, 8=Encrypt, 9=Decrypt, 10=Open, 11=Modify Permissions, 99=Other |
| `category_name` | STRING | `"System Activity"` |
| `category_uid` | INT | `CAST(1 AS INT)` |
| `class_name` | STRING | `"File System Activity"` |
| `class_uid` | INT | `CAST(1001 AS INT)` |
| `file.name` | STRING | File name |
| `file.path` | STRING | Full file path |
| `actor.user.name` | STRING | User performing the action |
| `actor.user.uid` | STRING | User ID |
| `actor.process.name` | STRING | Process performing the action |
| `actor.process.pid` | INT | Process ID |
| `actor.process.cmd_line` | STRING | Process command line |
| `device.hostname` | STRING | Device hostname |
| `device.ip` | STRING | Device IP |
| `device.uid` | STRING | Device unique ID |
| `status_id` | INT | 1=Success, 2=Failure |

> Template: `ocsf_templates/system_activity/file_activity.yaml`

---

### script_activity (class_uid: 1008)

| Field | Type | Notes |
|-------|------|-------|
| `activity_id` | INT | 1=Create, 2=Read, 3=Update, 4=Delete, 5=Execute |
| `category_name` | STRING | `"System Activity"` |
| `category_uid` | INT | `CAST(1 AS INT)` |
| `class_name` | STRING | `"Script Activity"` |
| `class_uid` | INT | `CAST(1008 AS INT)` |
| `script.name` | STRING | Script name |
| `script.uid` | STRING | Script unique ID |
| `script.type` | STRING | Script type name |
| `script.type_id` | INT | Script type ID |
| `script.file.name` | STRING | Script file name |
| `script.file.path` | STRING | Script file path |
| `script.script_content.value` | STRING | Script content (string) |
| `script.script_content.is_truncated` | BOOLEAN | Whether content was truncated |
| `actor.user.name` | STRING | User who executed the script |
| `device.hostname` | STRING | Device hostname |
| `device.ip` | STRING | Device IP |

> Template: `ocsf_templates/system_activity/script_activity.yaml`

---

## Findings Category (category_uid: 2)

### vulnerability_finding (class_uid: 2002)

| Field | Type | Notes |
|-------|------|-------|
| `activity_id` | INT | 1=Create, 2=Update, 3=Close |
| `category_name` | STRING | `"Findings"` |
| `category_uid` | INT | `CAST(2 AS INT)` |
| `class_name` | STRING | `"Vulnerability Finding"` |
| `class_uid` | INT | `CAST(2002 AS INT)` |
| `finding_info.title` | STRING | Vulnerability title |
| `finding_info.desc` | STRING | Vulnerability description |
| `finding_info.uid` | STRING | Finding unique ID |
| `finding_info.created_time` | TIMESTAMP | When finding was created |
| `finding_info.first_seen_time` | TIMESTAMP | When first observed |
| `finding_info.last_seen_time` | TIMESTAMP | When last observed |
| `finding_info.src_url` | STRING | Reference URL (e.g. CVE link) |
| `severity_id` | INT | 1=Info, 2=Low, 3=Medium, 4=High, 5=Critical |
| `severity` | STRING | Severity name |
| `status_id` | INT | 1=New, 2=In Progress, 3=Suppressed, 4=Resolved |
| `status` | STRING | Status name |
| `device.hostname` | STRING | Affected device |
| `device.ip` | STRING | Affected device IP |
| `device.uid` | STRING | Affected device ID |
| `vulnerabilities` | ARRAY | Array of vulnerability detail objects |
| `start_time` | TIMESTAMP | Scan start time |
| `end_time` | TIMESTAMP | Scan end time |

> Template: `ocsf_templates/findings/vulnerability_finding.yaml`

---

### data_security_finding (class_uid: 2006)

| Field | Type | Notes |
|-------|------|-------|
| `activity_id` | INT | 1=Create, 2=Update, 3=Close |
| `category_name` | STRING | `"Findings"` |
| `category_uid` | INT | `CAST(2 AS INT)` |
| `class_name` | STRING | `"Data Security Finding"` |
| `class_uid` | INT | `CAST(2006 AS INT)` |
| `finding_info.title` | STRING | Finding title |
| `finding_info.uid` | STRING | Finding unique ID |
| `severity_id` | INT | 1=Info through 5=Critical |
| `severity` | STRING | Severity name |
| `status_id` | INT | 1=New, 2=In Progress, 3=Suppressed, 4=Resolved |
| `device.hostname` | STRING | Affected device |
| `resources` | ARRAY | Affected resources |

> Template: `ocsf_templates/findings/data_security_finding.yaml`

---

### detection_finding (class_uid: 2004)

Used for security detections from EDR, SIEM, IDS/IPS, alert platforms, and vulnerability scanners
that have triggered an alert (e.g. GitHub Dependabot alerts, CrowdStrike detections).

| Field | Type | Notes |
|-------|------|-------|
| `activity_id` | INT | 1=Create, 2=Update, 3=Close, 99=Other |
| `category_name` | STRING | `"Findings"` |
| `category_uid` | INT | `CAST(2 AS INT)` |
| `class_name` | STRING | `"Detection Finding"` |
| `class_uid` | INT | `CAST(2004 AS INT)` |
| `finding_info.title` | STRING | Detection/alert title |
| `finding_info.uid` | STRING | Detection unique ID |
| `finding_info.desc` | STRING | Detection description |
| `finding_info.created_time` | TIMESTAMP | When finding was created |
| `finding_info.first_seen_time` | TIMESTAMP | When first observed |
| `finding_info.last_seen_time` | TIMESTAMP | When last observed |
| `finding_info.src_url` | STRING | Link to the detection rule or alert |
| `finding_info.analytic.name` | STRING | Rule or analytic name that triggered |
| `finding_info.analytic.uid` | STRING | Rule ID |
| `finding_info.attacks` | ARRAY | MITRE ATT&CK tactic/technique mappings |
| `confidence` | STRING | `"High"`, `"Medium"`, `"Low"` |
| `confidence_id` | INT | 0=Unknown, 1=Low, 2=Medium, 3=High, 99=Other |
| `confidence_score` | INT | Vendor numerical score (0-100) |
| `is_alert` | BOOLEAN | Whether promoted to alert |
| `impact` | STRING | Impact level name |
| `impact_id` | INT | 0=Unknown, 1=Low, 2=Medium, 3=High, 99=Other |
| `impact_score` | INT | Vendor numerical impact score |
| `risk_level` | STRING | Risk level name |
| `risk_level_id` | INT | 0=Info, 1=Low, 2=Medium, 3=High, 4=Critical |
| `risk_score` | INT | Vendor risk score |
| `severity_id` | INT | 1=Info through 5=Critical |
| `severity` | STRING | Severity name |
| `status_id` | INT | 0=Unknown, 1=New, 2=In Progress, 3=Suppressed, 4=Resolved, 99=Other |
| `status` | STRING | Status name |
| `message` | STRING | Human-readable detection summary |
| `evidences` | ARRAY\<VARIANT\> | Evidence artifacts supporting the detection |
| `remediations` | ARRAY | Remediation steps: `ARRAY<STRUCT<desc: STRING, kb_articles: ARRAY<STRING>>>` |
| `resources` | ARRAY | Affected resources: hostname, ip, name, uid |
| `device.hostname` | STRING | Device where detection occurred |
| `device.ip` | STRING | Device IP |
| `device.uid` | STRING | Device unique ID |
| `src_endpoint.ip` | STRING | Source endpoint IP |
| `actor.user.name` | STRING | User associated with the detection |
| `cloud.provider` | STRING | Cloud provider (for cloud detections) |
| `start_time` | TIMESTAMP | Start of detection window |
| `end_time` | TIMESTAMP | End of detection window |

Plus: `metadata.*`, `enrichments`, `observables`, `cloud.*`, `unmapped`.

> No template yet — copy fields from `ocsf_templates/findings/data_security_finding.yaml` and adjust class_uid/class_name.

---

## Application Activity Category (category_uid: 6)

### api_activity (class_uid: 6003)

| Field | Type | Notes |
|-------|------|-------|
| `activity_id` | INT | 1=Create, 2=Read, 3=Update, 4=Delete, 5=Connect |
| `category_name` | STRING | `"Application Activity"` |
| `category_uid` | INT | `CAST(6 AS INT)` |
| `class_name` | STRING | `"API Activity"` |
| `class_uid` | INT | `CAST(6003 AS INT)` |
| `api.operation` | STRING | API operation name |
| `api.request.uid` | STRING | Request unique ID |
| `api.response.code` | INT | API response code |
| `api.response.message` | STRING | Response message |
| `http_request.http_method` | STRING | `GET`, `POST`, `PUT`, `DELETE` |
| `http_request.url` | STRING | API endpoint URL |
| `http_request.user_agent` | STRING | User-Agent |
| `http_response.code` | INT | HTTP status code |
| `http_response.latency` | INT | Response time in ms |
| `actor.user.name` | STRING | Calling user |
| `actor.user.uid` | STRING | Calling user ID |
| `src_endpoint.ip` | STRING | Client IP |
| `dst_endpoint.ip` | STRING | API server IP |
| `status_id` | INT | 1=Success, 2=Failure |
| `resources` | ARRAY | Affected resources |

Plus: `cloud.*`, `metadata.*`, `enrichments`, `observables`.

> Template: `ocsf_templates/application_activity/api_activity.yaml`

---

### datastore_activity (class_uid: 6005)

| Field | Type | Notes |
|-------|------|-------|
| `activity_id` | INT | 1=Create, 2=Read, 3=Update, 4=Delete, 5=Query, 6=Allocate, 7=Deallocate, 99=Other |
| `category_name` | STRING | `"Application Activity"` |
| `category_uid` | INT | `CAST(6 AS INT)` |
| `class_name` | STRING | `"Datastore Activity"` |
| `class_uid` | INT | `CAST(6005 AS INT)` |
| `database.name` | STRING | Database name |
| `database.uid` | STRING | Database unique ID |
| `database.type` | STRING | Database type: `mysql`, `postgres`, `mongodb`, etc. |
| `databucket.name` | STRING | Bucket or container name |
| `databucket.uid` | STRING | Bucket unique ID |
| `table.name` | STRING | Table name |
| `table.uid` | STRING | Table unique ID |
| `api.operation` | STRING | Operation performed: `SELECT`, `INSERT`, `DELETE`, etc. |
| `http_request.url` | STRING | API endpoint URL (when accessed via HTTP/REST) |
| `http_request.http_method` | STRING | HTTP method: `GET`, `POST`, etc. |
| `http_response.code` | INT | HTTP response code |
| `actor.user.name` | STRING | User performing the operation |
| `actor.user.uid` | STRING | User ID |
| `src_endpoint.ip` | STRING | Client IP address |
| `dst_endpoint.ip` | STRING | Database server IP |
| `dst_endpoint.port` | INT | Database port |
| `device.hostname` | STRING | Device hostname (for system-originated operations) |
| `status_id` | INT | 1=Success, 2=Failure |
| `action_id` | INT | 0=Unknown, 1=Allowed, 2=Denied, 99=Other |

> Note: Template header comment incorrectly shows "Class UID: 4007 | Category: Network Activity" — the correct values are class_uid 6005, category_uid 6 (Application Activity) as shown by the CAST literals in the template body.

> Template: `ocsf_templates/network_activity/datastore_activity.yaml`

---

## OCSF Numeric ID Quick Reference

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

### status_id
| ID | Name |
|----|------|
| 0 | Unknown |
| 1 | Success |
| 2 | Failure |
| 99 | Other |

### action_id
| ID | Name |
|----|------|
| 0 | Unknown |
| 1 | Allowed |
| 2 | Denied |
| 99 | Other |

### disposition_id
| ID | Name |
|----|------|
| 0 | Unknown |
| 1 | Allowed |
| 2 | Blocked |
| 3 | Quarantined |
| 4 | Isolated |
| 5 | Deleted |
| 10 | Detected |
| 14 | Delayed |
| 17 | Logged |
| 19 | Alert |

### activity_id by class

**network_activity**:
1=Open, 2=Close, 3=Refuse, 4=Fail, 5=Traffic, 6=Scan, 7=Probe, 99=Other

**http_activity**:
1=Request, 2=Response, 3=Upload, 4=Download, 5=Send, 6=Receive, 99=Other

**dns_activity**:
1=Query, 2=Response, 99=Other

**dhcp_activity / ssh_activity**:
1=Open, 2=Close, 3=Send, 4=Receive, 99=Other

**authentication**:
1=Logon, 2=Logoff, 3=Authentication Ticket, 4=Service Ticket Request, 99=Other

**authorize_session**:
1=Assign Privileges, 2=Revoke Privileges, 99=Other

**account_change**:
1=Create, 2=Enable, 3=Password Change, 4=Password Reset, 5=Disable, 6=Delete, 7=Attach Policy, 8=Detach Policy, 9=Lock, 10=MFA Enable, 11=MFA Disable, 99=Other

**process_activity**:
1=Launch, 2=Terminate, 3=Open, 4=Inject, 5=Set User ID, 6=Rename, 99=Other

**file_activity**:
1=Create, 2=Read, 3=Write, 4=Rename, 5=Delete, 6=Mount, 7=Unmount, 8=Encrypt, 9=Decrypt, 10=Open, 11=Modify Permissions, 99=Other

**api_activity**:
1=Create, 2=Read, 3=Update, 4=Delete, 5=Connect, 99=Other

**datastore_activity**:
1=Create, 2=Read, 3=Update, 4=Delete, 5=Query, 6=Allocate, 7=Deallocate, 99=Other

**vulnerability_finding / data_security_finding / detection_finding**:
1=Create, 2=Update, 3=Close, 99=Other

### auth_protocol_id (authentication table)
| ID | Name |
|----|------|
| 0 | Unknown |
| 1 | NTLM |
| 2 | Kerberos |
| 3 | Digest |
| 4 | OpenID |
| 5 | SAML |
| 6 | OAuth |
| 7 | SSO |
| 8 | CHAP |
| 9 | PAP |
| 10 | RADIUS |
| 11 | LDAP |
| 99 | Other |

### logon_type_id (authentication table)
| ID | Name |
|----|------|
| 0 | Unknown |
| 1 | System |
| 2 | Interactive |
| 3 | Network |
| 4 | Batch |
| 5 | Service |
| 7 | Unlock |
| 8 | Network Cleartext |
| 9 | New Credentials |
| 10 | RemoteInteractive |
| 11 | CachedInteractive |
| 12 | Cached Remote Interactive |
| 99 | Other |

### rcode_id (dns_activity table)
| ID | Name |
|----|------|
| 0 | NoError |
| 1 | FormError |
| 2 | ServError |
| 3 | NXDomain |
| 4 | NotImp |
| 5 | Refused |
| 8 | NXRRSet |
| 99 | Other |
