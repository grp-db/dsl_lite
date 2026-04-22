# Contributing to DSL Lite

DSL Lite is a Databricks Data & AI Forward Deployed Engineering accelerator. The most common contributions are:

- **New pipeline presets** — adding support for a new log source
- **New DAB bundles** — adding deployment config for a new pipeline
- **Bug fixes** — correcting field expressions, regex patterns, or OCSF mappings
- **Documentation** — improving tutorials, docs, or inline comments
- **Augmentation** — improve or extend agent skills

---

## Quick Start

```bash
git clone https://github.com/<org>/dsl_lite
cd dsl_lite
git checkout -b feature/my-source-sourcetype
```

---

## Syncing to a Customer Repo

Use this workflow to mirror the latest `grp-db/dsl_lite` changes into a customer's fork. These commands run in a **Databricks cluster terminal**.

> **Note:** Cluster terminals are ephemeral — local clones and `git config` settings are lost when a cluster restarts or terminates. Re-run the full setup after any cluster restart.

### First time (or after a cluster restart)

```bash
git clone https://github.com/grp-db/dsl_lite.git
cd dsl_lite
git remote rename origin upstream
git remote add origin https://<token>@github.com/<customer-org>/dsl_lite.git
git config user.email <email>
git config user.name <name>
```

Replace `<token>` with a GitHub PAT that has write access to the customer repo.

### Every sync (same session, cluster still running)

```bash
cd dsl_lite
git pull upstream main
git push origin main --force
```

### After pushing — update the Databricks workspace

| Method | Steps |
|---|---|
| **Databricks Repos UI** | Open the repo in the customer workspace → three-dot menu → **Pull** |
| **DABs deploy** | `databricks bundle deploy --target <env>` (no Repos sync needed) |

---

## Adding a New Pipeline

### Step 1 — Build the preset

Follow [tutorials/building-a-preset-end-to-end.md](tutorials/building-a-preset-end-to-end.md).

**Option A — Agent-assisted (recommended for new sources)**

Use the **Preset Agent** notebook (`notebooks/agent/preset_agent.py`) in your Databricks workspace to generate a first-draft `preset.yaml` from a UC table or raw log samples via the Databricks Foundation Model API:

1. Open `notebooks/agent/preset_agent.py` in your workspace.
2. Set `source_name`, `source_type`, and point `source_table` or `raw_sample_path` at your data.
3. Run — the agent produces a complete `preset.yaml` draft with bronze, silver, and gold layers.
4. Copy the output into `pipelines/<source>/<source_type>/preset.yaml` and fill in the `author` placeholder.

**Option B — Manual (copy the template)**

```bash
mkdir -p pipelines/<source>/<source_type>
cp pipelines/templates/preset.yaml pipelines/<source>/<source_type>/preset.yaml
# Edit the preset — replace all placeholders, add autoloader path, parse fields
```

**Iterate with the Preset Explorer**

Use the **Preset Explorer** notebook (`notebooks/explorer/preset_explorer.py`) in your Databricks workspace to run bronze, silver, and gold transforms interactively against real sample data and iterate on the YAML before committing.

### Step 2 — Validate the preset

```bash
python3 vault/validate_preset.py pipelines/<source>/<source_type>/preset.yaml
```

All checks must pass (no `✗` errors) before opening a PR. Warnings (`⚠`) are advisory.

### Step 3 — Add a bundle

Follow [tutorials/adding-a-bundle.md](tutorials/adding-a-bundle.md):

```bash
mkdir -p bundles/<source>/<source_type>/resources
cp bundles/templates/databricks.yml bundles/<source>/<source_type>/databricks.yml
cp bundles/templates/sdp.yml        bundles/<source>/<source_type>/resources/sdp.yml
cp bundles/templates/sss.yml        bundles/<source>/<source_type>/resources/sss.yml
# Replace all <source>/<source_type> placeholders
```

Validate the bundle locally (requires Databricks CLI configured):

```bash
cd bundles/<source>/<source_type>
databricks bundle validate -t dev
```

### Step 4 — Update the Available Bundles table

Add a row to the **Available Bundles** table in [bundles/README.md](bundles/README.md):

```markdown
| `<source>/<source_type>` | `<source>_<source_type>_sdp` | `<source>_<source_type>_sss` | <ocsf_tables> |
```

### Step 5 — Open a PR

```bash
git add pipelines/<source>/<source_type>/preset.yaml
git add bundles/<source>/<source_type>/
git add bundles/README.md
git commit -m "add <source>/<source_type> pipeline and bundle"
git push origin feature/my-source-sourcetype
```

---

## Validating All Presets

```bash
# Validate all pipelines at once
python3 vault/validate_preset.py

# Or via make
make validate-presets
```

---

## Updating OCSF Templates

If you add or change fields in `notebooks/ddl/create_ocsf_tables.py`, run the vault
utilities to keep `ocsf_templates/` in sync:

```bash
# Check which templates are missing fields
python3 vault/check_template_fields.py

# Automatically add missing fields (review changes before committing)
python3 vault/add_missing_fields.py
```

---

## Conventions

| Area | Convention |
|---|---|
| Pipeline names | `<source>_<source_type>` (snake_case) |
| Bronze table | `<source>_<source_type>_bronze` |
| Silver table | `<source>_<source_type>_silver` |
| Gold tables | OCSF class name, e.g. `network_activity`, `authentication` |
| Bundle name | `dsl_lite_<source>_<source_type>` |
| Resource keys | `<source>_<source_type>_sdp` / `<source>_<source_type>_sss` |
| OCSF version | `1.7.0` (update `metadata.version` if upgrading) |

### Gold field ordering

Follow the ordering in `ocsf_templates/` — category/class/type first, then activity,
then action/status, then time fields, then metadata, then endpoint/object structs,
then `raw_data` and `unmapped` last.

---

## Questions

Open an issue or reach out to **Garrett R Peternel, Databricks Data & AI Forward Deployed Engineering**.
