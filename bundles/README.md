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

---

## Bundle Structure

Every bundle follows the same structure:

```
bundles/<source>/<source_type>/
  databricks.yml          ← bundle config: variables, targets, execution mode
  resources/
    sdp.yml               ← SDP pipeline resource (Lakeflow, serverless)
    sss.yml               ← SSS job resource (classic compute, 3-task Bronze→Silver→Gold)
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

# 1. Set your workspace and catalog in databricks.yml (see Variables section below)

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
| `zeek/conn` | `zeek_conn_sdp` | `zeek_conn_sss` | network_activity |
| `aws/vpc_flowlogs` | `aws_vpc_flowlogs_sdp` | `aws_vpc_flowlogs_sss` | network_activity |

---

## Variables

Each bundle's `databricks.yml` defines the same set of variables. All root-level defaults are **placeholders** — set real values in the `targets` section.

| Variable | Default | Used by | Notes |
|---|---|---|---|
| `bronze_catalog` | `""` | SDP only | Leave empty to use database name only |
| `silver_catalog` | `""` | SDP only | Leave empty to use database name only |
| `gold_catalog` | `""` | SDP only | Required for SDP — must be a valid UC catalog |
| `source_database` | varies | SDP + SSS | Bronze and Silver schema (e.g. `cisco`, `github`) |
| `gold_database` | `"ocsf"` | SDP + SSS | Gold (OCSF) schema |
| `sss_checkpoints_base` | placeholder | SSS only | Base Volume path for streaming checkpoints |
| `spark_version` | `"16.4.x-scala2.12"` | SSS only | DBR version for classic job clusters |
| `node_type_id` | `"i3.xlarge"` | SSS only | AWS default — Azure: `Standard_D4ds_v5`, GCP: `n2-highmem-4` |

### Catalog routing in SDP

SDP supports independent catalog per layer. Set in the `targets` section of `databricks.yml`:

```yaml
targets:
  dev:
    variables:
      bronze_catalog: "cyber_lakehouse"
      silver_catalog: "cyber_lakehouse"
      gold_catalog:   "cyber_lakehouse"
      source_database: "cisco"
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

## Tutorial: Adding a New Bundle

This walkthrough adds a new bundle for a fictional `palo_alto/firewall` pipeline.

### Step 1 — Create the preset

If you haven't already, create the preset YAML:

```
pipelines/palo_alto/firewall/preset.yaml
```

### Step 2 — Create the bundle directory

```bash
mkdir -p bundles/palo_alto/firewall/resources
```

### Step 3 — Copy an existing bundle as a template

```bash
cp bundles/cisco/ios/databricks.yml     bundles/palo_alto/firewall/databricks.yml
cp bundles/cisco/ios/resources/sdp.yml  bundles/palo_alto/firewall/resources/sdp.yml
cp bundles/cisco/ios/resources/sss.yml  bundles/palo_alto/firewall/resources/sss.yml
```

### Step 4 — Update `databricks.yml`

Open `bundles/palo_alto/firewall/databricks.yml` and change:

| Find | Replace with |
|---|---|
| `dsl_lite_cisco_ios` | `dsl_lite_palo_alto_firewall` |
| `../../../pipelines/cisco/ios/**` | `../../../pipelines/palo_alto/firewall/**` |
| `default: "cisco"` (source_database) | `default: "palo_alto"` |
| `cisco_ios_sdp` (quick start comment) | `palo_alto_firewall_sdp` |

### Step 5 — Update `resources/sdp.yml`

| Find | Replace with |
|---|---|
| `cisco_ios_sdp` | `palo_alto_firewall_sdp` |
| `Cisco IOS` | `Palo Alto Firewall` |
| `pipelines/cisco/ios/preset.yaml` | `pipelines/palo_alto/firewall/preset.yaml` |

### Step 6 — Update `resources/sss.yml`

| Find | Replace with |
|---|---|
| `cisco_ios_sss` | `palo_alto_firewall_sss` |
| `Cisco IOS` | `Palo Alto Firewall` |
| `pipelines/cisco/ios/preset.yaml` | `pipelines/palo_alto/firewall/preset.yaml` |
| `cisco_ios` (checkpoint subdirectory) | `palo_alto_firewall` |

### Step 7 — Set your variables and deploy

```bash
cd bundles/palo_alto/firewall

# Edit databricks.yml targets with your catalog/workspace details

databricks bundle validate -t dev
databricks bundle deploy -t dev
databricks bundle run palo_alto_firewall_sdp -t dev
```

---

## Teardown

```bash
cd bundles/cisco/ios
databricks bundle destroy -t dev

cd bundles/cisco/ios
databricks bundle destroy -t prod --auto-approve
```
