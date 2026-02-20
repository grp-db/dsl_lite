# OCSF: Authentication

**Class UID:** 3002  
**Category:** Identity & Access Management (Category 3)  
**Reference:** [schema.ocsf.io/1.7.0/classes/authentication](https://schema.ocsf.io/1.7.0/classes/authentication)

## Overview

Tracks user authentication events (logon, logoff, authentication failures).

## Table: `authentication`

**Bold** columns are common across OCSF tables in this category (Identity & Access Management) and should be included in YAML mappings.

| Column | Type | Description |
|--------|------|-------------|
| **`dsl_id`** | STRING NOT NULL | Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers. |
| **`action`** | STRING | The action taken by the system (e.g., Allowed, Denied). See action_id for numeric representation. |
| **`action_id`** | INT | The action ID: 0=Unknown, 1=Allowed, 2=Denied, 99=Other. |
| `activity` | STRING | The authentication activity name (e.g., Logon, Logoff). Normalized value based on activity_id. |
| **`activity_id`** | INT | The authentication activity ID: 0=Unknown, 1=Logon, 2=Logoff, 3=Authentication Ticket, 4=Service Ticket Request, 99=Other. |
| **`activity_name`** | STRING | The authentication activity name (e.g., Logon, Logoff). |
| **`actor`** | STRUCT | The actor (user or process) that performed the authentication. Fields: app_name, app_uid, authorizations, idp, process (cmd_line, cpid, name, pid, session, uid, user), user. |
| `auth_factors` | ARRAY&lt;STRUCT&gt; | Authentication factors used (e.g., password, MFA token, biometric). Struct: factor_type, factor_type_id. |
| `auth_protocol` | STRING | The authentication protocol (e.g., NTLM, Kerberos, SAML, OAuth). |
| `auth_protocol_id` | INT | The authentication protocol ID: 0=Unknown, 1=NTLM, 2=Kerberos, 3=Digest, 4=OpenID, 5=SAML, 6=OAuth, 7=SSO, 8=CHAP, 9=PAP, 10=RADIUS, 11=LDAP, 99=Other. |
| **`category_name`** | STRING | The OCSF category name: Identity & Access Management. |
| **`category_uid`** | INT | The OCSF category unique identifier: 3 for Identity & Access Management. |
| **`class_name`** | STRING | The OCSF class name: Authentication. |
| **`class_uid`** | INT | The OCSF class unique identifier: 3002 for Authentication. |
| **`cloud`** | STRUCT | Cloud environment. Fields: account (name, uid), cloud_partition, project_uid, provider, region, zone. |
| `disposition` | STRING | The event disposition name (e.g., Allowed, Blocked, Quarantined). Describes the outcome/action taken. |
| `disposition_id` | INT | The disposition ID: 0=Unknown, 1=Allowed, 2=Blocked, 3=Quarantined, 4=Isolated, 5=Deleted, 6=Dropped, 7=Custom Action, 8=Approved, 9=Restored, 10=Exonerated, 99=Other. |
| **`dst_endpoint`** | STRUCT | The destination endpoint (authentication target/server). [Endpoint reference](../../ocsf_ddl_fields/ocsf-endpoint.md). |
| **`enrichments`** | ARRAY&lt;STRUCT&gt; | Additional enrichment data from threat intel, GeoIP, or other sources. Struct: data, desc, name, value. |
| `is_mfa` | BOOLEAN | Indicates whether multi-factor authentication was used. |
| `is_remote` | BOOLEAN | Indicates whether the authentication was from a remote location. |
| `logon_type` | STRING | The logon type name (e.g., Interactive, Network, Service). |
| `logon_type_id` | INT | The Windows logon type ID: 0=Unknown, 2=Interactive, 3=Network, 4=Batch, 5=Service, 7=Unlock, 8=NetworkCleartext, 9=NewCredentials, 10=RemoteInteractive, 11=CachedInteractive, 99=Other. |
| **`message`** | STRING | Human-readable description of the event. |
| **`metadata`** | STRUCT | Event metadata. Fields: correlation_uid, event_code, log_level, log_name, log_provider, log_format, log_version, logged_time, modified_time, original_time, processed_time, product (name, vendor_name, version), tags, tenant_uid, uid, version. See [metadata reference](../../ocsf_ddl_fields/ocsf-metadata.md). |
| **`observables`** | ARRAY&lt;STRUCT&gt; | Observable artifacts extracted from the event (e.g., IP addresses, usernames, domains) for threat hunting. Struct: name, type, value. |
| **`raw_data`** | VARIANT | The original raw event data in its native format (JSON, XML, text, etc.). |
| **`service`** | STRUCT | The service or application being authenticated to. Fields: name, uid. |
| **`session`** | STRUCT | Session information including creation time, expiration, and session attributes. Fields: created_time, credential_uid, expiration_reason, expiration_time, is_mfa, is_remote, is_vpn, issuer, terminal, uid, uid_alt, uuid. |
| **`severity`** | STRING | The event severity name (e.g., Informational, Low, Medium, High, Critical). |
| **`severity_id`** | INT | The event severity ID: 0=Unknown, 1=Informational, 2=Low, 3=Medium, 4=High, 5=Critical, 6=Fatal, 99=Other. |
| **`src_endpoint`** | STRUCT | The source endpoint (client/device initiating authentication). [Endpoint reference](../../ocsf_ddl_fields/ocsf-endpoint.md). |
| **`status`** | STRING | The event status name (e.g., Success, Failure). |
| **`status_code`** | STRING | The vendor-specific status or error code. |
| **`status_detail`** | STRING | Additional details about the status or error. |
| **`status_id`** | INT | The event status ID: 0=Unknown, 1=Success, 2=Failure, 99=Other. |
| **`time`** | TIMESTAMP | The event occurrence time (required field). |
| **`timezone_offset`** | INT | The timezone offset in minutes from UTC. |
| **`type_name`** | STRING | The event type name, formatted as "Authentication: &lt;activity_name&gt;". |
| **`type_uid`** | BIGINT | The event type unique identifier (class_uid * 100 + activity_id). |
| **`unmapped`** | VARIANT | Vendor-specific fields that do not map to OCSF schema attributes. |
| **`user`** | STRUCT | The authenticated user. Fields: has_mfa, name, type, type_id, uid. |

**See also:** [OCSF ID reference](../../ocsf_ddl_fields/ocsf-ids.md) (incl. auth_protocol_id, logon_type_id) · [OCSF endpoint reference](../../ocsf_ddl_fields/ocsf-endpoint.md) · [OCSF metadata reference](../../ocsf_ddl_fields/ocsf-metadata.md) · [OCSF cloud reference](../../ocsf_ddl_fields/ocsf-cloud.md) · [OCSF IAM common structs](../../ocsf_ddl_fields/ocsf-iam-common-structs.md) (session, user, service) · [OCSF enrichments/observables](../../ocsf_ddl_fields/ocsf-enrichments-observables.md)

## Delta table properties

- `delta.enableDeletionVectors` = true  
- `delta.minReaderVersion` = 3, `delta.minWriterVersion` = 7
