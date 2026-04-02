# Adding a Bundle for a New Pipeline

This tutorial walks through adding a Declarative Automation Bundle for a new DSL Lite pipeline.
It assumes you have already built the preset for your pipeline (see [building-a-preset-end-to-end.md](building-a-preset-end-to-end.md)).

Throughout this tutorial, replace `<source>` and `<source_type>` with your actual values
(e.g. `source=palo_alto`, `source_type=firewall`).

---

## Step 1: Create the bundle directory

```bash
mkdir -p bundles/<source>/<source_type>/resources
```

---

## Step 2: Copy the templates

Templates live in `bundles/templates/`. Copy all three into your new bundle:

```bash
cp bundles/templates/databricks.yml bundles/<source>/<source_type>/databricks.yml
cp bundles/templates/sdp.yml        bundles/<source>/<source_type>/resources/sdp.yml
cp bundles/templates/sss.yml        bundles/<source>/<source_type>/resources/sss.yml
```

---

## Step 3: Replace placeholders

Each template uses `<source>`, `<source_type>`, `<SOURCE>`, and `<SOURCE_TYPE>` as placeholders.
Replace them in all three files:

| Placeholder | Example value |
|---|---|
| `<source>` | `palo_alto` |
| `<source_type>` | `firewall` |
| `<SOURCE>` | `Palo Alto` |
| `<SOURCE_TYPE>` | `Firewall` |

**`databricks.yml`** — update these fields:

| Find | Replace with |
|---|---|
| `dsl_lite_<source>_<source_type>` | `dsl_lite_palo_alto_firewall` |
| `<source>/<source_type>` (quick start path) | `palo_alto/firewall` |
| `<source>_<source_type>_sdp` (quick start run key) | `palo_alto_firewall_sdp` |
| `default: "<source>"` (bronze/silver database) | `default: "palo_alto"` |

**`resources/sdp.yml`** — update these fields:

| Find | Replace with |
|---|---|
| `<source>_<source_type>_sdp` | `palo_alto_firewall_sdp` |
| `<SOURCE> <SOURCE_TYPE> (SDP)` | `Palo Alto Firewall (SDP)` |
| `pipelines/<source>/<source_type>/preset.yaml` | `pipelines/palo_alto/firewall/preset.yaml` |

**`resources/sss.yml`** — update these fields:

| Find | Replace with |
|---|---|
| `<source>_<source_type>_sss` | `palo_alto_firewall_sss` |
| `<SOURCE> <SOURCE_TYPE> (SSS)` | `Palo Alto Firewall (SSS)` |
| `pipelines/<source>/<source_type>/preset.yaml` | `pipelines/palo_alto/firewall/preset.yaml` |
| `<source>_<source_type>` (checkpoint subdirectory) | `palo_alto_firewall` |

---

## Step 4: Set your variables

Open `bundles/<source>/<source_type>/databricks.yml` and fill in the `targets` section:

```yaml
targets:
  dev:
    workspace:
      host: "https://<your-workspace>.azuredatabricks.net"
    variables:
      bronze_catalog: "cyber_lakehouse"
      silver_catalog: "cyber_lakehouse"
      gold_catalog:   "cyber_lakehouse"
      bronze_database: "palo_alto"
      silver_database: "palo_alto"
```

`repo_path` defaults to `/Workspace/Users/<current-user>/dsl_lite`. Override it only if your
dsl_lite clone is at a different workspace path (e.g. under `/Workspace/Repos/`).

---

## Step 5: Select execution mode

In `databricks.yml`, uncomment the mode you want to deploy:

```yaml
# SDP (recommended, serverless):
include:
  - resources/sdp.yml

# SSS (classic compute):
# include:
#   - resources/sss.yml
```

---

## Step 6: Validate and deploy

```bash
cd bundles/<source>/<source_type>

# Validate — catches config errors before deploying
databricks bundle validate -t dev

# Deploy
databricks bundle deploy -t dev

# Run the pipeline
databricks bundle run <source>_<source_type>_sdp -t dev
```

---

## Step 7: Tear down (optional)

```bash
databricks bundle destroy -t dev
```
