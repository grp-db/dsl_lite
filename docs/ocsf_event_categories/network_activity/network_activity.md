# OCSF: Network Activity

**Class UID:** 4001  
**Category:** Network Activity (Category 4)  
**Reference:** [schema.ocsf.io/1.7.0/classes/network_activity](https://schema.ocsf.io/1.7.0/classes/network_activity)

## Overview

Tracks network connection and traffic events (open, close, traffic flow, etc.).

**Commonly used for:** Zeek conn logs, firewall logs, VPC flow logs, network device logs.

## Table: `network_activity`

**Bold** columns are common across OCSF tables in this category (Network Activity) and should be included in YAML mappings.

| Column | Type | Description |
|--------|------|-------------|
| **`dsl_id`** | STRING NOT NULL | Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers. |
| **`action`** | STRING | The action taken by the network device (e.g., Allowed, Denied, Dropped). |
| **`action_id`** | INT | The action ID: 0=Unknown, 1=Allowed, 2=Denied, 99=Other. |
| **`activity`** | STRING | The network activity name (e.g., Open, Close, Traffic, Fail). Normalized value based on activity_id. |
| **`activity_id`** | INT | The network activity ID: 0=Unknown, 1=Open (connection established), 2=Close (connection terminated), 3=Refuse (connection refused), 4=Fail, 5=Traffic (data flow), 6=Scan, 7=Probe, 99=Other. |
| **`activity_name`** | STRING | The network activity name (e.g., Open, Close, Traffic). |
| **`category_name`** | STRING | The OCSF category name: Network Activity. |
| **`category_uid`** | INT | The OCSF category unique identifier: 4 for Network Activity. |
| **`class_name`** | STRING | The OCSF class name: Network Activity. |
| **`class_uid`** | INT | The OCSF class unique identifier: 4001 for Network Activity. |
| `cloud` | STRUCT | Cloud environment information (AWS, Azure, GCP). Fields: account (name, uid), cloud_partition, project_uid, provider, region, zone. |
| **`connection_info`** | STRUCT | Connection details: direction (Inbound/Outbound), protocol (TCP/UDP/ICMP), TCP flags, connection UID. Fields: direction, direction_id, flag_history, protocol_name, protocol_num, protocol_ver, protocol_ver_id, uid. |
| **`disposition`** | STRING | Disposition name. |
| **`disposition_id`** | INT | Disposition ID. |
| **`dst_endpoint`** | STRUCT | The destination endpoint (server/responder). Includes IP, port, hostname, geolocation. Fields: domain, hostname, instance_uid, interface_name, interface_uid, ip, name, port, svc_name, type, type_id, uid, location (city, continent, country, lat, long, postal_code), mac, vpc_uid, zone. |
| `end_time` | TIMESTAMP | The connection end/close time. |
| **`enrichments`** | ARRAY&lt;STRUCT&gt; | Additional enrichment data from threat intel, GeoIP, or other sources. Struct: data (VARIANT), desc, name, value. |
| **`message`** | STRING | Human-readable description of the network event. |
| **`metadata`** | STRUCT | Event metadata. Fields: correlation_uid, event_code, log_level, log_name, log_provider, log_format, log_version, logged_time, modified_time, original_time, processed_time, product (name, vendor_name, version), tags, tenant_uid, uid, version. See [metadata reference](../../ocsf_ddl_fields/ocsf-metadata.md). |
| **`observables`** | ARRAY&lt;STRUCT&gt; | Observable artifacts extracted from the event (IPs, domains, ports, protocols) for threat hunting. Struct: name, type, value. |
| **`policy`** | STRUCT | Network policy or firewall rule that was applied to this connection. Fields: is_applied, name, uid, version. |
| **`raw_data`** | VARIANT | The original raw event data in its native format. |
| **`severity`** | STRING | The event severity name (e.g., Informational, Low, Medium, High, Critical). |
| **`severity_id`** | INT | The event severity ID: 0=Unknown, 1=Informational, 2=Low, 3=Medium, 4=High, 5=Critical, 6=Fatal, 99=Other. |
| **`src_endpoint`** | STRUCT | The source endpoint (client/initiator). Includes IP, port, hostname, geolocation. [Endpoint reference](../../ocsf_ddl_fields/ocsf-endpoint.md). |
| `start_time` | TIMESTAMP | The connection start/open time. |
| **`status`** | STRING | The event status name (e.g., Success, Failure). |
| **`status_code`** | STRING | The vendor-specific status or connection state code (e.g., Zeek conn_state). |
| **`status_detail`** | STRING | Additional details about the connection status or state. |
| **`status_id`** | INT | The event status ID: 0=Unknown, 1=Success, 2=Failure, 99=Other. |
| **`time`** | TIMESTAMP | The event occurrence time (typically connection start or log time). |
| **`timezone_offset`** | INT | The timezone offset in minutes from UTC. |
| `tls` | STRUCT | TLS protocol information including cipher suite, certificate details, JA3/JA3S fingerprints, and Server Name Indication (SNI). Fields: alert, certificate (created_time, expiration_time, fingerprints, issuer, serial_number, subject, version), certificate_chain, cipher, client_ciphers, handshake_dur, ja3_hash, ja3s_hash, key_length, server_ciphers, sni, tls_extension_list, version. |
| **`traffic`** | STRUCT | Traffic statistics: bytes and packets transmitted in both directions. Fields: bytes, bytes_in, bytes_missed, bytes_out, chunks, chunks_in, chunks_out, packets, packets_in, packets_out. |
| **`type_name`** | STRING | Event type name. |
| **`type_uid`** | BIGINT | The event type unique identifier (class_uid * 100 + activity_id). |
| **`unmapped`** | VARIANT | Vendor-specific fields not in OCSF schema. |
| `url` | STRUCT | URL if applicable. Fields: url_string. |

**See also:** [OCSF ID reference](../../ocsf_ddl_fields/ocsf-ids.md) · [OCSF endpoint reference](../../ocsf_ddl_fields/ocsf-endpoint.md) · [OCSF metadata reference](../../ocsf_ddl_fields/ocsf-metadata.md) · [OCSF cloud reference](../../ocsf_ddl_fields/ocsf-cloud.md) · [OCSF enrichments/observables](../../ocsf_ddl_fields/ocsf-enrichments-observables.md) · [OCSF connection_info](../../ocsf_ddl_fields/ocsf-connection-info.md) · [OCSF traffic](../../ocsf_ddl_fields/ocsf-traffic.md)

## Delta table properties

- `delta.enableDeletionVectors` = true  
- `delta.minReaderVersion` = 3, `delta.minWriterVersion` = 7  
- Optimizer statistics on `time`
