"""KPI and project-health calculations for the synthetic Command Center."""

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
}

EXPECTED_COLUMNS = {
    "projects": {
        "project_id",
        "status",
        "priority",
        "progress_pct",
        "due_date",
        "last_update",
    },
    "kpis": {
        "kpi_id",
        "project_id",
        "direction",
        "target_value",
        "actual_value",
        "validation_status",
    },
    "blockers": {
        "blocker_id",
        "project_id",
        "status",
        "severity",
        "opened_date",
    },
    "decisions": {
        "status",
    },
}

PRIORITY_WEIGHT = {
    "Low": 0,
    "Medium": 1,
    "High": 2,
    "Critical": 3,
}

SEVERITY_WEIGHT = {
    "Low": 1,
    "Medium": 2,
    "High": 3,
    "Critical": 4,
}

STATUS_WEIGHT = {
    "Complete": 0,
    "On Track": 0,
    "Planning": 1,
    "At Risk": 3,
    "Blocked": 5,
}

VALID_DIRECTIONS = {
    "higher_is_better",
    "lower_is_better",
}


def load_inputs(data_dir: Path) -> dict[str, pd.DataFrame]:
    """Load the project, KPI, blocker, and decision datasets."""

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

    _validate_input_schema(frames)

    return frames


def _validate_input_schema(
    frames: dict[str, pd.DataFrame],
) -> None:
    """Confirm that every dataset contains the required columns."""

    schema_errors: list[str] = []

    for label, required_columns in EXPECTED_COLUMNS.items():
        missing_columns = sorted(
            required_columns - set(frames[label].columns)
        )

        if missing_columns:
            schema_errors.append(
                f"{label}: missing required column(s): "
                f"{missing_columns}"
            )

    if schema_errors:
        raise ValueError(
            "Input schema validation failed: "
            + " | ".join(schema_errors)
        )


def _to_numeric(
    series: pd.Series,
    label: str,
) -> pd.Series:
    """Convert a series to numeric values and fail on invalid data."""

    numeric = pd.to_numeric(
        series,
        errors="coerce",
    )

    if numeric.isna().any():
        invalid_count = int(numeric.isna().sum())

        raise ValueError(
            f"{label}: {invalid_count} invalid numeric "
            "value(s) detected."
        )

    return numeric


def resolve_reporting_date(
    projects: pd.DataFrame,
    blockers: pd.DataFrame,
    reporting_date: str | pd.Timestamp | None = None,
) -> pd.Timestamp:
    """
    Resolve the reporting date.

    A supplied reporting date takes priority. Otherwise, the latest
    project update or blocker-opened date is used. The current date
    is used only when no valid activity dates are available.
    """

    if reporting_date is not None:
        resolved = pd.to_datetime(
            reporting_date,
            errors="coerce",
        )

        if pd.isna(resolved):
            raise ValueError(
                f"Invalid reporting date: {reporting_date}"
            )

        return pd.Timestamp(resolved).normalize()

    activity_dates: list[pd.Series] = []

    if "last_update" in projects.columns:
        activity_dates.append(
            pd.to_datetime(
                projects["last_update"],
                errors="coerce",
            )
        )

    if "opened_date" in blockers.columns:
        activity_dates.append(
            pd.to_datetime(
                blockers["opened_date"],
                errors="coerce",
            )
        )

    if activity_dates:
        combined_dates = pd.concat(
            activity_dates,
            ignore_index=True,
        ).dropna()

        if not combined_dates.empty:
            return pd.Timestamp(
                combined_dates.max()
            ).normalize()

    return pd.Timestamp.today().normalize()


def calculate_kpi_attainment(
    kpis: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate KPI variance, attainment, and target status."""

    result = kpis.copy()

    target = _to_numeric(
        result["target_value"],
        "kpis.target_value",
    )

    actual = _to_numeric(
        result["actual_value"],
        "kpis.actual_value",
    )

    if target.lt(0).any() or actual.lt(0).any():
        raise ValueError(
            "KPI target and actual values cannot be negative."
        )

    directions = (
        result["direction"]
        .astype("string")
        .str.strip()
    )

    invalid_directions = sorted(
        set(directions.dropna()) - VALID_DIRECTIONS
    )

    if invalid_directions:
        raise ValueError(
            "Invalid KPI direction value(s): "
            f"{invalid_directions}"
        )

    higher_is_better = directions.eq(
        "higher_is_better"
    )

    lower_is_better = directions.eq(
        "lower_is_better"
    )

    result["target_value"] = target
    result["actual_value"] = actual
    result["variance"] = actual - target

    result["favorable_variance"] = (
        result["variance"]
        .where(
            higher_is_better,
            -result["variance"],
        )
        .round(2)
    )

    attainment = pd.Series(
        0.0,
        index=result.index,
        dtype="float64",
    )

    # Higher-is-better KPIs with positive targets.
    higher_positive_target = (
        higher_is_better
        & target.gt(0)
    )

    attainment.loc[higher_positive_target] = (
        actual.loc[higher_positive_target]
        / target.loc[higher_positive_target]
        * 100
    )

    # Higher-is-better KPIs with a zero target.
    higher_zero_target = (
        higher_is_better
        & target.eq(0)
    )

    attainment.loc[
        higher_zero_target & actual.eq(0)
    ] = 100.0

    attainment.loc[
        higher_zero_target & actual.gt(0)
    ] = 150.0

    # Lower-is-better KPIs with positive targets and actuals.
    lower_positive_values = (
        lower_is_better
        & target.gt(0)
        & actual.gt(0)
    )

    attainment.loc[lower_positive_values] = (
        target.loc[lower_positive_values]
        / actual.loc[lower_positive_values]
        * 100
    )

    # A zero actual exceeds a positive lower-is-better target.
    attainment.loc[
        lower_is_better
        & target.gt(0)
        & actual.eq(0)
    ] = 150.0

    # A zero target and zero actual represent exact attainment.
    attainment.loc[
        lower_is_better
        & target.eq(0)
        & actual.eq(0)
    ] = 100.0

    # A zero target with a positive lower-is-better actual misses target.
    attainment.loc[
        lower_is_better
        & target.eq(0)
        & actual.gt(0)
    ] = 0.0

    result["attainment_pct"] = (
        attainment
        .clip(
            lower=0,
            upper=150,
        )
        .round(1)
    )

    result["target_met"] = (
        (
            higher_is_better
            & actual.ge(target)
        )
        |
        (
            lower_is_better
            & actual.le(target)
        )
    )

    result["performance_status"] = "Below Target"

    result.loc[
        result["attainment_pct"].ge(90)
        & ~result["target_met"],
        "performance_status",
    ] = "Near Target"

    result.loc[
        result["target_met"],
        "performance_status",
    ] = "Target Met"

    return result


def calculate_project_health(
    projects: pd.DataFrame,
    blockers: pd.DataFrame,
    enriched_kpis: pd.DataFrame,
    reporting_date: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Calculate project-level schedule, blocker, KPI, and risk health."""

    result = projects.copy()

    resolved_reporting_date = resolve_reporting_date(
        projects,
        blockers,
        reporting_date,
    )

    result["progress_pct"] = _to_numeric(
        result["progress_pct"],
        "projects.progress_pct",
    )

    result["due_date"] = pd.to_datetime(
        result["due_date"],
        errors="coerce",
    )

    if result["due_date"].isna().any():
        raise ValueError(
            "projects.due_date contains invalid date values."
        )

    result["days_to_due"] = (
        result["due_date"]
        - resolved_reporting_date
    ).dt.days

    result["is_overdue"] = (
        result["days_to_due"].lt(0)
        & result["status"].ne("Complete")
    )

    result["due_soon"] = (
        result["days_to_due"].between(
            0,
            14,
            inclusive="both",
        )
        & result["status"].ne("Complete")
    )

    open_blockers = blockers[
        blockers["status"].isin(
            ["Open", "Escalated"]
        )
    ].copy()

    open_blockers["severity_score"] = (
        open_blockers["severity"]
        .map(SEVERITY_WEIGHT)
        .fillna(0)
    )

    open_blockers["high_critical_flag"] = (
        open_blockers["severity"]
        .isin(["High", "Critical"])
        .astype(int)
    )

    blocker_summary = (
        open_blockers
        .groupby(
            "project_id",
            as_index=False,
        )
        .agg(
            open_blockers=(
                "blocker_id",
                "count",
            ),
            blocker_severity_score=(
                "severity_score",
                "sum",
            ),
            high_critical_blockers=(
                "high_critical_flag",
                "sum",
            ),
        )
    )

    kpi_working = enriched_kpis.copy()

    kpi_working["review_required_flag"] = (
        kpi_working["validation_status"]
        .astype("string")
        .str.strip()
        .eq("Review Required")
        .astype(int)
    )

    kpi_summary = (
        kpi_working
        .groupby(
            "project_id",
            as_index=False,
        )
        .agg(
            avg_attainment_pct=(
                "attainment_pct",
                "mean",
            ),
            kpis_met=(
                "target_met",
                "sum",
            ),
            total_kpis=(
                "kpi_id",
                "count",
            ),
            kpis_review_required=(
                "review_required_flag",
                "sum",
            ),
        )
    )

    result = result.merge(
        blocker_summary,
        on="project_id",
        how="left",
    )

    result = result.merge(
        kpi_summary,
        on="project_id",
        how="left",
    )

    numeric_fill_columns = [
        "open_blockers",
        "blocker_severity_score",
        "high_critical_blockers",
        "avg_attainment_pct",
        "kpis_met",
        "total_kpis",
        "kpis_review_required",
    ]

    result[numeric_fill_columns] = (
        result[numeric_fill_columns]
        .fillna(0)
    )

    result["avg_attainment_pct"] = (
        result["avg_attainment_pct"]
        .round(1)
    )

    status_score = (
        result["status"]
        .map(STATUS_WEIGHT)
        .fillna(1)
    )

    priority_score = (
        result["priority"]
        .map(PRIORITY_WEIGHT)
        .fillna(0)
    )

    overdue_score = (
        result["is_overdue"]
        .astype(int)
        * 3
    )

    low_progress_score = (
        (
            result["progress_pct"].lt(50)
            & result["status"].isin(
                ["At Risk", "Blocked"]
            )
        )
        .astype(int)
        * 2
    )

    kpi_risk_score = pd.Series(
        0,
        index=result.index,
        dtype="int64",
    )

    has_kpis = result["total_kpis"].gt(0)

    kpi_risk_score.loc[
        has_kpis
        & result["avg_attainment_pct"].lt(80)
    ] = 2

    kpi_risk_score.loc[
        has_kpis
        & result["avg_attainment_pct"].between(
            80,
            99.9,
            inclusive="both",
        )
    ] = 1

    validation_risk_score = (
        result["kpis_review_required"]
        .gt(0)
        .astype(int)
    )

    result["risk_score"] = (
        status_score
        + priority_score
        + result["blocker_severity_score"]
        + overdue_score
        + low_progress_score
        + kpi_risk_score
        + validation_risk_score
    ).astype(int)

    result["health"] = pd.cut(
        result["risk_score"],
        bins=[
            -1,
            2,
            6,
            float("inf"),
        ],
        labels=[
            "Healthy",
            "Watch",
            "Critical",
        ],
    ).astype("string")

    result["health_reason"] = result.apply(
        _build_health_reason,
        axis=1,
    )

    result["reporting_date"] = (
        resolved_reporting_date
        .date()
        .isoformat()
    )

    return result


def _build_health_reason(
    row: pd.Series,
) -> str:
    """Create a concise explanation of project health."""

    reasons: list[str] = []

    if row["status"] == "Blocked":
        reasons.append("Project is blocked")
    elif row["status"] == "At Risk":
        reasons.append("Project is marked at risk")

    if bool(row["is_overdue"]):
        reasons.append("Due date has passed")

    if row["high_critical_blockers"] > 0:
        reasons.append(
            "High or critical blocker is open"
        )
    elif row["open_blockers"] > 0:
        reasons.append("Open blocker requires attention")

    if (
        row["total_kpis"] > 0
        and row["avg_attainment_pct"] < 80
    ):
        reasons.append("KPI attainment is below 80%")
    elif (
        row["total_kpis"] > 0
        and row["avg_attainment_pct"] < 100
    ):
        reasons.append("One or more KPIs are below target")

    if row["kpis_review_required"] > 0:
        reasons.append(
            "KPI validation review is required"
        )

    if not reasons:
        return "No material risk indicators detected"

    return "; ".join(reasons)


def build_summary(
    projects: pd.DataFrame,
    blockers: pd.DataFrame,
    decisions: pd.DataFrame,
    enriched_kpis: pd.DataFrame,
    reporting_date: str | pd.Timestamp | None = None,
    project_health: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build the leadership KPI summary table."""

    resolved_reporting_date = resolve_reporting_date(
        projects,
        blockers,
        reporting_date,
    )

    active_projects = projects[
        projects["status"].ne("Complete")
    ]

    open_blockers = blockers[
        blockers["status"].isin(
            ["Open", "Escalated"]
        )
    ].copy()

    if open_blockers.empty:
        average_days_blocked = 0.0
    else:
        opened_dates = pd.to_datetime(
            open_blockers["opened_date"],
            errors="coerce",
        )

        valid_opened_dates = opened_dates.dropna()

        if valid_opened_dates.empty:
            average_days_blocked = 0.0
        else:
            days_blocked = (
                resolved_reporting_date
                - valid_opened_dates
            ).dt.days.clip(lower=0)

            average_days_blocked = round(
                float(days_blocked.mean()),
                1,
            )

    project_progress = _to_numeric(
        projects["progress_pct"],
        "projects.progress_pct",
    )

    total_kpis = len(enriched_kpis)

    if total_kpis:
        kpi_target_attainment_rate = round(
            float(
                enriched_kpis["target_met"]
                .mean()
                * 100
            ),
            1,
        )

        average_kpi_attainment = round(
            float(
                enriched_kpis["attainment_pct"]
                .mean()
            ),
            1,
        )
    else:
        kpi_target_attainment_rate = 0.0
        average_kpi_attainment = 0.0

    critical_health_projects = 0

    if project_health is not None:
        critical_health_projects = int(
            project_health["health"]
            .astype("string")
            .eq("Critical")
            .sum()
        )

    metrics: list[tuple[str, Any]] = [
        (
            "Projects tracked",
            int(len(projects)),
        ),
        (
            "Active projects",
            int(len(active_projects)),
        ),
        (
            "Projects on track",
            int(
                projects["status"]
                .eq("On Track")
                .sum()
            ),
        ),
        (
            "Projects at risk or blocked",
            int(
                projects["status"]
                .isin(["At Risk", "Blocked"])
                .sum()
            ),
        ),
        (
            "Critical-health projects",
            critical_health_projects,
        ),
        (
            "Average progress",
            round(
                float(project_progress.mean()),
                1,
            ),
        ),
        (
            "KPIs tracked",
            int(total_kpis),
        ),
        (
            "KPIs meeting target",
            int(
                enriched_kpis["target_met"]
                .sum()
            ),
        ),
        (
            "KPI target attainment rate",
            kpi_target_attainment_rate,
        ),
        (
            "Average KPI attainment",
            average_kpi_attainment,
        ),
        (
            "Open blockers",
            int(len(open_blockers)),
        ),
        (
            "High/Critical open blockers",
            int(
                open_blockers["severity"]
                .isin(["High", "Critical"])
                .sum()
            ),
        ),
        (
            "Pending decisions",
            int(
                decisions["status"]
                .eq("Pending")
                .sum()
            ),
        ),
        (
            "Average days blocked",
            average_days_blocked,
        ),
    ]

    return pd.DataFrame(
        metrics,
        columns=[
            "metric",
            "value",
        ],
    )


def run_pipeline(
    project_root: Path,
    reporting_date: str | pd.Timestamp | None = None,
) -> dict[str, pd.DataFrame]:
    """Run KPI calculations and write analytics outputs."""

    data = load_inputs(
        project_root / "data"
    )

    resolved_reporting_date = resolve_reporting_date(
        data["projects"],
        data["blockers"],
        reporting_date,
    )

    enriched_kpis = calculate_kpi_attainment(
        data["kpis"]
    )

    project_health = calculate_project_health(
        data["projects"],
        data["blockers"],
        enriched_kpis,
        resolved_reporting_date,
    )

    summary = build_summary(
        data["projects"],
        data["blockers"],
        data["decisions"],
        enriched_kpis,
        resolved_reporting_date,
        project_health,
    )

    output_dir = project_root / "outputs"

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    enriched_kpis.to_csv(
        output_dir / "enriched_kpis.csv",
        index=False,
    )

    project_health.to_csv(
        output_dir / "project_health.csv",
        index=False,
    )

    summary.to_csv(
        output_dir / "kpi_summary.csv",
        index=False,
    )

    metadata = {
        "reporting_date": (
            resolved_reporting_date
            .date()
            .isoformat()
        ),
        "input_row_counts": {
            label: int(len(frame))
            for label, frame in data.items()
        },
        "output_row_counts": {
            "enriched_kpis": int(
                len(enriched_kpis)
            ),
            "project_health": int(
                len(project_health)
            ),
            "kpi_summary": int(
                len(summary)
            ),
        },
    }

    (
        output_dir
        / "pipeline_metadata.json"
    ).write_text(
        json.dumps(
            metadata,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "summary": summary,
        "project_health": project_health,
        "enriched_kpis": enriched_kpis,
        **data,
    }


def main() -> None:
    """Run the KPI pipeline directly from the command line."""

    project_root = (
        Path(__file__)
        .resolve()
        .parents[1]
    )

    outputs = run_pipeline(
        project_root
    )

    print(
        outputs["summary"]
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
