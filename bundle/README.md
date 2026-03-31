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
- **Volumes** — if using SSS jobs, create a Volume for checkpoint storage before deploying:
  ```sql
  CREATE CATALOG IF NOT EXISTS dev;
  CREATE SCHEMA IF NOT EXISTS dev.dsl_bronze_dev;
  CREATE VOLUME IF NOT EXISTS dev.dsl_bronze_dev.checkpoints;
  ```

---

## Bundle Overview

The bundle deploys **three types of resources**, all driven by preset YAML configuration files in `pipelines/`:

| Resource Type | File(s) | Description |
|---|---|---|
| SSS Multi-Task Job | `resources/serverless/*_job.yml` or `resources/classic/*_job.yml` | One job per preset, 3 tasks (Bronze → Silver → Gold) |
| SSS Single-Task Job | `resources/serverless/sss_pipeline.yml` or `resources/classic/sss_pipeline.yml` | All layers in one notebook; preset set via `preset_name` variable |
| SDP Pipeline | `resources/sdp_pipeline.yml` | Lakeflow Spark Declarative Pipeline; preset set via `preset_name` variable |

### Available Preset Jobs (SSS Multi-Task)

| Job Key | Source | Gold Tables (OCSF) |
|---|---|---|
| `cisco_ios_pipeline` | Cisco IOS logs | authentication, authorize_session, network_activity, process_activity |
| `cloudflare_gateway_dns_pipeline` | Cloudflare Gateway DNS | dns_activity |
| `github_audit_logs_pipeline` | GitHub Audit Logs | account_change, authentication, authorize_session, user_access, group_management |
| `zeek_conn_pipeline` | Zeek Conn logs | network_activity |
| `aws_vpc_flowlogs_pipeline` | AWS VPC Flow Logs | network_activity |

---

## Compute Mode

SSS jobs (multi-task and single-task) come in two compute variants. The SDP pipeline is always serverless by default regardless of which mode is selected.

### Switching compute modes

Open `databricks.yml` and uncomment **one** of the two `include` blocks:

```yaml
# Option 1: Serverless (recommended — no cluster management required)
include:
  - resources/*.yml
  - resources/serverless/*.yml

# Option 2: Classic compute (requires spark_version and node_type_id variables)
# include:
#   - resources/*.yml
#   - resources/classic/*.yml
```

### Serverless (`resources/serverless/`)

- No cluster configuration needed — Databricks manages compute automatically
- `spark_version` and `node_type_id` variables are **ignored**
- Recommended for most deployments

### Classic compute (`resources/classic/`)

- Uses `job_clusters` with a dedicated cluster per job run
- Requires setting `spark_version` and `node_type_id` variables
- `node_type_id` is cloud-specific:
  - **AWS:** `i3.xlarge`, `m5.xlarge`, etc.
  - **Azure:** `Standard_D4ds_v5`, `Standard_D8ds_v5`, etc.
  - **GCP:** `n2-highmem-4`, `n2-standard-8`, etc.

---

## Quick Start

### 1. Choose your compute mode

Edit the `include` block in `databricks.yml` as described above.

### 2. Set your variables

All defaults in `databricks.yml` are **placeholders** — replace them with values that match your workspace. At minimum, update the `dev` target variables:

```yaml
targets:
  dev:
    variables:
      catalog: "my_catalog"              # your UC catalog name
      bronze_database: "dsl_bronze_dev"  # schema for Bronze tables
      silver_database: "dsl_silver_dev"  # schema for Silver tables
      gold_database:   "dsl_gold_dev"    # schema for Gold tables
      sss_checkpoints_base: "/Volumes/my_catalog/dsl_bronze_dev/checkpoints"  # SSS only
```

If using classic compute, also set:

```yaml
    variables:
      spark_version: "16.4.x-scala2.12"
      node_type_id: "i3.xlarge"   # adjust for your cloud (see Compute Mode section above)
```

### 3. Validate the bundle

```bash
databricks bundle validate -t dev
```

### 4. Deploy

```bash
# Deploy to dev (default target)
databricks bundle deploy

# Deploy to a specific target
databricks bundle deploy -t staging
databricks bundle deploy -t prod
```

### 5. Run a pipeline

```bash
databricks bundle run cisco_ios_pipeline -t dev
databricks bundle run cloudflare_gateway_dns_pipeline -t dev
databricks bundle run github_audit_logs_pipeline -t dev
databricks bundle run zeek_conn_pipeline -t dev
databricks bundle run aws_vpc_flowlogs_pipeline -t dev
```

---

## Execution Modes

### SSS Multi-Task Job (Recommended)

Each preset has a dedicated 3-task job that runs Bronze → Silver → Gold sequentially using `availableNow` trigger (batch mode). Jobs can be scheduled via the Databricks UI or by adding a `schedule` block to the resource YAML.

**To run continuously:** Change `continuous: "False"` to `continuous: "True"` in the job resource file, and remove the `depends_on` sections so all three tasks start simultaneously.

### SSS Single-Task Job (Generic)

Runs all three layers in one notebook. Simpler but less fault-isolated. The preset is selected via `preset_name`:

```bash
databricks bundle deploy -t dev --var="preset_name=cloudflare/gateway_dns"
databricks bundle run sss_medallion_pipeline -t dev
```

### SDP Pipeline (Lakeflow)

Uses Spark Declarative Pipelines (requires DBR 16.0+ / Spark 4.1+). Always runs serverless — the `resources/sdp_pipeline.yml` file contains no cluster config. The preset is set via `preset_name`:

```bash
databricks bundle deploy -t dev --var="preset_name=zeek/conn"
databricks bundle run dsl_lite_sdp -t dev
```

---

## Variables Reference

All variables are defined in `databricks.yml`. The root-level defaults are placeholders — the per-target values under `targets:` override them at deploy time and should be set to match your workspace.

| Variable | Default (placeholder) | Description |
|---|---|---|
| `catalog` | `main` | UC catalog for Gold tables and SDP pipeline target |
| `bronze_database` | `dsl_bronze` | Schema for Bronze tables |
| `silver_database` | `dsl_silver` | Schema for Silver tables |
| `gold_database` | `dsl_gold` | Schema for Gold (OCSF) tables |
| `sss_checkpoints_base` | `/Volumes/main/dsl_bronze/checkpoints` | SSS only — base path for streaming checkpoints. Not used by SDP (Lakeflow manages those internally). |
| `spark_version` | `16.4.x-scala2.12` | Classic compute only — Databricks Runtime version |
| `node_type_id` | `i3.xlarge` | Classic compute only — worker instance type (cloud-specific, see above) |
| `preset_name` | `cisco/ios` | Preset path for SDP and SSS single-task jobs |

---

## Targets

| Target | Mode | Profile | Notes |
|---|---|---|---|
| `dev` | development | DEFAULT | Default target; job names prefixed with `[dev]` |
| `staging` | development | DEFAULT | Pre-production validation |
| `prod` | production | DEFAULT | Production deployment |

Update `workspace.profile` in each target to match your CLI profile names.

---

## Adding a New Preset

1. Create your preset YAML under `pipelines/<vendor>/<type>/preset.yaml`
2. Copy `resources/serverless/cisco_ios_job.yml` (or the classic equivalent) to a new file
3. Replace all occurrences of `cisco/ios` with your preset path
4. Update the job `name`, resource key, and task descriptions
5. Run `databricks bundle validate && databricks bundle deploy`

---

## How Preset Files Are Resolved

When the bundle is deployed, DABs syncs the `pipelines/` directory to the workspace alongside the source notebooks. Preset YAML files are accessible from running notebooks at:

```
${workspace.file_path}/pipelines/<vendor>/<type>/preset.yaml
```

No manual file uploads required.

---

## Scheduling Jobs

Add a `schedule` block to any job resource file:

```yaml
resources:
  jobs:
    cisco_ios_pipeline:
      schedule:
        quartz_cron_expression: "0 0 2 * * ?"   # 2am daily
        timezone_id: "America/Los_Angeles"
        pause_status: UNPAUSED
```

---

## Skipping Layers

If Bronze or Silver tables already exist and you only want to refresh Gold:

- **SSS single-task:** set `skip_bronze: "True"` and/or `skip_silver: "True"` in the task `base_parameters`
- **SSS multi-task:** comment out the `bronze` and/or `silver` task blocks and remove the corresponding `depends_on` entries
- **SDP:** set `dsl_lite.skip_bronze: "true"` and/or `dsl_lite.skip_silver: "true"` in the pipeline `configuration` block

---

## Teardown

```bash
databricks bundle destroy -t dev
databricks bundle destroy -t prod --auto-approve
```
