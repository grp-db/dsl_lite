# OCSF Endpoint Struct Reference

The **endpoint** structure is used for `src_endpoint` and `dst_endpoint` across OCSF tables (Network Activity, Identity & Access Management, and others). Use this reference when mapping source/destination IP, hostname, port, and geolocation in YAML or pipelines.

## Struct shape

All endpoint fields use the same schema. Context (e.g. “client”, “server”, “DNS resolver”) is determined by the column name (`src_endpoint` vs `dst_endpoint`).

| Field | Type | Description |
|-------|------|-------------|
| `domain` | STRING | Domain name. |
| `hostname` | STRING | Hostname. |
| `instance_uid` | STRING | Instance unique identifier. |
| `interface_name` | STRING | Network interface name. |
| `interface_uid` | STRING | Interface unique identifier. |
| `ip` | STRING | IP address (IPv4 or IPv6). |
| `name` | STRING | Endpoint name. |
| `port` | INT | Port number. |
| `svc_name` | STRING | Service name (e.g. `http`, `dns`). |
| `type` | STRING | Endpoint type name. |
| `type_id` | INT | Endpoint type ID. |
| `uid` | STRING | Endpoint unique identifier. |
| **`location`** | STRUCT | Geolocation (see below). |
| `mac` | STRING | MAC address. |
| `vpc_uid` | STRING | VPC/network segment identifier. |
| `zone` | STRING | Zone (e.g. availability zone). |

## Nested: `location`

| Field | Type | Description |
|-------|------|-------------|
| `city` | STRING | City. |
| `continent` | STRING | Continent. |
| `country` | STRING | Country code or name. |
| `lat` | FLOAT | Latitude. |
| `long` | FLOAT | Longitude. |
| `postal_code` | STRING | Postal code. |

## Spark DDL (single line)

Use this when defining or validating endpoint columns:

```sql
STRUCT<
  domain: STRING,
  hostname: STRING,
  instance_uid: STRING,
  interface_name: STRING,
  interface_uid: STRING,
  ip: STRING,
  name: STRING,
  port: INT,
  svc_name: STRING,
  type: STRING,
  type_id: INT,
  uid: STRING,
  location: STRUCT<
    city: STRING,
    continent: STRING,
    country: STRING,
    lat: FLOAT,
    long: FLOAT,
    postal_code: STRING
  >,
  mac: STRING,
  vpc_uid: STRING,
  zone: STRING
>
```

## Where it’s used

- **Network Activity:** `src_endpoint`, `dst_endpoint` (network_activity, dns_activity, http_activity)
- **Identity & Access Management:** `src_endpoint`, `dst_endpoint` (authentication, authorize_session)
- Other OCSF tables that include source/destination endpoints use this same shape.
