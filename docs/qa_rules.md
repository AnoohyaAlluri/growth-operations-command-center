# QA and Governance Rules

## Identity and Referential Integrity

- Every project, KPI, blocker, decision, and update must have a unique ID.
- Every KPI, blocker, decision, and update must reference an existing project.

## Required Fields

- Projects require an owner, priority, status, and due date.
- KPIs require a direction, target, actual value, and data source.
- Blockers require severity, owner, status, and target resolution date.
- Decisions require an owner and follow-up action.

## Date Rules

- Project due dates cannot occur before start dates.
- Blocker target resolution dates cannot occur before opened dates.
- Closed blockers require resolution dates.

## Status Rules

- Completed projects must have 100% progress.
- Valid project statuses are Planning, On Track, At Risk, Blocked, and Complete.
- Valid blocker statuses are Open, Escalated, and Closed.

## KPI Rules

- Target and actual values must be numeric and nonnegative.
- Direction must be higher_is_better or lower_is_better.
- KPI target attainment is capped at 150% for visualization stability.

## Public-Safe Rule

No confidential organization, customer, employee, tenant, owner, address, contact, or financial information may be added to the repository.
