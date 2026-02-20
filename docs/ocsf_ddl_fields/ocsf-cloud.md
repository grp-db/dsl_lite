# OCSF Cloud Struct Reference

The **cloud** top-level field holds cloud environment context (account, provider, region, zone). It appears on IAM, Network Activity, Findings, and other tables when events originate from or relate to a cloud provider.

## Struct shape

| Field | Type | Description |
|-------|------|-------------|
| **`account`** | STRUCT | Cloud account (see below). |
| `cloud_partition` | STRING | Partition or partition key (e.g. AWS partition: aws, aws-cn, aws-us-gov). |
| `project_uid` | STRING | Project or subscription identifier (e.g. GCP project ID, Azure subscription ID). |
| `provider` | STRING | Cloud provider (e.g. aws, azure, gcp, oci). |
| `region` | STRING | Region (e.g. us-east-1, westus2). |
| `zone` | STRING | Availability zone or similar (e.g. us-east-1a). |

## Nested: `account`

| Field | Type | Description |
|-------|------|-------------|
| `name` | STRING | Account or subscription display name. |
| `uid` | STRING | Account or subscription unique identifier. |

## Spark DDL

```sql
STRUCT<
  account: STRUCT<
    name: STRING,
    uid: STRING
  >,
  cloud_partition: STRING,
  project_uid: STRING,
  provider: STRING,
  region: STRING,
  zone: STRING
>
```

## Where it’s used

Used as top-level **`cloud`** on: account_change, api_activity, authentication, authorize_session, data_security_finding, network_activity, and other OCSF tables when cloud context is available.
