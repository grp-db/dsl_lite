# DSL Lite — Declarative Automation Bundles

Each subdirectory in `bundles/` is a self-contained Declarative Automation Bundle for a single DSL Lite pipeline. Bundles are isolated by `source/source_type`, matching the structure of the `pipelines/` directory.

```
bundles/
  cisco/ios/
  cloudflare/gateway_dns/
  github/audit_logs/
  zeek/conn/
  aws/vpc_flowlogs/
```

Each bundle deploys and operates independently — changes to one pipeline never affect another.

---

## Prerequisites

- **Databricks CLI** ≥ 0.220 — [install](https://docs.databricks.com/dev-tools/cli/install.html)
- **Authentication** — configure a CLI profile:
  ```bash
  databricks configure --profile DEFAULT
  ```
- **Unity Catalog** — required for all modes
- **DBR 16.0+ / Spark 4.1+** — required for SDP mode
- **dsl_lite available in Databricks Workspace** — the bundle references source files by workspace path (see `repo_path` below); the repo must be accessible in the workspace via Repos or Workspace Files

---

## Bundle Structure

Every bundle follows the same structure:

```
bundles/<source>/<source_type>/
  databricks.yml          ← bundle config: variables, targets, execution mode
  resources/
    sdp.yml               ← SDP pipeline resource (Lakeflow, serverless)
    sss.yml               ← SSS job resource (classic compute, Bronze→Silver→Gold)
```

### Execution mode

Each `databricks.yml` has an `include` block that selects the execution mode. Edit it to switch between SDP and SSS:

```yaml
# Option 1: SDP — Lakeflow Spark Declarative Pipeline (recommended, serverless)
include:
  - resources/sdp.yml

# Option 2: SSS — Spark Structured Streaming, classic compute
# include:
#   - resources/sss.yml
```

---

## Quick Start (SDP — Recommended)

```bash
# Navigate to the bundle for your pipeline
cd bundles/cisco/ios

# 1. Set repo_path, workspace host, and catalog variables in databricks.yml
#    repo_path example: /Workspace/Repos/user@domain.com/dsl_lite

# 2. Validate
databricks bundle validate -t dev

# 3. Deploy
databricks bundle deploy -t dev

# 4. Run
databricks bundle run cisco_ios_sdp -t dev
```

---

## Available Bundles

| Path | Resource key (SDP) | Resource key (SSS) | Gold tables (OCSF) |
|---|---|---|---|
| `cisco/ios` | `cisco_ios_sdp` | `cisco_ios_sss` | authentication, authorize_session, network_activity, process_activity |
| `cloudflare/gateway_dns` | `cloudflare_gateway_dns_sdp` | `cloudflare_gateway_dns_sss` | dns_activity |
| `github/audit_logs` | `github_audit_logs_sdp` | `github_audit_logs_sss` | account_change, authentication, authorize_session, user_access, group_management |
| `okta/system_log` | `okta_system_log_sdp` | `okta_system_log_sss` | authentication, account_change, group_management |
| `zeek/conn` | `zeek_conn_sdp` | `zeek_conn_sss` | network_activity |
| `aws/vpc_flowlogs` | `aws_vpc_flowlogs_sdp` | `aws_vpc_flowlogs_sss` | network_activity |

---

## Variables

Each bundle's `databricks.yml` defines the same set of variables. All root-level defaults are **placeholders** — set real values in the `targets` section.

| Variable | Default | Used by | Notes |
|---|---|---|---|
| `repo_path` | auto (`/Workspace/Users/<current-user>/dsl_lite`) | SDP + SSS | Resolves to current user's workspace path by default; override for CI/CD or Repos checkouts |
| `bronze_catalog` | `""` | SDP only | Leave empty to use database name only |
| `silver_catalog` | `""` | SDP only | Leave empty to use database name only |
| `gold_catalog` | `""` | SDP only | Required for SDP — must be a valid UC catalog |
| `bronze_database` | varies | SDP + SSS | Bronze schema (e.g. `cisco`, `github`) |
| `silver_database` | varies | SDP + SSS | Silver schema (e.g. `cisco`, `github`) |
| `gold_database` | `"ocsf"` | SDP + SSS | Gold (OCSF) schema |
| `sss_checkpoints_base` | placeholder | SSS only | Base Volume path for streaming checkpoints |
| `spark_version` | `"16.4.x-scala2.12"` | SSS only | DBR version for classic job clusters |
| `node_type_id` | `"i3.xlarge"` | SSS only | AWS default — Azure: `Standard_D4ds_v5`, GCP: `n2-highmem-4` |

### `repo_path` — workspace path to dsl_lite

The bundle references all source files (`sdp_medallion.py`, `sss_bronze.py`, preset YAMLs, etc.) by their absolute workspace path via `${var.repo_path}`. This avoids DABs sync boundary restrictions — the bundle deploys the pipeline/job *configuration* and points it at code that already lives in your workspace.

Set `repo_path` to wherever dsl_lite is accessible in your workspace:

```yaml
# Databricks Repos checkout:
repo_path: /Workspace/Repos/user@domain.com/dsl_lite

# Workspace Files upload:
repo_path: /Workspace/Users/user@domain.com/dsl_lite
```

Set this per-target in `databricks.yml`:

```yaml
targets:
  dev:
    variables:
      repo_path: /Workspace/Repos/user@domain.com/dsl_lite
  prod:
    variables:
      repo_path: /Workspace/Repos/svc-account@domain.com/dsl_lite
```

### Catalog routing in SDP

SDP supports independent catalog per layer. Set in the `targets` section of `databricks.yml`:

```yaml
targets:
  dev:
    variables:
      bronze_catalog: "cyber_lakehouse"
      silver_catalog: "cyber_lakehouse"
      gold_catalog:   "cyber_lakehouse"
      bronze_database: "cisco"
      silver_database: "cisco"
      gold_database:   "ocsf"
```

Tables will be created at:
- Bronze: `cyber_lakehouse.cisco.<bronze_table>`
- Silver: `cyber_lakehouse.cisco.<silver_table>`
- Gold:   `cyber_lakehouse.ocsf.<ocsf_table>`

### Catalog routing in SSS

SSS notebooks accept a single database string — there is no separate catalog parameter. To include a catalog, use `catalog.database` format in the database variable:

```yaml
variables:
  source_database: "cyber_lakehouse.cisco"   # catalog.database
  gold_database:   "cyber_lakehouse.ocsf"
```

---

## Targets

Each bundle has three pre-configured targets:

| Target | Mode | Notes |
|---|---|---|
| `dev` | development | Default; resource names prefixed with `[dev]` |
| `staging` | development | Pre-production validation |
| `prod` | production | No name prefix |

Update `workspace.host` and `workspace.profile` in each target to match your workspace and CLI profile.

---

## SDP — Additional Options

### Skipping layers

To reuse existing Bronze or Silver tables, edit the `configuration` block in `resources/sdp.yml`:

```yaml
configuration:
  dsl_lite.skip_bronze: "true"    # skip ingestion, use existing bronze table
  dsl_lite.skip_silver: "false"
```

### Continuous mode

SDP pipelines run in triggered (batch) mode by default. To stream continuously, set `continuous: true` in `resources/sdp.yml`. This can also be toggled in the Lakeflow UI after deployment.

### Scheduling

SDP pipelines are scheduled via the Lakeflow UI or by adding a `trigger` block to `resources/sdp.yml`.

---

## SSS — Additional Options

### Continuous mode

By default SSS jobs run in batch mode (`availableNow`). To run continuously, change `continuous: "False"` to `continuous: "True"` in `resources/sss.yml` and remove the `depends_on` blocks so all three tasks start simultaneously.

### Scheduling

Add a `schedule` block to `resources/sss.yml`:

```yaml
resources:
  jobs:
    cisco_ios_sss:
      schedule:
        quartz_cron_expression: "0 0 2 * * ?"   # 2am daily
        timezone_id: "America/Los_Angeles"
        pause_status: UNPAUSED
```

### Checkpoint volume

A Unity Catalog Volume must exist before running SSS jobs:

```sql
CREATE VOLUME IF NOT EXISTS <catalog>.<schema>.checkpoints;
```

Then set `sss_checkpoints_base` in `databricks.yml` to point to it.

---

## Adding a New Bundle

See **[tutorials/adding-a-bundle.md](../tutorials/adding-a-bundle.md)** for a step-by-step walkthrough.

Templates for all three bundle files live in `bundles/templates/` — copy and fill in placeholders rather than copying from an existing bundle.

---

## Teardown

```bash
cd bundles/cisco/ios
databricks bundle destroy -t dev

databricks bundle destroy -t prod --auto-approve
```
