# GitHub Sync Guide — Mirroring DSL Lite to a Customer Repo

This guide covers syncing `grp-db/dsl_lite` to a customer-owned GitHub repo. Use it when a customer cannot access the internal repo directly but needs a copy in their own GitHub organization.

> This is one deployment pattern — not required for all customers. If the customer can access `grp-db/dsl_lite` directly (or uses DABs pointing at the internal repo), skip this.

---

## How it works

```
[grp-db/dsl_lite] ──pull upstream──► [local clone] ──push origin──► [customer repo]
    (upstream)                                                            (origin)
```

---

## Setup (first time, or after a cluster restart)

These commands run in a **Databricks cluster terminal**.

> **Cluster terminals are ephemeral** — local clones and `git config` settings are lost when a cluster restarts or terminates. Re-run this full block after any restart.

```bash
git clone https://github.com/grp-db/dsl_lite.git
cd dsl_lite
git remote rename origin upstream
git remote add origin https://<token>@github.com/<customer-org>/dsl_lite.git
git config user.email <email>
git config user.name <name>
```

Replace `<token>` with a GitHub PAT that has write access to the customer repo.

---

## Sync (same session, cluster still running)

```bash
cd dsl_lite
git pull upstream main
git push origin main --force
```

---

## After pushing — update the Databricks workspace

| Method | Steps |
|---|---|
| **Databricks Repos UI** | Open the repo in the customer workspace → three-dot menu → **Pull** |
| **DABs deploy** | `databricks bundle deploy --target <env>` (no Repos sync needed) |

---

## Notes

- `--force` is required because the customer repo may have diverged (e.g. local config changes). If the customer has made changes they want to preserve, merge manually instead of force-pushing.
- If the customer repo doesn't exist yet, create it on GitHub first (empty, no README) before running setup.
- For customers using DABs exclusively, the Repos sync step is optional — the bundle deploy reads source files from workspace paths directly.
