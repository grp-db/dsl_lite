# OCSF: Process Activity

**Class UID:** 1007  
**Category:** System Activity (Category 1)  
**Reference:** [schema.ocsf.io/1.7.0/classes/process_activity](https://schema.ocsf.io/1.7.0/classes/process_activity)

## Overview

Tracks process lifecycle events (launch, terminate, injection, etc.).

**Commonly used for:** EDR logs, Windows Security logs, Sysmon, auditd, system monitoring.

## Table: `process_activity`

**Bold** columns are common across OCSF tables in this category (System Activity) and should be included in YAML mappings.

| Column | Type | Description |
|--------|------|-------------|
| **`dsl_id`** | STRING NOT NULL | Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers. |
| **`action`** | STRING | The action taken on the process (e.g., Allowed, Blocked, Terminated). |
| **`action_id`** | INT | The action ID: 0=Unknown, 1=Allowed, 2=Denied, 99=Other. |
| `activity` | STRING | The process activity name (e.g., Launch, Terminate, Inject). Normalized value based on activity_id. |
| **`activity_id`** | INT | The process activity ID: 0=Unknown, 1=Launch (process started), 2=Terminate (process ended), 3=Open (process handle opened), 4=Inject (code injection), 5=Set User ID, 6=Rename, 99=Other. |
| **`activity_name`** | STRING | The process activity name (e.g., Launch, Terminate). |
| `actor` | STRUCT | The actor (parent process or user) that initiated the process activity. Fields: app_name, app_uid, authorizations, idp, process (cmd_line, cpid, name, pid, session, uid, user), user. |
| **`category_name`** | STRING | The OCSF category name: System Activity. |
| **`category_uid`** | INT | The OCSF category unique identifier: 1 for System Activity. |
| **`class_name`** | STRING | The OCSF class name: Process Activity. |
| **`class_uid`** | INT | The OCSF class unique identifier: 1007 for Process Activity. |
| `device` | STRUCT | The device/host where the process activity occurred. Fields: created_time, desc, domain, groups, hostname, ip, is_compliant, is_managed, is_personal, is_trusted, name, region, risk_level, risk_level_id, risk_score, subnet, type, type_id, uid. |
| **`disposition`** | STRING | The disposition name (e.g., Allowed, Blocked, Quarantined). For EDR, indicates if process was allowed to run or blocked. |
| **`disposition_id`** | INT | The disposition ID: 0=Unknown, 1=Allowed, 2=Blocked, 3=Quarantined, 4=Isolated, 5=Deleted, 99=Other. |
| `enrichments` | ARRAY&lt;STRUCT&gt; | Additional enrichment data from threat intel (e.g., malicious process hashes), behavioral analysis. Struct: data, desc, name, value. |
| `exit_code` | INT | The process exit code (0=success, non-zero=error). |
| `injection_type` | STRING | The type of code injection technique used (e.g., DLL Injection, Process Hollowing, Thread Execution Hijacking). |
| `injection_type_id` | INT | The injection type ID: 0=Unknown, 1=CreateRemoteThread, 2=QueueUserAPC, 3=SetWindowsHookEx, 4=Process Hollowing, 5=AppInit DLLs, 99=Other. |
| **`message`** | STRING | Human-readable description of the process event. |
| **`metadata`** | STRUCT | Event metadata. Fields: correlation_uid, event_code, log_level, log_name, log_provider, log_format, log_version, logged_time, modified_time, original_time, processed_time, product (name, vendor_name, version), tags, tenant_uid, uid, version. See [metadata reference](../../ocsf_ddl_fields/ocsf-metadata.md). |
| `module` | STRUCT | Module/DLL loaded by the process. Includes file path, load address, load type. Fields: base_address, file (name, path), function_name, load_type, load_type_id, start_address, type. |
| **`observables`** | ARRAY&lt;STRUCT&gt; | Observable artifacts: process names, file hashes, command lines, parent processes—critical for threat hunting. Struct: name, type, value. |
| `process` | STRUCT | The process details: name, PID, command line, parent PID, user, session info. Fields: cmd_line, cpid, name, pid, session (created_time, credential_uid, expiration_*, is_mfa, is_remote, is_vpn, issuer, terminal, uid, uuid), uid, user (has_mfa, name, type, type_id, uid). |
| **`raw_data`** | VARIANT | The original raw process log in its native format. |
| `requested_permissions` | INT | The access rights/permissions requested for the process. |
| **`severity`** | STRING | The event severity name (e.g., Informational, Low, Medium, High, Critical). |
| **`severity_id`** | INT | The event severity ID: 0=Unknown, 1=Informational, 2=Low, 3=Medium, 4=High, 5=Critical, 6=Fatal, 99=Other. |
| **`status`** | STRING | The event status name (e.g., Success, Failure). |
| **`status_code`** | STRING | The vendor-specific status or error code. |
| **`status_detail`** | STRING | Additional details about the process status. |
| **`status_id`** | INT | The event status ID: 0=Unknown, 1=Success, 2=Failure, 99=Other. |
| **`time`** | TIMESTAMP | The process event time (required field). |
| **`timezone_offset`** | INT | The timezone offset in minutes from UTC. |
| **`type_name`** | STRING | The event type name, formatted as "Process Activity: &lt;activity_name&gt;". |
| **`type_uid`** | BIGINT | The event type unique identifier (class_uid * 100 + activity_id). |
| **`unmapped`** | VARIANT | Vendor-specific process fields that do not map to OCSF schema attributes. |

**See also:** [OCSF ID reference](../../ocsf_ddl_fields/ocsf-ids.md) (incl. injection_type_id) · [OCSF metadata reference](../../ocsf_ddl_fields/ocsf-metadata.md) · [OCSF enrichments/observables](../../ocsf_ddl_fields/ocsf-enrichments-observables.md)

## Delta table properties

- `delta.enableDeletionVectors` = true  
- `delta.minReaderVersion` = 3, `delta.minWriterVersion` = 7
