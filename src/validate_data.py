"""Validation pipeline for the synthetic Growth & Operations Command Center data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


DATA_FILES = {
    "projects": "synthetic_projects.csv",
    "kpis": "synthetic_kpis.csv",
    "blockers": "synthetic_blockers.csv",
    "decisions": "synthetic_decisions.csv",
    "updates": "synthetic_weekly_updates.csv",
}

EXPECTED_COLUMNS = {
    "projects": {
        "project_id",
        "project_name",
        "owner",
        "priority",
        "status",
        "progress_pct",
        "start_date",
        "due_date",
        "last_update",
        "evidence_reference",
    },
    "kpis": {
        "kpi_id",
        "project_id",
        "metric_name",
        "direction",
        "target_value",
        "actual_value",
        "validation_status",
    },
    "blockers": {
        "blocker_id",
        "project_id",
        "blocker_title",
        "severity",
        "owner",
        "status",
        "opened_date",
        "target_resolution_date",
        "resolution_date",
    },
    "decisions": {
        "decision_id",
        "project_id",
        "decision_title",
        "decision_owner",
        "status",
        "follow_up_action",
    },
    "updates": {
        "update_id",
        "project_id",
        "week_start",
        "accomplishment",
        "next_priority",
    },
}

REQUIRED_FIELDS = {
    "projects": [
        "project_id",
        "project_name",
        "owner",
        "priority",
        "status",
        "progress_pct",
        "start_date",
        "due_date",
        "last_update",
    ],
    "kpis": [
        "kpi_id",
        "project_id",
        "metric_name",
        "direction",
        "target_value",
        "actual_value",
        "validation_status",
    ],
    "blockers": [
        "blocker_id",
        "project_id",
        "blocker_title",
        "severity",
        "owner",
        "status",
        "opened_date",
        "target_resolution_date",
    ],
    "decisions": [
        "decision_id",
        "project_id",
        "decision_title",
        "decision_owner",
        "status",
        "follow_up_action",
    ],
    "updates": [
        "update_id",
        "project_id",
        "week_start",
        "accomplishment",
        "next_priority",
    ],
}

PROJECT_STATUSES = {
    "Planning",
    "On Track",
    "At Risk",
    "Blocked",
    "Complete",
}

PRIORITIES = {
    "Low",
    "Medium",
    "High",
    "Critical",
}

BLOCKER_SEVERITIES = {
    "Low",
    "Medium",
    "High",
    "Critical",
}

BLOCKER_STATUSES = {
    "Open",
    "Escalated",
    "Closed",
}

DECISION_STATUSES = {
    "Pending",
    "Approved",
    "Rejected",
}

VALIDATION_STATUSES = {
    "Pending",
    "Validated",
    "Review Required",
}

DIRECTIONS = {
    "higher_is_better",
    "lower_is_better",
}


def load_data(data_dir: Path) -> dict[str, pd.DataFrame]:
    """Load all required source CSV files."""

    if not data_dir.exists():
        raise FileNotFoundError(
            f"Data directory does not exist: {data_dir}"
        )

    frames: dict[str, pd.DataFrame] = {}

    for label, filename in DATA_FILES.items():
        file_path = data_dir / filename

        if not file_path.exists():
            raise FileNotFoundError(
                f"Required data file is missing: {file_path}"
            )

        try:
            frames[label] = pd.read_csv(file_path)
        except Exception as exc:
            raise ValueError(
                f"Unable to read {file_path}: {exc}"
            ) from exc

    return frames


def _blank_mask(series: pd.Series) -> pd.Series:
    """Identify null or blank values."""

    return (
        series.astype("string")
        .str.strip()
        .fillna("")
        .eq("")
    )


def _clean_values(series: pd.Series) -> set[str]:
    """Return normalized, nonblank string values."""

    cleaned = (
        series.astype("string")
        .str.strip()
        .fillna("")
    )

    return set(
        cleaned[cleaned.ne("")].tolist()
    )


def _check_unique(
    df: pd.DataFrame,
    column: str,
    label: str,
    errors: list[str],
) -> None:
    """Check whether an identifier column contains duplicates."""

    duplicates = (
        df.loc[df[column].duplicated(keep=False), column]
        .astype("string")
        .str.strip()
        .fillna("")
    )

    duplicate_values = sorted(
        {
            value
            for value in duplicates.tolist()
            if value
        }
    )

    if duplicate_values:
        errors.append(
            f"{label}: duplicate {column} values found: "
            f"{duplicate_values}"
        )


def _check_required(
    df: pd.DataFrame,
    columns: list[str],
    label: str,
    errors: list[str],
) -> None:
    """Check that required fields are populated."""

    for column in columns:
        missing = _blank_mask(df[column])

        if missing.any():
            errors.append(
                f"{label}: {int(missing.sum())} record(s) "
                f"missing required field '{column}'."
            )


def _check_allowed(
    df: pd.DataFrame,
    column: str,
    allowed: set[str],
    label: str,
    errors: list[str],
) -> None:
    """Check categorical values against an approved set."""

    invalid_values = sorted(
        _clean_values(df[column]) - allowed
    )

    if invalid_values:
        errors.append(
            f"{label}: invalid {column} values: "
            f"{invalid_values}"
        )


def _build_report(
    frames: dict[str, pd.DataFrame],
    errors: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    """Build the final validation report."""

    return {
        "status": "PASS" if not errors else "FAIL",
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "row_counts": {
            name: int(len(frame))
            for name, frame in frames.items()
        },
    }


def validate_data(data_dir: Path) -> dict[str, Any]:
    """
    Run schema, referential, categorical, date,
    numeric, and business-rule validation.
    """

    errors: list[str] = []
    warnings: list[str] = []

    try:
        frames = load_data(data_dir)
    except (FileNotFoundError, ValueError) as exc:
        return {
            "status": "FAIL",
            "error_count": 1,
            "warning_count": 0,
            "errors": [str(exc)],
            "warnings": [],
            "row_counts": {},
        }

    # Validate the dataset schemas before accessing columns.
    for label, expected_columns in EXPECTED_COLUMNS.items():
        missing_columns = sorted(
            expected_columns - set(frames[label].columns)
        )

        if missing_columns:
            errors.append(
                f"{label}: missing required column(s): "
                f"{missing_columns}"
            )

    # Stop field-level validation when required columns are missing.
    if errors:
        return _build_report(
            frames,
            errors,
            warnings,
        )

    projects = frames["projects"]
    kpis = frames["kpis"]
    blockers = frames["blockers"]
    decisions = frames["decisions"]
    updates = frames["updates"]

    identifier_columns = {
        "projects": "project_id",
        "kpis": "kpi_id",
        "blockers": "blocker_id",
        "decisions": "decision_id",
        "updates": "update_id",
    }

    # Validate unique record identifiers.
    for label, column in identifier_columns.items():
        _check_unique(
            frames[label],
            column,
            label,
            errors,
        )

    # Validate required values.
    for label, columns in REQUIRED_FIELDS.items():
        _check_required(
            frames[label],
            columns,
            label,
            errors,
        )

    # Validate approved categorical values.
    _check_allowed(
        projects,
        "status",
        PROJECT_STATUSES,
        "projects",
        errors,
    )

    _check_allowed(
        projects,
        "priority",
        PRIORITIES,
        "projects",
        errors,
    )

    _check_allowed(
        blockers,
        "severity",
        BLOCKER_SEVERITIES,
        "blockers",
        errors,
    )

    _check_allowed(
        blockers,
        "status",
        BLOCKER_STATUSES,
        "blockers",
        errors,
    )

    _check_allowed(
        decisions,
        "status",
        DECISION_STATUSES,
        "decisions",
        errors,
    )

    _check_allowed(
        kpis,
        "validation_status",
        VALIDATION_STATUSES,
        "kpis",
        errors,
    )

    _check_allowed(
        kpis,
        "direction",
        DIRECTIONS,
        "kpis",
        errors,
    )

    # Validate project relationships.
    project_ids = _clean_values(
        projects["project_id"]
    )

    related_frames = [
        ("kpis", kpis),
        ("blockers", blockers),
        ("decisions", decisions),
        ("updates", updates),
    ]

    for label, frame in related_frames:
        orphaned_ids = sorted(
            _clean_values(frame["project_id"])
            - project_ids
        )

        if orphaned_ids:
            errors.append(
                f"{label}: orphaned project_id values: "
                f"{orphaned_ids}"
            )

    # Validate project progress.
    progress = pd.to_numeric(
        projects["progress_pct"],
        errors="coerce",
    )

    if progress.isna().any():
        errors.append(
            "projects: progress_pct must contain numeric values."
        )

    invalid_progress = (
        progress.dropna().lt(0)
        | progress.dropna().gt(100)
    )

    if invalid_progress.any():
        errors.append(
            "projects: progress_pct must be between 0 and 100."
        )

    completed_projects = (
        projects["status"]
        .astype("string")
        .str.strip()
        .eq("Complete")
    )

    incomplete_completed_projects = (
        completed_projects
        & progress.ne(100)
    )

    if incomplete_completed_projects.any():
        errors.append(
            "projects: completed projects must have "
            "progress_pct equal to 100."
        )

    # Validate project dates.
    project_dates: dict[str, pd.Series] = {}

    for column in [
        "start_date",
        "due_date",
        "last_update",
    ]:
        parsed_dates = pd.to_datetime(
            projects[column],
            errors="coerce",
        )

        project_dates[column] = parsed_dates

        if parsed_dates.isna().any():
            errors.append(
                f"projects: invalid date values detected "
                f"in {column}."
            )

    due_before_start = (
        project_dates["start_date"].notna()
        & project_dates["due_date"].notna()
        & (
            project_dates["due_date"]
            < project_dates["start_date"]
        )
    )

    if due_before_start.any():
        errors.append(
            "projects: due_date cannot be earlier "
            "than start_date."
        )

    # Validate blocker dates.
    opened_dates = pd.to_datetime(
        blockers["opened_date"],
        errors="coerce",
    )

    target_resolution_dates = pd.to_datetime(
        blockers["target_resolution_date"],
        errors="coerce",
    )

    if opened_dates.isna().any():
        errors.append(
            "blockers: invalid opened_date values detected."
        )

    if target_resolution_dates.isna().any():
        errors.append(
            "blockers: invalid target_resolution_date "
            "values detected."
        )

    target_before_opened = (
        opened_dates.notna()
        & target_resolution_dates.notna()
        & (
            target_resolution_dates
            < opened_dates
        )
    )

    if target_before_opened.any():
        errors.append(
            "blockers: target_resolution_date cannot "
            "be earlier than opened_date."
        )

    resolution_text = (
        blockers["resolution_date"]
        .astype("string")
        .str.strip()
        .fillna("")
    )

    resolution_provided = resolution_text.ne("")

    resolution_dates = pd.to_datetime(
        resolution_text.where(
            resolution_provided
        ),
        errors="coerce",
    )

    invalid_resolution_dates = (
        resolution_provided
        & resolution_dates.isna()
    )

    if invalid_resolution_dates.any():
        errors.append(
            "blockers: invalid resolution_date values detected."
        )

    closed_blockers = (
        blockers["status"]
        .astype("string")
        .str.strip()
        .eq("Closed")
    )

    closed_without_resolution = (
        closed_blockers
        & ~resolution_provided
    )

    if closed_without_resolution.any():
        errors.append(
            "blockers: closed blockers require "
            "a resolution_date."
        )

    resolution_before_opened = (
        closed_blockers
        & resolution_dates.notna()
        & opened_dates.notna()
        & (
            resolution_dates
            < opened_dates
        )
    )

    if resolution_before_opened.any():
        errors.append(
            "blockers: resolution_date cannot be "
            "earlier than opened_date."
        )

    # Validate KPI values.
    target_values = pd.to_numeric(
        kpis["target_value"],
        errors="coerce",
    )

    actual_values = pd.to_numeric(
        kpis["actual_value"],
        errors="coerce",
    )

    if target_values.isna().any():
        errors.append(
            "kpis: target_value must contain numeric values."
        )

    if actual_values.isna().any():
        errors.append(
            "kpis: actual_value must contain numeric values."
        )

    if target_values.dropna().lt(0).any():
        errors.append(
            "kpis: target_value cannot be negative."
        )

    if actual_values.dropna().lt(0).any():
        errors.append(
            "kpis: actual_value cannot be negative."
        )

    # Validate weekly update dates.
    week_start_dates = pd.to_datetime(
        updates["week_start"],
        errors="coerce",
    )

    if week_start_dates.isna().any():
        errors.append(
            "updates: invalid week_start values detected."
        )

    # Evidence references are recommended but not mandatory.
    missing_evidence = _blank_mask(
        projects["evidence_reference"]
    )

    if missing_evidence.any():
        warnings.append(
            f"projects: {int(missing_evidence.sum())} "
            "record(s) have no evidence reference."
        )

    return _build_report(
        frames,
        errors,
        warnings,
    )


def main() -> None:
    """Run validation and save the report."""

    project_root = Path(__file__).resolve().parents[1]
    data_dir = project_root / "data"
    output_dir = project_root / "outputs"

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    report = validate_data(data_dir)

    output_path = (
        output_dir
        / "validation_report.json"
    )

    output_path.write_text(
        json.dumps(
            report,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            report,
            indent=2,
        )
    )

    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
