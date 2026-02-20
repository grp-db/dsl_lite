# OCSF Traffic Struct Reference

The **traffic** top-level field holds byte and packet counts for a connection or request/response. It appears on Network Activity tables: network_activity, dns_activity, http_activity. Use this reference when mapping flow stats from Zeek, firewalls, or proxies.

## Struct shape

| Field | Type | Description |
|-------|------|-------------|
| `bytes` | BIGINT | Total bytes. |
| `bytes_in` | BIGINT | Bytes received (inbound / response). |
| `bytes_missed` | BIGINT | Bytes missed (e.g. dropped, not captured). |
| `bytes_out` | BIGINT | Bytes sent (outbound / request). |
| `chunks` | BIGINT | Chunk count. |
| `chunks_in` | BIGINT | Chunks received. |
| `chunks_out` | BIGINT | Chunks sent. |
| `packets` | BIGINT | Total packets. |
| `packets_in` | BIGINT | Packets received. |
| `packets_out` | BIGINT | Packets sent. |

## Spark DDL

```sql
STRUCT<
  bytes: BIGINT,
  bytes_in: BIGINT,
  bytes_missed: BIGINT,
  bytes_out: BIGINT,
  chunks: BIGINT,
  chunks_in: BIGINT,
  chunks_out: BIGINT,
  packets: BIGINT,
  packets_in: BIGINT,
  packets_out: BIGINT
>
```

## Where it’s used

- **network_activity** – Connection bytes/packets in both directions.
- **dns_activity** – DNS query/response size.
- **http_activity** – HTTP request/response size (bytes_out = request, bytes_in = response).
