# OCSF Enrichments & Observables Reference

Two common array-of-struct fields appear across almost all OCSF tables: **enrichments** (threat intel, GeoIP, etc.) and **observables** (extracted indicators for hunting and correlation). Use this reference when mapping enrichment or IOC data in YAML or pipelines.

---

## enrichments

**Type:** `ARRAY<STRUCT<...>>`

Holds additional context from enrichment engines: threat intel, GeoIP, reputation, or custom key-value data.

### Element struct

| Field | Type | Description |
|-------|------|-------------|
| `data` | VARIANT | Arbitrary enrichment payload (nested object or array). |
| `desc` | STRING | Human-readable description of the enrichment. |
| `name` | STRING | Enrichment name or source (e.g. GeoIP, threat_feed). |
| `value` | STRING | Single value or summary. |

### Spark DDL

```sql
ARRAY<STRUCT<
  data: VARIANT,
  desc: STRING,
  name: STRING,
  value: STRING
>>
```

### Where it’s used

Present on virtually every OCSF table (account_change, authentication, authorize_session, network_activity, dns_activity, http_activity, process_activity, file_activity, findings, etc.) when enrichment is applied.

---

## observables

**Type:** `ARRAY<STRUCT<...>>`

Holds extracted indicators (IPs, domains, hashes, usernames, etc.) for threat hunting, correlation, and IOC matching.

### Element struct

| Field | Type | Description |
|-------|------|-------------|
| `name` | STRING | Observable name or type (e.g. ip, domain, file_hash, user). |
| `type` | STRING | Type or category (e.g. ipv4, domain_name, sha256). |
| `value` | STRING | The observable value (e.g. 10.0.0.1, evil.com, hash). |

### Spark DDL

```sql
ARRAY<STRUCT<
  name: STRING,
  type: STRING,
  value: STRING
>>
```

### Where it’s used

Present on virtually every OCSF table. Critical for SIEM, hunting, and matching against threat intel; same shape across all classes.
