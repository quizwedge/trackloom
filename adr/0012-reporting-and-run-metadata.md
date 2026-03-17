# 0012: Reporting and Run Metadata

- Status: Accepted

## Context
Large merges need auditability and reproducibility.

## Decision
Add apply reports in JSON and CSV, including run metadata and source linkage (`source_plan_json`, `source_decisions_file`).
When applying from a plan JSON, run metadata should reflect the plan's compare settings if provided;
otherwise these fields may be null and the report should indicate the source of the settings.

## Consequences
- Easier traceability and post-run analysis, including plan-vs-CLI setting provenance.
- Additional report files to manage.
