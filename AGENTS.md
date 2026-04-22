# DSL Lite

This file provides guidance to AI-based development tools when working with files in this repository.

DSL Lite is a declarative data pipeline framework for ingesting and normalizing raw security logs into OCSF-compliant tables using a medallion architecture (Bronze → Silver → Gold).

## Repository Structure

- `src/` — Core pipeline engine (DSL parser, medallion orchestration)
- `pipelines/<source>/<source_type>/preset.yaml` — Data ingestion presets (one per log source)
- `pipelines/templates/preset.yaml` — Annotated template for new presets
- `bundles/` — Declarative Automation Bundle definitions for deployment
- `ocsf_templates/` — Ready-made OCSF field lists for all event classes
- `docs/dsl_lite_features/` — Architecture, lookup joins, and advanced configuration docs
- `notebooks/explorer/` — Interactive preset development and testing (`preset_explorer.py`)
- `notebooks/agent/` — Foundation-model-powered preset agent (`preset_agent.py`)
- `notebooks/profiler/` — Pipeline validation notebook (`pipeline_profiler.py`): schema diff, data profile, E2E sample run, OCSF coverage
- `notebooks/ddl/` — OCSF table DDL / UC setup scripts
- `tutorials/` — End-to-end guides for preset authoring and bundle deployment
- `vault/` — Preset validators, template sync scripts, source-lookup utilities
- `.agents/skills/dsl-lite-preset-dev/` — Skill bundle loaded by AI tooling (SKILL.md + references/)
- `raw_logs/` — Sample log files for testing presets

## Working on Presets

Presets are YAML files that define how raw logs flow through the three layers:

- **Bronze** — ingest raw files via Auto Loader, extract timestamp, tag source/sourcetype
- **Silver** — parse structured fields from `value` (text) or `data` VARIANT (JSON)
- **Gold** — map silver columns to OCSF-compliant field paths using dot notation

Use relevant skills when developing or modifying presets (if they are defined).
