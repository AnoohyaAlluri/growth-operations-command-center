"""Validation pipeline for the synthetic Growth & Operations Command Center data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import pandas as pd

PROJECT_STATUSES = {"Planning", "On Track", "At Risk", "Blocked", "Complete"}
PRIORITIES = {"Low", "Medium", "High", "Critical"}
BLOCKER_SEVERITIES = {"Low", "Medium", "High", "Critical"}
BLOCKER_STATUSES = {"Open", "Escalated", "Closed"}
DECISION_STATUSES = {"Pending", "Approved", "Rejected"}
VALIDATION_STATUSES = {"Pending", "Validated", "Review Required"}
DIRECTIONS = {"higher_is_better", "lower_is_better"}


def load_data(data_dir: Path) -> Dict[str, pd.DataFrame]:
    """Load all source CSVs."""
    return {
        "projects": pd.read_csv(data_dir / "synthetic_projects.csv"),
        "kpis": pd.read_csv(data_dir / "synthetic_kpis.csv"),
        "blockers": pd.read_csv(data_dir / "synthetic_blockers.csv"),
        "decisions": pd.read_csv(data_dir / "synthetic_decisions.csv"),
        "updates": pd.read_csv(data_dir / "synthetic_weekly_updates.csv"),
    }


def _check_unique(df: pd.DataFrame, column: str, label: str, errors: List[str]) -> None:
    duplicates = df.loc[df[column].duplicated(keep=False), column].astype(str).tolist()
    if duplicates:
        errors.append(f"{label}: duplicate {column} values found: {sorted(set(duplicates))}")


def _check_required(df: pd.DataFrame, columns: List[str], label: str, errors: List[str]) -> None:
    for column in columns:
        missing = df[column].isna() | (df[column].astype(str).str.strip() == "")
        if missing.any():
            errors.append(f"{label}: {int(missing.sum())} record(s) missing required field '{column}'.")


def validate_data(data_dir: Path) -> Dict[str, object]:
    """Run referential, categorical, date, and business-rule validation."""
    frames = load_data(data_dir)
    projects = frames["projects"]
    kpis = frames["kpis"]
    blockers = frames["blockers"]
    decisions = frames["decisions"]
    updates = frames["updates"]

    errors: List[str] = []
    warnings: List[str] = []

    _check_unique(projects, "project_id", "projects", errors)
    _check_unique(kpis, "kpi_id", "kpis", errors)
    _check_unique(blockers, "blocker_id", "blockers", errors)
    _check_unique(decisions, "decision_id", "decisions", errors)
    _check_unique(updates, "update_id", "updates", errors)

    _check_required(projects, ["project_id", "project_name", "owner", "priority", "status", "due_date"], "projects", errors)
    _check_required(kpis, ["kpi_id", "project_id", "metric_name", "direction", "target_value", "actual_value"], "kpis", errors)
    _check_required(blockers, ["blocker_id", "project_id", "blocker_title", "severity", "owner", "status"], "blockers", errors)
    _check_required(decisions, ["decision_id", "project_id", "decision_title", "decision_owner", "status", "follow_up_action"], "decisions", errors)
    _check_required(updates, ["update_id", "project_id", "week_start", "accomplishment", "next_priority"], "updates", errors)

    invalid_status = sorted(set(projects["status"]) - PROJECT_STATUSES)
    if invalid_status:
        errors.append(f"projects: invalid status values: {invalid_status}")

    invalid_priority = sorted(set(projects["priority"]) - PRIORITIES)
    if invalid_priority:
        errors.append(f"projects: invalid priority values: {invalid_priority}")

    invalid_severity = sorted(set(blockers["severity"]) - BLOCKER_SEVERITIES)
    if invalid_severity:
        errors.append(f"blockers: invalid severity values: {invalid_severity}")

    invalid_blocker_status = sorted(set(blockers["status"]) - BLOCKER_STATUSES)
    if invalid_blocker_status:
        errors.append(f"blockers: invalid status values: {invalid_blocker_status}")

    invalid_decision_status = sorted(set(decisions["status"]) - DECISION_STATUSES)
    if invalid_decision_status:
        errors.append(f"decisions: invalid status values: {invalid_decision_status}")

    invalid_validation = sorted(set(kpis["validation_status"]) - VALIDATION_STATUSES)
    if invalid_validation:
        errors.append(f"kpis: invalid validation status values: {invalid_validation}")

    invalid_direction = sorted(set(kpis["direction"]) - DIRECTIONS)
    if invalid_direction:
        errors.append(f"kpis: invalid direction values: {invalid_direction}")

    project_ids = set(projects["project_id"])
    for label, frame in [("kpis", kpis), ("blockers", blockers), ("decisions", decisions), ("updates", updates)]:
        orphaned = sorted(set(frame["project_id"]) - project_ids)
        if orphaned:
            errors.append(f"{label}: orphaned project_id values: {orphaned}")

    progress = pd.to_numeric(projects["progress_pct"], errors="coerce")
    if progress.isna().any() or ((progress < 0) | (progress > 100)).any():
        errors.append("projects: progress_pct must be numeric and between 0 and 100.")

    completed_incomplete = projects[(projects["status"] == "Complete") & (progress < 100)]
    if not completed_incomplete.empty:
        errors.append("projects: completed projects must have progress_pct equal to 100.")

    for column in ["start_date", "due_date", "last_update"]:
        parsed = pd.to_datetime(projects[column], errors="coerce")
        if parsed.isna().any():
            errors.append(f"projects: invalid date values detected in {column}.")

    start_dates = pd.to_datetime(projects["start_date"], errors="coerce")
    due_dates = pd.to_datetime(projects["due_date"], errors="coerce")
    if (due_dates < start_dates).any():
        errors.append("projects: due_date cannot be earlier than start_date.")

    blocker_opened = pd.to_datetime(blockers["opened_date"], errors="coerce")
    blocker_target = pd.to_datetime(blockers["target_resolution_date"], errors="coerce")
    if blocker_opened.isna().any() or blocker_target.isna().any():
        errors.append("blockers: invalid opened_date or target_resolution_date.")
    if (blocker_target < blocker_opened).any():
        errors.append("blockers: target_resolution_date cannot be earlier than opened_date.")

    closed_missing_resolution = blockers[
        (blockers["status"] == "Closed")
        & (blockers["resolution_date"].fillna("").astype(str).str.strip() == "")
    ]
    if not closed_missing_resolution.empty:
        errors.append("blockers: closed blockers require a resolution_date.")

    target_numeric = pd.to_numeric(kpis["target_value"], errors="coerce")
    actual_numeric = pd.to_numeric(kpis["actual_value"], errors="coerce")
    if target_numeric.isna().any() or actual_numeric.isna().any():
        errors.append("kpis: target_value and actual_value must be numeric.")
    if (target_numeric < 0).any() or (actual_numeric < 0).any():
        errors.append("kpis: target_value and actual_value cannot be negative.")

    missing_evidence = projects["evidence_reference"].fillna("").astype(str).str.strip() == ""
    if missing_evidence.any():
        warnings.append(f"projects: {int(missing_evidence.sum())} record(s) have no evidence reference.")

    report = {
        "status": "PASS" if not errors else "FAIL",
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "row_counts": {name: int(len(frame)) for name, frame in frames.items()},
    }
    return report


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    data_dir = project_root / "data"
    output_dir = project_root / "outputs"
    output_dir.mkdir(exist_ok=True)

    report = validate_data(data_dir)
    output_path = output_dir / "validation_report.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
