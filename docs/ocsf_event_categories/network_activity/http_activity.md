# OCSF: HTTP Activity

**Class UID:** 4002  
**Category:** Network Activity (Category 4)  
**Reference:** [schema.ocsf.io/1.7.0/classes/http_activity](https://schema.ocsf.io/1.7.0/classes/http_activity)

## Overview

Tracks HTTP/HTTPS requests and responses for web traffic monitoring and API activity.

**Commonly used for:** Web proxy logs, API gateway logs, WAF logs, load balancer logs.

## Table: `http_activity`

**Bold** columns are common across OCSF tables in this category (Network Activity) and should be included in YAML mappings.

| Column | Type | Description |
|--------|------|-------------|
| **`dsl_id`** | STRING NOT NULL | Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers. |
| **`action`** | STRING | The action taken on the HTTP request (e.g., Allowed, Blocked, Redirected). |
| **`action_id`** | INT | The action ID: 0=Unknown, 1=Allowed, 2=Denied, 99=Other. |
| **`activity`** | STRING | The HTTP activity name (e.g., Request, Response, Upload, Download). Normalized value based on activity_id. |
| **`activity_id`** | INT | The HTTP activity ID: 0=Unknown, 1=Request, 2=Response, 3=Upload, 4=Download, 5=Send, 6=Receive, 99=Other. |
| **`activity_name`** | STRING | The HTTP activity name. |
| `app_name` | STRING | The application name that generated the HTTP traffic (e.g., browser, mobile app, API client). |
| **`category_name`** | STRING | The OCSF category name: Network Activity. |
| **`category_uid`** | INT | The OCSF category unique identifier: 4 for Network Activity. |
| **`class_name`** | STRING | The OCSF class name: HTTP Activity. |
| **`class_uid`** | INT | The OCSF class unique identifier: 4002 for HTTP Activity. |
| **`connection_info`** | STRUCT | Connection details: protocol (HTTP/HTTPS), direction, connection UID. Fields: direction, direction_id, flag_history, protocol_name, protocol_num, protocol_ver, protocol_ver_id, uid. |
| **`disposition`** | STRING | The disposition name (e.g., Allowed, Blocked, Quarantined). For web security, indicates if request was blocked/filtered. |
| **`disposition_id`** | INT | The disposition ID: 0=Unknown, 1=Allowed, 2=Blocked, 3=Quarantined, 99=Other. |
| **`dst_endpoint`** | STRUCT | The destination web server. Includes IP, port (80/443), hostname, geolocation. [Endpoint reference](../../ocsf_ddl_fields/ocsf-endpoint.md). |
| **`enrichments`** | ARRAY&lt;STRUCT&gt; | Additional enrichment data from threat intel (e.g., malicious URL indicators), GeoIP, or reputation services. Struct: data, desc, name, value. |
| `file` | STRUCT | The file being accessed via HTTP (for file downloads/uploads). Fields: name, path. |
| `firewall_rule` | STRUCT | Web application firewall (WAF) rule that matched this request. Fields: name, uid, category, desc, type, version, condition, duration, match_details, match_location, rate_limit, sensitivity. |
| `http_cookies` | ARRAY&lt;STRUCT&gt; | HTTP cookies sent/received. Includes security flags (httpOnly, secure, samesite). Struct: domain, expiration_time, http_only, is_http_only, is_secure, name, path, samesite, secure, value. |
| `http_request` | STRUCT | HTTP request details: method (GET/POST/PUT/DELETE), URL, headers, user-agent, referrer, query args. Fields: args, body_length, http_headers (name, value), http_method, length, referrer, url, user_agent, version. |
| `http_response` | STRUCT | HTTP response details: status code (200/404/500), content-type, response size, latency in ms. Fields: body_length, code, content_type, http_headers, latency, length, message, status. |
| **`message`** | STRING | Human-readable description of the HTTP event. |
| **`metadata`** | STRUCT | Event metadata. Fields: correlation_uid, event_code, log_level, log_name, log_provider, log_format, log_version, logged_time, modified_time, original_time, processed_time, product (name, vendor_name, version), tags, tenant_uid, uid, version. See [metadata reference](../../ocsf_ddl_fields/ocsf-metadata.md). |
| **`observables`** | ARRAY&lt;STRUCT&gt; | Observable artifacts: URLs, domains, IPs, user-agents—critical for threat hunting and IOC matching. Struct: name, type, value. |
| **`policy`** | STRUCT | Web security policy or WAF rule that was applied. Fields: is_applied, name, uid, version. |
| **`raw_data`** | VARIANT | The original raw HTTP log in its native format. |
| **`severity`** | STRING | The event severity name (e.g., Informational, Low, Medium, High, Critical). |
| **`severity_id`** | INT | The event severity ID: 0=Unknown, 1=Informational, 2=Low, 3=Medium, 4=High, 5=Critical, 6=Fatal, 99=Other. |
| **`src_endpoint`** | STRUCT | The HTTP client (source of request). Includes client IP, hostname, port, geolocation. |
| **`status`** | STRING | The event status name (e.g., Success, Failure). |
| **`status_code`** | STRING | The vendor-specific status code. |
| **`status_detail`** | STRING | Additional details about the HTTP status. |
| **`status_id`** | INT | The event status ID: 0=Unknown, 1=Success, 2=Failure, 99=Other. |
| **`time`** | TIMESTAMP | The HTTP request time (required field). |
| **`timezone_offset`** | INT | The timezone offset in minutes from UTC. |
| **`traffic`** | STRUCT | HTTP traffic statistics: request size (bytes_out), response size (bytes_in), total bytes. Fields: bytes, bytes_in, bytes_missed, bytes_out, chunks, chunks_in, chunks_out, packets, packets_in, packets_out. |
| **`type_name`** | STRING | The event type name, formatted as "HTTP Activity: &lt;activity_name&gt;". |
| **`type_uid`** | BIGINT | The event type unique identifier (class_uid * 100 + activity_id). |
| **`unmapped`** | VARIANT | Vendor-specific HTTP fields that do not map to OCSF schema attributes. |

**See also:** [OCSF ID reference](../../ocsf_ddl_fields/ocsf-ids.md) · [OCSF endpoint reference](../../ocsf_ddl_fields/ocsf-endpoint.md) · [OCSF metadata reference](../../ocsf_ddl_fields/ocsf-metadata.md) · [OCSF enrichments/observables](../../ocsf_ddl_fields/ocsf-enrichments-observables.md) · [OCSF connection_info](../../ocsf_ddl_fields/ocsf-connection-info.md) · [OCSF traffic](../../ocsf_ddl_fields/ocsf-traffic.md)

## Delta table properties

- `delta.enableDeletionVectors` = true  
- `delta.minReaderVersion` = 3, `delta.minWriterVersion` = 7  
- Optimizer statistics on `time`
