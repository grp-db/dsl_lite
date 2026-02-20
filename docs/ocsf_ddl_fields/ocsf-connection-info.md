# OCSF Connection Info Struct Reference

The **connection_info** top-level field holds protocol and direction details for a connection. It appears on Network Activity tables: network_activity, dns_activity, http_activity. Use this reference when mapping Zeek, firewall, or proxy connection metadata.

## Struct shape

| Field | Type | Description |
|-------|------|-------------|
| `direction` | STRING | Direction name (e.g. Inbound, Outbound). |
| `direction_id` | INT | Direction ID. |
| `flag_history` | STRING | TCP flag history or similar (e.g. for connection state). |
| `protocol_name` | STRING | Protocol name (e.g. TCP, UDP, HTTP, HTTPS). |
| `protocol_num` | INT | Protocol number (e.g. IANA protocol number). |
| `protocol_ver` | STRING | Protocol version. |
| `protocol_ver_id` | INT | Protocol version ID. |
| `uid` | STRING | Connection unique identifier (e.g. Zeek conn_uid). |

## Spark DDL

```sql
STRUCT<
  direction: STRING,
  direction_id: INT,
  flag_history: STRING,
  protocol_name: STRING,
  protocol_num: INT,
  protocol_ver: STRING,
  protocol_ver_id: INT,
  uid: STRING
>
```

## Where it’s used

- **network_activity** – TCP/UDP/ICMP connection direction and protocol.
- **dns_activity** – DNS over UDP/TCP.
- **http_activity** – HTTP/HTTPS.
