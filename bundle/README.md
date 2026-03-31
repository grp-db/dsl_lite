# DSL Lite — Databricks Asset Bundles (DABs)

This directory and the root `databricks.yml` define the Databricks Asset Bundle for deploying DSL Lite pipelines to any Databricks workspace.

---

## Prerequisites

- **Databricks CLI** ≥ 0.220 — [install](https://docs.databricks.com/dev-tools/cli/install.html)
- **Authentication** — configure a CLI profile:
  ```bash
  databricks configure --profile DEFAULT
  ```
- **Unity Catalog** — required for all modes
- **DBR 16.0+ / Spark 4.1+** — required for SDP mode

---

## Execution Modes

Two modes are available. Select one by editing the `include` block in `databricks.yml`:

```yaml
# SDP — Lakeflow Spark Declarative Pipelines (recommended, serverless)
include:
  - resources/sdp/*.yml

# SSS — Spark Structured Streaming, classic compute
# include:
#   - resources/sss/*.yml
```

---

## SDP Mode (Recommended)

Uses Lakeflow to run Bronze → Silver → Gold as a single serverless pipeline per preset. No cluster configuration required.

**`gold_catalog` is required for SDP** — the pipeline needs a valid Unity Catalog catalog name to register tables. Leave `bronze_catalog` and `silver_catalog` empty to omit the catalog prefix for those layers.

### Quick start

**1. Set variables** in `databricks.yml` — update the `dev` target at minimum:

```yaml
targets:
  dev:
    variables:
      gold_catalog:   "cyber_lakehouse"   # required for SDP
      bronze_catalog: ""                  # optional — leave empty to use database only
      silver_catalog: ""                  # optional
```

**2. Validate and deploy:**

```bash
databricks bundle validate -t dev
databricks bundle deploy -t dev
```

**3. Run a pipeline:**

```bash
databricks bundle run cisco_ios_sdp -t dev
databricks bundle run cloudflare_gateway_dns_sdp -t dev
databricks bundle run github_audit_logs_sdp -t dev
databricks bundle run zeek_conn_sdp -t dev
databricks bundle run aws_vpc_flowlogs_sdp -t dev
```

### Available SDP pipelines

| Resource key | Preset | Gold tables (OCSF) |
|---|---|---|
| `cisco_ios_sdp` | `cisco/ios` | authentication, authorize_session, network_activity, process_activity |
| `cloudflare_gateway_dns_sdp` | `cloudflare/gateway_dns` | dns_activity |
| `github_audit_logs_sdp` | `github/audit_logs` | account_change, authentication, authorize_session, user_access, group_management |
| `zeek_conn_sdp` | `zeek/conn` | network_activity |
| `aws_vpc_flowlogs_sdp` | `aws/vpc_flowlogs` | network_activity |

### Catalog routing in SDP

SDP supports independent catalog configuration per layer via Spark conf keys in `resources/sdp/<preset>.yml`:

| Layer | Spark conf key | DABs variable |
|---|---|---|
| Bronze | `dsl_lite.bronze_catalog_name` | `bronze_catalog` |
| Bronze | `dsl_lite.bronze_database_name` | `cisco_database` (per-pipeline) |
| Silver | `dsl_lite.silver_catalog_name` | `silver_catalog` |
| Silver | `dsl_lite.silver_database_name` | `cisco_database` (per-pipeline) |
| Gold | `dsl_lite.gold_catalog_name` | `gold_catalog` |
| Gold | `dsl_lite.gold_database_name` | `gold_database` |

### Skipping layers

To skip Bronze or Silver (reuse existing tables), edit `dsl_lite.skip_bronze` or `dsl_lite.skip_silver` in the pipeline resource file:

```yaml
configuration:
  dsl_lite.skip_bronze: "true"
  dsl_lite.skip_silver: "false"
```

---

## SSS Mode (Alternative)

Uses Spark Structured Streaming with classic compute. Use when DBR < 16.0 or per-layer scheduling is required.

### Setup

**1. Switch the include block** in `databricks.yml`:

```yaml
include:
  - resources/sss/*.yml
```

**2. Set variables** — update `spark_version` and `node_type_id` for your cloud/workspace, and set `sss_checkpoints_base` to a Volume path that exists:

```yaml
targets:
  dev:
    variables:
      sss_checkpoints_base: "/Volumes/my_catalog/my_schema/checkpoints"
      spark_version: "16.4.x-scala2.12"
      node_type_id:  "i3.xlarge"   # AWS — see node types below
```

**Node types by cloud:**
- AWS: `i3.xlarge`
- Azure: `Standard_D4ds_v5`
- GCP: `n2-highmem-4`

**3. Create the checkpoint volume** before running:

```sql
CREATE VOLUME IF NOT EXISTS my_catalog.my_schema.checkpoints;
```

**4. Deploy and run:**

```bash
databricks bundle deploy -t dev
databricks bundle run cisco_ios_sss -t dev
```

### Available SSS jobs

| Resource key | Preset |
|---|---|
| `cisco_ios_sss` | `cisco/ios` |
| `cloudflare_gateway_dns_sss` | `cloudflare/gateway_dns` |
| `github_audit_logs_sss` | `github/audit_logs` |
| `zeek_conn_sss` | `zeek/conn` |
| `aws_vpc_flowlogs_sss` | `aws/vpc_flowlogs` |

### Catalog routing in SSS

SSS notebooks accept a single database string per layer — there is no separate catalog parameter. To include a catalog, use `catalog.database` format in the database variable:

```yaml
# databricks.yml — with catalog
variables:
  cisco_database: "cyber_lakehouse.cisco"
  gold_database:  "cyber_lakehouse.ocsf"

# databricks.yml — without catalog (database only)
variables:
  cisco_database: "cisco"
  gold_database:  "ocsf"
```

The `bronze_catalog`, `silver_catalog`, and `gold_catalog` variables are **SDP-only** and are not passed to SSS notebooks.

### Continuous streaming

By default all SSS jobs run in batch mode (`availableNow`). To run continuously, change `continuous: "False"` to `continuous: "True"` in the task parameters and remove the `depends_on` blocks so all three tasks start simultaneously.

---

## Variables Reference

All root-level defaults are **placeholders** — set real values in the `targets` section.

### Catalog variables (SDP only)

| Variable | Default | Notes |
|---|---|---|
| `bronze_catalog` | `""` | Optional. Leave empty to use database name only. |
| `silver_catalog` | `""` | Optional. Leave empty to use database name only. |
| `gold_catalog` | `""` | **Required for SDP.** Must be a valid UC catalog name. |

### Database variables (SDP + SSS)

| Variable | Default | Pipeline |
|---|---|---|
| `cisco_database` | `"cisco"` | Cisco IOS bronze + silver |
| `cloudflare_database` | `"cloudflare"` | Cloudflare Gateway DNS bronze + silver |
| `github_database` | `"github"` | GitHub Audit Logs bronze + silver |
| `zeek_database` | `"zeek"` | Zeek Conn bronze + silver |
| `aws_database` | `"aws"` | AWS VPC Flow Logs bronze + silver |
| `gold_database` | `"ocsf"` | Gold (OCSF) — shared across all pipelines |

### SSS-only variables

| Variable | Default | Notes |
|---|---|---|
| `sss_checkpoints_base` | `"/Volumes/main/ocsf/checkpoints"` | Base path; each pipeline appends its own subdirectory |
| `spark_version` | `"16.4.x-scala2.12"` | DBR version for classic job clusters |
| `node_type_id` | `"i3.xlarge"` | Worker instance type (AWS default) |

---

## Targets

| Target | Mode | Notes |
|---|---|---|
| `dev` | development | Default; resource names prefixed with `[dev]` |
| `staging` | development | Pre-production validation |
| `prod` | production | Production deployment |

Update `workspace.profile` in each target to match your CLI profile name.

---

## How Preset Files Are Resolved

DABs syncs the `pipelines/` directory to the workspace at deploy time. Preset YAML files are accessible from running notebooks and pipelines at:

```
${workspace.file_path}/pipelines/<vendor>/<type>/preset.yaml
```

No manual file uploads required.

---

## Adding a New Preset

1. Create your preset YAML at `pipelines/<vendor>/<type>/preset.yaml`
2. Copy `resources/sdp/cisco_ios.yml` to `resources/sdp/<your_preset>.yml`
3. Replace `cisco/ios` with your preset path, update the resource key, name, and database variable references
4. Add a matching `<your_source>_database` variable to `databricks.yml`
5. Repeat steps 2–4 in `resources/sss/` if SSS support is also needed

---

## Scheduling SDP Pipelines

SDP pipelines run in triggered (batch) mode by default. To run continuously, set `continuous: true` in the pipeline resource file. Scheduled triggers can also be configured via the Lakeflow UI after deployment.

## Scheduling SSS Jobs

Add a `schedule` block to any SSS job resource file:

```yaml
resources:
  jobs:
    cisco_ios_sss:
      schedule:
        quartz_cron_expression: "0 0 2 * * ?"   # 2am daily
        timezone_id: "America/Los_Angeles"
        pause_status: UNPAUSED
```

---

## Teardown

```bash
databricks bundle destroy -t dev
databricks bundle destroy -t prod --auto-approve
```
