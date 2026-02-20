# OCSF: DNS Activity

**Class UID:** 4003  
**Category:** Network Activity (Category 4)  
**Reference:** [schema.ocsf.io/1.7.0/classes/dns_activity](https://schema.ocsf.io/1.7.0/classes/dns_activity)

## Overview

Tracks DNS query and response events for threat detection and investigation.

**Commonly used for:** DNS server logs, DNS firewall logs, Zeek/Suricata DNS logs, Cloudflare Gateway, Pi-hole.

DNS Activity events capture DNS queries and responses for security monitoring, threat detection (e.g., DNS tunneling, DGA domains, C2 communication), and performance analysis. Critical for detecting malware, data exfiltration, and unauthorized DNS usage.

## Table: `dns_activity`

**Bold** columns are common across OCSF tables in this category (Network Activity) and should be included in YAML mappings.

| Column | Type | Description |
|--------|------|-------------|
| **`dsl_id`** | STRING NOT NULL | Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers. |
| **`action`** | STRING | The action taken (e.g., Allowed, Blocked for DNS filtering). |
| **`action_id`** | INT | The action ID: 0=Unknown, 1=Allowed, 2=Denied/Blocked, 99=Other. |
| **`activity`** | STRING | The DNS activity name (e.g., Query, Response). Normalized value based on activity_id. |
| **`activity_id`** | INT | The DNS activity ID: 0=Unknown, 1=Query (DNS request), 2=Response (DNS reply), 99=Other. |
| **`activity_name`** | STRING | The DNS activity name (e.g., Query, Response). |
| `answers` | ARRAY&lt;STRUCT&gt; | DNS response answers. Each answer: class (IN/CH), type (A/AAAA/CNAME/MX/TXT), rdata (resolved data), ttl (time-to-live in seconds). Struct: class, packet_uid, type, flag_ids, flags, rdata, ttl. |
| `app_name` | STRING | The application name that generated the DNS query (e.g., browser, email client). |
| **`category_name`** | STRING | The OCSF category name: Network Activity. |
| **`category_uid`** | INT | The OCSF category unique identifier: 4 for Network Activity. |
| **`class_name`** | STRING | The OCSF class name: DNS Activity. |
| **`class_uid`** | INT | The OCSF class unique identifier: 4003 for DNS Activity. |
| **`connection_info`** | STRUCT | Connection details: protocol (UDP/TCP), direction, connection UID. Fields: direction, direction_id, flag_history, protocol_name, protocol_num, protocol_ver, protocol_ver_id, uid. |
| **`disposition`** | STRING | The disposition name (e.g., Allowed, Blocked, Sinkholed). For DNS security, indicates if query was blocked/filtered. |
| **`disposition_id`** | INT | The disposition ID: 0=Unknown, 1=Allowed, 2=Blocked, 3=Quarantined, 4=Isolated, 5=Deleted, 6=Dropped, 99=Other. |
| **`dst_endpoint`** | STRUCT | The DNS server (resolver) that handled the query. Includes IP, port (typically 53), hostname. [Endpoint reference](../../ocsf_ddl_fields/ocsf-endpoint.md). |
| **`enrichments`** | ARRAY&lt;STRUCT&gt; | Additional enrichment data from threat intel (e.g., malicious domain indicators), GeoIP, or DNS reputation services. Struct: data, desc, name, value. |
| **`message`** | STRING | Human-readable description of the DNS event. |
| **`metadata`** | STRUCT | Event metadata. Fields: correlation_uid, event_code, log_level, log_name, log_provider, log_format, log_version, logged_time, modified_time, original_time, processed_time, product (name, vendor_name, version), tags, tenant_uid, uid, version. See [metadata reference](../../ocsf_ddl_fields/ocsf-metadata.md). |
| **`observables`** | ARRAY&lt;STRUCT&gt; | Observable artifacts: queried domains, resolved IPs, DNS servers—critical for threat hunting and IOC matching. Struct: name, type, value. |
| **`policy`** | STRUCT | DNS security policy or filtering rule that was applied (e.g., Cloudflare Gateway policy, Pi-hole blocklist). Fields: is_applied, name, uid, version. |
| `query` | STRUCT | DNS query details: hostname (FQDN queried), type (A/AAAA/CNAME/MX/TXT/etc), class (usually IN), opcode (QUERY/IQUERY/STATUS). Fields: class, packet_uid, type, hostname, opcode, opcode_id. |
| **`raw_data`** | VARIANT | The original raw DNS log in its native format. |
| `rcode` | STRING | DNS response code name (e.g., NoError, NXDomain, ServFail, Refused). Indicates query result status. |
| `rcode_id` | INT | DNS response code ID: 0=NoError (success), 1=FormErr, 2=ServFail, 3=NXDomain (domain not found), 4=NotImp, 5=Refused, 99=Other. |
| **`severity`** | STRING | The event severity name (e.g., Informational, Low, Medium, High, Critical). |
| **`severity_id`** | INT | The event severity ID: 0=Unknown, 1=Informational, 2=Low, 3=Medium, 4=High, 5=Critical, 6=Fatal, 99=Other. |
| **`src_endpoint`** | STRUCT | The DNS client (source of query). Includes client IP, hostname, port, geolocation. |
| **`status`** | STRING | The event status name (e.g., Success, Failure). |
| **`status_code`** | STRING | The vendor-specific status code. |
| **`status_detail`** | STRING | Additional details about the DNS query/response status. |
| **`status_id`** | INT | The event status ID: 0=Unknown, 1=Success, 2=Failure, 99=Other. |
| **`time`** | TIMESTAMP | The DNS query time (required field). |
| **`timezone_offset`** | INT | The timezone offset in minutes from UTC. |
| **`traffic`** | STRUCT | DNS traffic statistics (bytes/packets for query and response). Fields: bytes, bytes_in, bytes_missed, bytes_out, chunks, chunks_in, chunks_out, packets, packets_in, packets_out. |
| **`type_name`** | STRING | The event type name, formatted as "DNS Activity: &lt;activity_name&gt;". |
| **`type_uid`** | BIGINT | The event type unique identifier (class_uid * 100 + activity_id). |
| **`unmapped`** | VARIANT | Vendor-specific DNS fields that do not map to OCSF schema attributes (e.g., DNS flags, EDNS options). |

**See also:** [OCSF ID reference](../../ocsf_ddl_fields/ocsf-ids.md) (incl. rcode_id) · [OCSF endpoint reference](../../ocsf_ddl_fields/ocsf-endpoint.md) · [OCSF metadata reference](../../ocsf_ddl_fields/ocsf-metadata.md) · [OCSF enrichments/observables](../../ocsf_ddl_fields/ocsf-enrichments-observables.md) · [OCSF connection_info](../../ocsf_ddl_fields/ocsf-connection-info.md) · [OCSF traffic](../../ocsf_ddl_fields/ocsf-traffic.md)

## Delta table properties

- `delta.enableDeletionVectors` = true  
- `delta.minReaderVersion` = 3, `delta.minWriterVersion` = 7
