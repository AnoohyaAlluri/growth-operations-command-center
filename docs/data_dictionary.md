# Data Dictionary

## `synthetic_projects.csv`

| Field | Type | Description |
|---|---|---|
| project_id | string | Unique project identifier |
| project_name | string | Public-safe project title |
| category | string | Analytical or operational category |
| owner | string | Role accountable for delivery |
| priority | category | Low, Medium, High, Critical |
| status | category | Planning, On Track, At Risk, Blocked, Complete |
| start_date | date | Synthetic start date |
| due_date | date | Synthetic target completion date |
| progress_pct | number | Completion percentage from 0 to 100 |
| business_objective | string | Business problem addressed |
| evidence_reference | string | Public-safe evidence path |
| last_update | date | Most recent synthetic status update |

## `synthetic_kpis.csv`

| Field | Type | Description |
|---|---|---|
| kpi_id | string | Unique KPI identifier |
| project_id | string | Related project |
| metric_name | string | KPI title |
| direction | category | higher_is_better or lower_is_better |
| target_value | number | Planned target |
| actual_value | number | Current synthetic result |
| unit | string | Percent, count, or another unit |
| reporting_cadence | string | Weekly, biweekly, or monthly |
| data_source | string | Public-safe source description |
| validation_status | category | Pending, Validated, Review Required |
| last_updated | date | Synthetic update date |

## Other Registers

The blocker, decision, and weekly-update registers preserve operational context required for escalation and executive reporting.
