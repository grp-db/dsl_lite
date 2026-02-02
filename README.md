# DSL Lite - Lightweight Cybersecurity Data Pipeline Framework

> **🏗️ Databricks Cybersecurity Accelerator**  
> Built by Databricks Field Engineering & Professional Services

## Overview

**DSL Lite** is a reusable cybersecurity accelerator designed for building end-to-end cyber lakehouse architectures using an augmented medallion approach with [OCSF (Open Cybersecurity Schema Framework)](https://schema.ocsf.io/) compliance.

This lightweight, self-deployable framework uses configuration files called "presets" to transform security logs into bronze, silver, and gold layers with OCSF-compliant schemas. It's designed for customers building complex cybersecurity projects and use cases that require:
- **Scalable data ingestion** from multiple security log sources
- **Standardized schema transformation** to OCSF data models
- **Flexible deployment** in self-managed or restricted environments
- **Production-ready pipelines** with minimal configuration

### About This Accelerator

This accelerator was developed by the **Databricks Field Engineering and Professional Services teams** to enable customers to rapidly deploy enterprise-grade cybersecurity data pipelines. While Databricks owns the intellectual property, this accelerator is made publicly available to support the broader security community in building robust cyber lakehouse architectures on the Databricks platform.

## Project Structure

```
dsl_lite/
├── src/                          # All Python source code
│   ├── dsl_sdp.py               # Entry point for Spark Declarative Pipelines
│   ├── dsl_spark.py             # Entry point for Spark jobs
│   ├── dsl.py                   # Core DSL Lite logic
│   └── utils.py                 # Utility functions
├── notebooks/                    # Databricks notebooks
│   └── create_ocsf_tables.py    # Setup notebook for OCSF tables
├── pipelines/                    # Configuration presets (Cisco, Zeek, Cloudflare, etc.)
├── ocsf_templates/              # OCSF mapping templates
├── raw_logs/                    # Sample logs for testing
└── README.md                    # Documentation
```

## How to use

To deploy a new data streaming pipeline you need:

- **Databases**: Bronze, silver, and gold layers with OCSF-compliant tables (create using `notebooks/create_ocsf_tables.py`)
- **Preset configuration**: YAML files defining data transformations for your log source (located in `pipelines/` directory)
- **Input location(s)**: Configure data source paths in the preset's `autoloader.inputs` section

DSL Lite provides starter templates in the `ocsf_templates/` directory for common security log sources.

### Execute as Spark Declarative Pipeline (SDP)

> **Note**: Apache Spark™ includes **declarative pipelines** beginning in Spark 4.1 via the `pyspark.pipelines` module. Databricks Runtime extends these capabilities with additional APIs and integrations.

- Upload the `src` directory containing `dsl_sdp.py`, `dsl.py` and `utils.py` to your workspace.
- Create `source` and `source_type` folders (i.e. `cisco/ios`) under `pipelines` to your workspace.
- Create a Lakeflow Spark Declarative Pipeline and specify default catalogs and databases, plus the following required configurations:

  - `dsl_lite.config_file` (required) - should contain a full path to a configuration file that will be used to generate a pipeline.  Example: `/Workspace/Users/<user@email.com>/dsl_lite/pipelines/cisco/ios/preset.yaml`.
  - `dsl_lite.gold_catalog_name` (required) - the name of UC catalog containing gold tables.
  - `dsl_lite.gold_database_name` (required) - the name of UC database containing gold tables.
  - `dsl_lite.bronze_catalog_name` (optional) - the name of UC catalog containing bronze tables.
  - `dsl_lite.bronze_database_name` (required) - the name of UC database containing bronze tables.
  - `dsl_lite.silver_catalog_name` (optional) - the name of UC catalog containing silver tables.
  - `dsl_lite.silver_database_name` (required) - the name of UC database containing silver tables.

**Example configuration JSON:**
```json
{
  "configuration": {
    "dsl_lite.bronze_database_name": "bronze",
    "dsl_lite.silver_database_name": "silver",
    "dsl_lite.gold_database_name": "gold",
    "dsl_lite.config_file": "/Workspace/Users/user@email.com/dsl_lite/pipelines/cisco/ios/preset.yaml",
    "dsl_lite.gold_catalog_name": "dsl_lite"
  }
}
```

### Execute as Spark (Python) job

- Upload the `src` directory containing `dsl_spark.py`, `dsl.py` and `utils.py` to your workspace.
- Create `source` and `source_type` folders (e.g. `cisco/ios`) under `pipelines` to your workspace.
- Create a job with a notebook task referring `src/dsl_spark.py` and with following parameters:

  - `preset_file` (required) - should contain a full path to a configuration file that will be used to process data.  Example: `/Workspace/Users/<user@email.com>/dsl_lite/pipelines/cisco/ios/preset.yaml`.
  - `bronze_database` (required) - the name of database containing bronze tables - could be specified as `catalog.database`.
  - `silver_database` (required) - the name of database containing silver tables - could be specified as `catalog.database`.
  - `gold_database` (required) - the name of database containing gold tables - could be specified as `catalog.database`.
  - `checkpoints_location` (required) - the path to storage location (DBFS or Volume) to store checkpoints for specific job.
  - `continuous` (optional, default `False`) - if job should run continuously (`True`) or not (`False`).

**Example configuration JSON:**
```json
{
  "preset_file": "/Workspace/Users/user@email.com/dsl_lite/pipelines/cisco/ios/preset.yaml",
  "bronze_database": "dsl_lite.cisco",
  "silver_database": "dsl_lite.cisco",
  "gold_database": "dsl_lite.ocsf",
  "checkpoints_location": "/Volumes/dsl_lite/pipelines/checkpoints/cisco-ios",
  "continuous": "False"
}
```

## Key Features

- **Self-contained deployment**: No dependencies on external DSL infrastructure
- **OCSF-compliant**: Outputs data in Open Cybersecurity Schema Framework format
- **Multiple execution modes**: Spark Declarative Pipelines (SDP) or standalone Spark jobs
- **Flexible input sources**: Read from multiple locations, supports Databricks Volumes, S3, ADLS, etc.
- **Secret management**: Reference Databricks Secrets in configurations via `{{secrets/<scope>/<key>}}`
- **Streaming or batch**: Run continuously or in batch mode with `availableNow` trigger
- **High performance**: Optimized `dsl_id` generation (3x faster than UDF-based approach)

## Supported Data Sources

DSL Lite uses Databricks Auto Loader to ingest data from file-based sources:
- **Cloud Storage**: S3, ADLS Gen2, Google Cloud Storage
- **Databricks Volumes**: Unity Catalog volumes
- **DBFS**: Databricks File System
- **Log Formats**: JSON, JSON Lines, CSV, Parquet, text/syslog

Support for streaming sources (Kafka, Event Hubs, Kinesis) can be added based on customer requirements.

---

## License & Attribution

**Copyright © Databricks, Inc.**

This accelerator is developed and maintained by Databricks Field Engineering and Professional Services. Databricks retains all intellectual property rights to this software.

### Usage & Distribution

This accelerator is made publicly available to support customers and the broader community in building cybersecurity solutions on the Databricks Lakehouse Platform. You are free to:
- Use this accelerator in your production environments
- Modify and extend it to meet your specific requirements
- Share it within your organization

**Note**: This is a community-supported accelerator. For production support and customization services, please contact your Databricks account team or Professional Services.

### Support & Contributions

- **Issues & Questions**: Open an issue in the repository or contact your Databricks representative
- **Feature Requests**: Reach out to Databricks Field Engineering or Professional Services
- **Contributions**: Contributions are welcome - please coordinate with the Databricks team

---

**Built with ❤️ by Databricks Field Engineering & Professional Services**