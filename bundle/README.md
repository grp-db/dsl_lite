# DSL Lite — Databricks Asset Bundles (DABs)

This directory and the root `databricks.yml` define the Databricks Asset Bundle for deploying DSL Lite pipelines to any Databricks workspace.

---

## Prerequisites

- **Databricks CLI** ≥ 0.220 — [install](https://docs.databricks.com/dev-tools/cli/install.html)
- **Authentication** — configure a CLI profile:
  ```bash
  databricks configure --profile DEFAULT
  # or for multiple workspaces:
  databricks configure --profile prod-workspace
  ```
- **Unity Catalog** — target workspace must have Unity Catalog enabled
- **DBR 16.0+ / Spark 4.1+** — required for SDP pipelines

---

## Recommended: SDP Pipeline (Lakeflow)

The **Spark Declarative Pipeline (SDP)** is the recommended way to deploy DSL Lite via DABs. It uses Lakeflow to manage the full Bronze → Silver → Gold pipeline as a single, serverless, continuously monitored resource — no cluster configuration required.

### Quick Start

**1. Set your variables** in `databricks.yml`. All root-level defaults are placeholders — update the `dev` target at minimum:

```yaml
targets:
  dev:
    variables:
      catalog: "my_catalog"
      bronze_database: "dsl_bronze_dev"
      silver_database: "dsl_silver_dev"
      gold_database:   "dsl_gold_dev"
```

**2. Select your preset** via the `preset_name` variable (must match a folder under `pipelines/`):

```bash
databricks bundle deploy -t dev --var="preset_name=cisco/ios"
```

Available presets:

| `preset_name` | Source | Gold Tables (OCSF) |
|---|---|---|
| `cisco/ios` | Cisco IOS logs | authentication, authorize_session, network_activity, process_activity |
| `cloudflare/gateway_dns` | Cloudflare Gateway DNS | dns_activity |
| `github/audit_logs` | GitHub Audit Logs | account_change, authentication, authorize_session, user_access, group_management |
| `zeek/conn` | Zeek Conn logs | network_activity |
| `aws/vpc_flowlogs` | AWS VPC Flow Logs | network_activity |

**3. Validate, deploy, and run:**

```bash
databricks bundle validate -t dev
databricks bundle deploy -t dev --var="preset_name=cisco/ios"
databricks bundle run dsl_lite_sdp -t dev
```

### SDP Pipeline resource

Defined in `resources/sdp_pipeline.yml`. Key configuration:

- Runs **serverless** by default — no `clusters` block needed
- Preset is wired via Spark conf key `dsl_lite.config_file`, pointing to the synced preset YAML
- Layer databases are set via Spark conf keys (`dsl_lite.bronze_database_name`, etc.)
- To skip Bronze or Silver (use existing tables): set `dsl_lite.skip_bronze: "true"` or `dsl_lite.skip_silver: "true"` in the pipeline `configuration` block

---

## SSS Jobs (Alternative)

Spark Structured Streaming jobs are available as an alternative when SDP is not suitable (e.g. DBR < 16.0, or you need per-layer scheduling control).

### Compute mode

SSS jobs come in two variants. Select one by editing the `include` block in `databricks.yml`:

```yaml
# Serverless (recommended if using SSS)
include:
  - resources/*.yml
  - resources/serverless/*.yml

# Classic compute (uses spark_version and node_type_id variables)
# include:
#   - resources/*.yml
#   - resources/classic/*.yml
```

> `spark_version` and `node_type_id` are only relevant for classic compute and can be left as-is when using serverless.

### SSS Multi-Task Job

One dedicated job per preset — Bronze, Silver, and Gold run as sequential tasks on a shared cluster. Good for scheduled batch processing.

```bash
databricks bundle deploy -t dev
databricks bundle run cisco_ios_pipeline -t dev
```

Available job keys: `cisco_ios_pipeline`, `cloudflare_gateway_dns_pipeline`, `github_audit_logs_pipeline`, `zeek_conn_pipeline`, `aws_vpc_flowlogs_pipeline`

**Checkpoint volumes** must exist before running SSS jobs:

```sql
CREATE CATALOG IF NOT EXISTS dev;
CREATE SCHEMA IF NOT EXISTS dev.dsl_bronze_dev;
CREATE VOLUME IF NOT EXISTS dev.dsl_bronze_dev.checkpoints;
```

Then set `sss_checkpoints_base` in the target variables.

**To run continuously:** change `continuous: "False"` to `continuous: "True"` in the job resource file and remove `depends_on` so all three tasks start simultaneously.

### SSS Single-Task Job (Generic)

Runs all three layers in one notebook. Uses the `preset_name` variable:

```bash
databricks bundle deploy -t dev --var="preset_name=cloudflare/gateway_dns"
databricks bundle run sss_medallion_pipeline -t dev
```

---

## Variables Reference

All root-level defaults in `databricks.yml` are **placeholders** — set real values in the `targets` section.

| Variable | Default (placeholder) | Used by |
|---|---|---|
| `catalog` | `main` | SDP, SSS |
| `bronze_database` | `dsl_bronze` | SDP, SSS |
| `silver_database` | `dsl_silver` | SDP, SSS |
| `gold_database` | `dsl_gold` | SDP, SSS |
| `preset_name` | `cisco/ios` | SDP, SSS single-task |
| `sss_checkpoints_base` | `/Volumes/main/dsl_bronze/checkpoints` | SSS only |
| `spark_version` | `16.4.x-scala2.12` | Classic compute only |
| `node_type_id` | `i3.xlarge` (AWS) | Classic compute only — Azure: `Standard_D4ds_v5`, GCP: `n2-highmem-4` |

---

## Targets

| Target | Mode | Notes |
|---|---|---|
| `dev` | development | Default; job/pipeline names prefixed with `[dev]` |
| `staging` | development | Pre-production validation |
| `prod` | production | Production deployment |

Update `workspace.profile` in each target to match your CLI profile names.

---

## How Preset Files Are Resolved

DABs syncs the `pipelines/` directory to the workspace at deploy time. Preset YAML files are accessible from notebooks and pipelines at:

```
${workspace.file_path}/pipelines/<vendor>/<type>/preset.yaml
```

No manual file uploads required.

---

## Adding a New Preset

1. Create your preset YAML under `pipelines/<vendor>/<type>/preset.yaml`
2. Deploy with `--var="preset_name=<vendor>/<type>"` to use it with SDP or the SSS single-task job
3. For a dedicated SSS multi-task job, copy `resources/serverless/cisco_ios_job.yml` (or the classic equivalent), replace all `cisco/ios` references with your preset path, and update the job name and resource key

---

## Scheduling SSS Jobs

Add a `schedule` block to any SSS job resource file:

```yaml
resources:
  jobs:
    cisco_ios_pipeline:
      schedule:
        quartz_cron_expression: "0 0 2 * * ?"   # 2am daily
        timezone_id: "America/Los_Angeles"
        pause_status: UNPAUSED
```

SDP pipelines are scheduled via the Lakeflow UI or by setting `continuous: true` in `resources/sdp_pipeline.yml`.

---

## Teardown

```bash
databricks bundle destroy -t dev
databricks bundle destroy -t prod --auto-approve
```
