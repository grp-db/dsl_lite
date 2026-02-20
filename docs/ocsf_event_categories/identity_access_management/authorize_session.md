# OCSF: Authorize Session

**Class UID:** 3003  
**Category:** Identity & Access Management (Category 3)  
**Reference:** [schema.ocsf.io/1.7.0/classes/authorize_session](https://schema.ocsf.io/1.7.0/classes/authorize_session)

## Overview

Tracks authorization and access control decisions (permission grants/denials, role assignments).

**Commonly used for:** IAM policy evaluations, access denied events, privilege escalations, Cisco IOS authorization failures.

## Table: `authorize_session`

**Bold** columns are common across OCSF tables in this category (Identity & Access Management) and should be included in YAML mappings.

| Column | Type | Description |
|--------|------|-------------|
| **`dsl_id`** | STRING NOT NULL | Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers. |
| **`action`** | STRING | The action taken on the authorization request (e.g., Allowed, Denied). |
| **`action_id`** | INT | The action ID: 0=Unknown, 1=Allowed, 2=Denied, 99=Other. |
| **`activity_id`** | INT | The authorization activity ID: 0=Unknown, 1=Assign Privileges, 2=Revoke Privileges, 99=Other. |
| **`activity_name`** | STRING | The authorization activity name (e.g., Assign Privileges, Revoke Privileges). |
| **`actor`** | STRUCT | The actor (user or service) requesting authorization. Fields: app_name, app_uid, authorizations, idp, process (cmd_line, cpid, name, pid, session, uid, user), user. |
| **`category_name`** | STRING | The OCSF category name: Identity & Access Management. |
| **`category_uid`** | INT | The OCSF category unique identifier: 3 for Identity & Access Management. |
| **`class_name`** | STRING | The OCSF class name: Authorize Session. |
| **`class_uid`** | INT | The OCSF class unique identifier: 3003 for Authorize Session. |
| **`cloud`** | STRUCT | Cloud environment information (AWS, Azure, GCP) for cloud IAM events. Fields: account, cloud_partition, project_uid, provider, region, zone. |
| `device` | STRUCT | The device from which authorization was requested (includes OS, hardware info, compliance status). Fields: created_time, hostname, hw_info (bios_*, chassis, cpu_*, ram_size, serial_number), hypervisor, instance_uid, ip, is_compliant, is_managed, is_personal, is_trusted, last_seen_time, location, mac, name, network_interfaces, org, os (build, name, version, type, etc.), region, risk_level, risk_level_id, subnet_uid, type, type_id, uid, uid_alt, vpc_uid, zone. |
| **`dst_endpoint`** | STRUCT | The destination resource/service being accessed. [Endpoint reference](../../ocsf_ddl_fields/ocsf-endpoint.md). |
| **`enrichments`** | ARRAY&lt;STRUCT&gt; | Additional enrichment data from threat intel or risk scoring. Struct: data, desc, name, value. |
| `http_request` | STRUCT | HTTP request details for web/API authorization requests. Fields: http_headers (name, value), http_method, referrer, url (hostname, path, port, query_string, scheme, subdomain, text, url_string), user_agent, version, x_forwarded_for. |
| **`message`** | STRING | Human-readable description of the authorization event. |
| **`metadata`** | STRUCT | Event metadata. Fields: correlation_uid, event_code, log_level, log_name, log_provider, log_format, log_version, logged_time, modified_time, original_time, processed_time, product (name, vendor_name, version), tags, tenant_uid, uid, version. See [metadata reference](../../ocsf_ddl_fields/ocsf-metadata.md). |
| **`observables`** | ARRAY&lt;STRUCT&gt; | Observable artifacts: usernames, resource names, IP addresses—critical for access pattern analysis. Struct: name, type, value. |
| `policy` | STRUCT | The IAM policy that was evaluated for this authorization decision. Fields: desc, group (desc, name, privileges, type, uid), name, uid, version. |
| `privileges` | ARRAY&lt;STRING&gt; | The specific privileges/permissions requested (e.g., read, write, execute, admin). |
| **`raw_data`** | VARIANT | The original raw authorization log in its native format. |
| `resource` | STRUCT | The resource being accessed (e.g., S3 bucket, database, API endpoint, network device). Fields: cloud_partition, criticality, data, group, labels, name, namespace, owner (account, domain, groups, name, org, type, uid), region, type, uid, version. |
| **`service`** | STRUCT | The service or application being authorized (e.g., AWS S3, Azure AD, Cisco IOS). Fields: name, uid. |
| **`session`** | STRUCT | Session information including creation time, MFA status, remote/VPN flags. Same shape as authentication session. |
| **`severity`** | STRING | The event severity name (e.g., Informational, Low, Medium, High, Critical). |
| **`severity_id`** | INT | The event severity ID: 0=Unknown, 1=Informational, 2=Low, 3=Medium, 4=High, 5=Critical, 6=Fatal, 99=Other. |
| **`src_endpoint`** | STRUCT | The source endpoint (client making the authorization request). [Endpoint reference](../../ocsf_ddl_fields/ocsf-endpoint.md). |
| **`status`** | STRING | The event status name (e.g., Success, Failure). |
| **`status_code`** | STRING | The vendor-specific authorization status or error code. |
| **`status_detail`** | STRING | Additional details about why authorization was granted or denied. |
| **`status_id`** | INT | The event status ID: 0=Unknown, 1=Success, 2=Failure, 99=Other. |
| **`time`** | TIMESTAMP | The authorization event time (required field). |
| **`timezone_offset`** | INT | The timezone offset in minutes from UTC. |
| **`type_name`** | STRING | The event type name, formatted as "Authorize Session: &lt;activity_name&gt;". |
| **`type_uid`** | BIGINT | The event type unique identifier (class_uid * 100 + activity_id). |
| **`unmapped`** | VARIANT | Vendor-specific authorization fields that do not map to OCSF schema attributes. |
| **`user`** | STRUCT | The user requesting authorization. Fields: has_mfa, name, type, type_id, uid. |

**See also:** [OCSF ID reference](../../ocsf_ddl_fields/ocsf-ids.md) · [OCSF endpoint reference](../../ocsf_ddl_fields/ocsf-endpoint.md) · [OCSF metadata reference](../../ocsf_ddl_fields/ocsf-metadata.md) · [OCSF cloud reference](../../ocsf_ddl_fields/ocsf-cloud.md) · [OCSF IAM common structs](../../ocsf_ddl_fields/ocsf-iam-common-structs.md) (session, user, service) · [OCSF enrichments/observables](../../ocsf_ddl_fields/ocsf-enrichments-observables.md)

## Delta table properties

- `delta.enableDeletionVectors` = true  
- `delta.enableRowTracking` = true  
- `delta.minReaderVersion` = 3, `delta.minWriterVersion` = 7  
- `delta.parquet.compression.codec` = zstd
