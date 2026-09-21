BEGIN;

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS analytics;

COMMENT ON SCHEMA staging IS 'Source-shaped ingestion tables and load validation results.';
COMMENT ON SCHEMA core IS 'Normalized, constrained operational data used as the production source of truth.';
COMMENT ON SCHEMA analytics IS 'Read-only reporting views for Power BI and operational analysis.';

COMMIT;
