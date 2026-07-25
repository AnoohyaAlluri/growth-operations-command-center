"""Create a leadership-facing risk register from project and blocker data."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import pandas as pd

from src.calculate_kpis import (
    PRIORITY_WEIGHT,
    SEVERITY_WEIGHT,
    run_pipeline,
)


REQUIRED_HEALTH_COLUMNS = {
    "project_id",
    "project_name",
    "owner",
    "priority",
    "status",
    "progress_pct",
    "days_to_due",
    "is_overdue",
    "due_soon",
    "open_blockers",
    "high_critical_blockers",
    "avg_attainment_pct",
    "kpis_review_required",
    "risk_score",
    "health",
    "health_reason",
    "reporting_date",
}

REQUIRED_BLOCKER_COLUMNS = {
    "blocker_id",
    "project_id",
    "blocker_title",
    "severity",
    "owner",
    "status",
    "opened_date",
}


def _validate_columns(
    frame: pd.DataFrame,
    required_columns: set[str],
    label: str,
) -> None:
    """Confirm that a DataFrame contains all required columns."""

    missing_columns = sorted(
        required_columns - set(frame.columns)
    )

    if missing_columns:
        raise ValueError(
            f"{label}: missing required column(s): "
            f"{missing_columns}"
        )


def _join_unique(values: pd.Series) -> str:
    """Join unique, nonblank values into one readable field."""

    cleaned = (
        values.astype("string")
        .str.strip()
        .dropna()
    )

    unique_values = sorted(
        {
            value
            for value in cleaned.tolist()
            if value
        }
    )

    return " | ".join(unique_values)


def _resolve_reporting_date(
    health: pd.DataFrame,
) -> pd.Timestamp:
    """Resolve the reporting date stored in project-health output."""

    reporting_dates = pd.to_datetime(
        health["reporting_date"],
        errors="coerce",
    ).dropna()

    if reporting_dates.empty:
        raise ValueError(
            "project_health: no valid reporting_date was found."
        )

    return pd.Timestamp(
        reporting_dates.max()
    ).normalize()


def _build_blocker_summary(
    blockers: pd.DataFrame,
    reporting_date: pd.Timestamp,
) -> pd.DataFrame:
    """Aggregate open and escalated blocker details by project."""

    open_blockers = blockers[
        blockers["status"].isin(
            ["Open", "Escalated"]
        )
    ].copy()

    output_columns = [
        "project_id",
        "blocker_count_detail",
        "escalated_blockers",
        "highest_severity",
        "highest_severity_score",
        "blocker_titles",
        "blocker_owners",
        "oldest_blocker_date",
        "maximum_days_blocked",
    ]

    if open_blockers.empty:
        return pd.DataFrame(
            columns=output_columns
        )

    open_blockers["severity_score"] = (
        open_blockers["severity"]
        .map(SEVERITY_WEIGHT)
        .fillna(0)
        .astype(int)
    )

    open_blockers["escalated_flag"] = (
        open_blockers["status"]
        .eq("Escalated")
        .astype(int)
    )

    open_blockers["opened_date"] = pd.to_datetime(
        open_blockers["opened_date"],
        errors="coerce",
    )

    if open_blockers["opened_date"].isna().any():
        raise ValueError(
            "blockers: invalid opened_date values detected."
        )

    open_blockers["days_blocked"] = (
        reporting_date
        - open_blockers["opened_date"]
    ).dt.days.clip(lower=0)

    blocker_summary = (
        open_blockers
        .groupby(
            "project_id",
            as_index=False,
        )
        .agg(
            blocker_count_detail=(
                "blocker_id",
                "count",
            ),
            escalated_blockers=(
                "escalated_flag",
                "sum",
            ),
            highest_severity_score=(
                "severity_score",
                "max",
            ),
            blocker_titles=(
                "blocker_title",
                _join_unique,
            ),
            blocker_owners=(
                "owner",
                _join_unique,
            ),
            oldest_blocker_date=(
                "opened_date",
                "min",
            ),
            maximum_days_blocked=(
                "days_blocked",
                "max",
            ),
        )
    )

    severity_lookup = {
        score: severity
        for severity, score in SEVERITY_WEIGHT.items()
    }

    blocker_summary["highest_severity"] = (
        blocker_summary["highest_severity_score"]
        .map(severity_lookup)
        .fillna("None")
    )

    blocker_summary["oldest_blocker_date"] = (
        blocker_summary["oldest_blocker_date"]
        .dt.date
        .astype("string")
    )

    return blocker_summary[
        output_columns
    ]


def _leadership_action(
    row: pd.Series,
) -> str:
    """Create a leadership-facing action based on project risk."""

    if (
        row["health"] == "Critical"
        or row["highest_severity"] == "Critical"
        or row["status"] == "Blocked"
    ):
        return (
            "Immediate escalation, owner confirmation, "
            "and recovery action required"
        )

    if (
        row["health"] == "Watch"
        or row["highest_severity"] == "High"
        or bool(row["is_overdue"])
    ):
        return (
            "Review in the next operating meeting "
            "and confirm mitigation plan"
        )

    if bool(row["due_soon"]):
        return (
            "Confirm milestone readiness and monitor "
            "through the due date"
        )

    return (
        "Continue routine monitoring and maintain "
        "current execution plan"
    )


def classify_risks(
    project_root: Path,
    pipeline_outputs: Mapping[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """
    Build and save the leadership-facing risk register.

    Existing pipeline outputs may be supplied to prevent the KPI
    pipeline from being executed more than once.
    """

    outputs = (
        dict(pipeline_outputs)
        if pipeline_outputs is not None
        else run_pipeline(project_root)
    )

    if "project_health" not in outputs:
        raise KeyError(
            "Pipeline outputs do not contain 'project_health'."
        )

    if "blockers" not in outputs:
        raise KeyError(
            "Pipeline outputs do not contain 'blockers'."
        )

    health = outputs["project_health"].copy()
    blockers = outputs["blockers"].copy()

    _validate_columns(
        health,
        REQUIRED_HEALTH_COLUMNS,
        "project_health",
    )

    _validate_columns(
        blockers,
        REQUIRED_BLOCKER_COLUMNS,
        "blockers",
    )

    reporting_date = _resolve_reporting_date(
        health
    )

    blocker_summary = _build_blocker_summary(
        blockers,
        reporting_date,
    )

    selected_health_columns = [
        "project_id",
        "project_name",
        "owner",
        "priority",
        "status",
        "progress_pct",
        "days_to_due",
        "is_overdue",
        "due_soon",
        "open_blockers",
        "high_critical_blockers",
        "avg_attainment_pct",
        "kpis_review_required",
        "risk_score",
        "health",
        "health_reason",
        "reporting_date",
    ]

    risk_register = health[
        selected_health_columns
    ].merge(
        blocker_summary,
        on="project_id",
        how="left",
    )

    text_defaults = {
        "highest_severity": "None",
        "blocker_titles": "No open blockers",
        "blocker_owners": "No assigned blocker owner",
        "oldest_blocker_date": "",
    }

    for column, default_value in text_defaults.items():
        risk_register[column] = (
            risk_register[column]
            .fillna(default_value)
        )

    numeric_defaults = [
        "blocker_count_detail",
        "escalated_blockers",
        "highest_severity_score",
        "maximum_days_blocked",
    ]

    risk_register[numeric_defaults] = (
        risk_register[numeric_defaults]
        .fillna(0)
    )

    risk_register[
        "blocker_count_detail"
    ] = (
        risk_register[
            "blocker_count_detail"
        ]
        .astype(int)
    )

    risk_register[
        "escalated_blockers"
    ] = (
        risk_register[
            "escalated_blockers"
        ]
        .astype(int)
    )

    risk_register[
        "highest_severity_score"
    ] = (
        risk_register[
            "highest_severity_score"
        ]
        .astype(int)
    )

    risk_register[
        "maximum_days_blocked"
    ] = (
        risk_register[
            "maximum_days_blocked"
        ]
        .astype(int)
    )

    risk_register[
        "priority_score"
    ] = (
        risk_register["priority"]
        .map(PRIORITY_WEIGHT)
        .fillna(0)
        .astype(int)
    )

    risk_register[
        "leadership_action"
    ] = risk_register.apply(
        _leadership_action,
        axis=1,
    )

    risk_register = (
        risk_register
        .sort_values(
            by=[
                "risk_score",
                "priority_score",
                "highest_severity_score",
                "days_to_due",
            ],
            ascending=[
                False,
                False,
                False,
                True,
            ],
            na_position="last",
        )
        .reset_index(drop=True)
    )

    risk_register[
        "risk_rank"
    ] = (
        risk_register.index
        + 1
    )

    final_columns = [
        "risk_rank",
        "project_id",
        "project_name",
        "owner",
        "priority",
        "status",
        "progress_pct",
        "days_to_due",
        "is_overdue",
        "due_soon",
        "risk_score",
        "health",
        "health_reason",
        "leadership_action",
        "open_blockers",
        "high_critical_blockers",
        "escalated_blockers",
        "highest_severity",
        "blocker_titles",
        "blocker_owners",
        "oldest_blocker_date",
        "maximum_days_blocked",
        "avg_attainment_pct",
        "kpis_review_required",
        "reporting_date",
    ]

    risk_register = risk_register[
        final_columns
    ]

    output_dir = (
        project_root
        / "outputs"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    risk_register.to_csv(
        output_dir
        / "risk_register.csv",
        index=False,
    )

    return risk_register


def main() -> None:
    """Run risk classification directly from the command line."""

    project_root = (
        Path(__file__)
        .resolve()
        .parents[1]
    )

    risk_register = classify_risks(
        project_root
    )

    print(
        risk_register
        .head(10)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
