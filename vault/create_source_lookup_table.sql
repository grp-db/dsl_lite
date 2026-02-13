-- Create Delta table from source_lookup.csv
-- Run this in a Databricks notebook or SQL cell to create the lookup table

-- Option 1: Create table from CSV file (one-time setup)
CREATE OR REPLACE TABLE dsl_lite.lookups.source_metadata
USING DELTA
AS
SELECT * FROM read_files(
  '/Volumes/dsl_lite/vault/source_lookup.csv',
  format => 'csv',
  header => 'true',
  inferSchema => 'true'
);

-- Option 2: If you've already uploaded the CSV to a Volume, use this:
-- CREATE OR REPLACE TABLE dsl_lite.lookups.source_metadata
-- USING DELTA
-- AS
-- SELECT * FROM read_files(
--   '/Volumes/<catalog>/<schema>/<volume>/source_lookup.csv',
--   format => 'csv',
--   header => 'true',
--   inferSchema => 'true'
-- );

-- Verify the table was created correctly
SELECT * FROM dsl_lite.lookups.source_metadata;

