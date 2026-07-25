"""Generate a leadership-ready weekly executive summary."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from src.calculate_kpis import run_pipeline
from src.classify_risks import classify_risks


REQUIRED_SUMMARY_COLUMNS = {
    "metric",
    "value",
}

REQUIRED_PROJECT_COLUMNS = {
    "project_id",
    "project_name",
}

REQUIRED_DECISION_COLUMNS = {
    "decision_id",
    "project_id",
    "decision_title",
    "decision_owner",
    "status",
    "follow_up_action",
}

REQUIRED_UPDATE_COLUMNS = {
    "update_id",
    "project_id",
    "week_start",
    "accomplishment",
    "next_priority",
}

REQUIRED_RISK_COLUMNS = {
    "project_id",
    "project_name",
    "status",
    "priority",
    "risk_score",
    "health",
    "health_reason",
    "leadership_action",
    "blocker_titles",
    "highest_severity",
    "days_to_due",
    "reporting_date",
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


def metric_value(
    summary: pd.DataFrame,
    metric: str,
    default: Any = "N/A",
) -> Any:
    """Return a metric value from the KPI summary table."""

    row = summary.loc[
        summary["metric"].eq(metric),
        "value",
    ]

    if row.empty:
        return default

    value = row.iloc[0]

    if pd.isna(value):
        return default

    return value


def _format_number(
    value: Any,
    decimals: int = 1,
) -> str:
    """Format numeric values for executive reporting."""

    if value == "N/A" or pd.isna(value):
        return "N/A"

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return str(value)

    if numeric_value.is_integer():
        return f"{int(numeric_value):,}"

    return f"{numeric_value:,.{decimals}f}"


def _format_percentage(
    value: Any,
) -> str:
    """Format a value as a percentage."""

    formatted = _format_number(
        value,
        decimals=1,
    )

    if formatted == "N/A":
        return formatted

    return f"{formatted}%"


def _load_weekly_updates(
    project_root: Path,
    projects: pd.DataFrame,
) -> pd.DataFrame:
    """Load, validate, and enrich weekly operational updates."""

    updates_path = (
        project_root
        / "data"
        / "synthetic_weekly_updates.csv"
    )

    if not updates_path.exists():
        raise FileNotFoundError(
            f"Weekly update file is missing: {updates_path}"
        )

    try:
        updates = pd.read_csv(
            updates_path
        )
    except Exception as exc:
        raise ValueError(
            f"Unable to read {updates_path}: {exc}"
        ) from exc

    _validate_columns(
        updates,
        REQUIRED_UPDATE_COLUMNS,
        "weekly_updates",
    )

    updates["week_start"] = pd.to_datetime(
        updates["week_start"],
        errors="coerce",
    )

    if updates["week_start"].isna().any():
        raise ValueError(
            "weekly_updates: invalid week_start values detected."
        )

    project_lookup = projects[
        [
            "project_id",
            "project_name",
        ]
    ].drop_duplicates(
        subset=["project_id"]
    )

    updates = updates.merge(
        project_lookup,
        on="project_id",
        how="left",
        validate="many_to_one",
    )

    missing_project_names = (
        updates["project_name"]
        .isna()
    )

    if missing_project_names.any():
        missing_ids = sorted(
            updates.loc[
                missing_project_names,
                "project_id",
            ]
            .astype(str)
            .unique()
            .tolist()
        )

        raise ValueError(
            "weekly_updates: project names could not be resolved "
            f"for project_id values: {missing_ids}"
        )

    return updates.sort_values(
        by=[
            "week_start",
            "project_name",
        ],
        ascending=[
            False,
            True,
        ],
    ).reset_index(drop=True)


def _select_current_updates(
    updates: pd.DataFrame,
    maximum_rows: int = 5,
) -> tuple[pd.DataFrame, pd.Timestamp | None]:
    """Select updates from the most recent reporting week."""

    if updates.empty:
        return updates.copy(), None

    latest_week = pd.Timestamp(
        updates["week_start"].max()
    ).normalize()

    current_updates = updates[
        updates["week_start"].eq(
            latest_week
        )
    ].copy()

    current_updates = (
        current_updates
        .drop_duplicates(
            subset=[
                "project_id",
                "accomplishment",
                "next_priority",
            ]
        )
        .head(maximum_rows)
    )

    return (
        current_updates,
        latest_week,
    )


def _resolve_reporting_date(
    risk_register: pd.DataFrame,
    latest_update_week: pd.Timestamp | None,
) -> str:
    """Resolve the reporting date for the executive summary."""

    reporting_dates = pd.to_datetime(
        risk_register["reporting_date"],
        errors="coerce",
    ).dropna()

    if not reporting_dates.empty:
        return (
            pd.Timestamp(
                reporting_dates.max()
            )
            .date()
            .isoformat()
        )

    if latest_update_week is not None:
        return (
            latest_update_week
            .date()
            .isoformat()
        )

    return (
        pd.Timestamp.today()
        .normalize()
        .date()
        .isoformat()
    )


def _append_portfolio_snapshot(
    lines: list[str],
    summary: pd.DataFrame,
) -> None:
    """Add executive KPI metrics to the summary."""

    snapshot_metrics = [
        (
            "Projects tracked",
            _format_number(
                metric_value(
                    summary,
                    "Projects tracked",
                )
            ),
        ),
        (
            "Active projects",
            _format_number(
                metric_value(
                    summary,
                    "Active projects",
                )
            ),
        ),
        (
            "Projects on track",
            _format_number(
                metric_value(
                    summary,
                    "Projects on track",
                )
            ),
        ),
        (
            "Projects at risk or blocked",
            _format_number(
                metric_value(
                    summary,
                    "Projects at risk or blocked",
                )
            ),
        ),
        (
            "Critical-health projects",
            _format_number(
                metric_value(
                    summary,
                    "Critical-health projects",
                )
            ),
        ),
        (
            "Average project progress",
            _format_percentage(
                metric_value(
                    summary,
                    "Average progress",
                )
            ),
        ),
        (
            "KPI target attainment rate",
            _format_percentage(
                metric_value(
                    summary,
                    "KPI target attainment rate",
                )
            ),
        ),
        (
            "Average KPI attainment",
            _format_percentage(
                metric_value(
                    summary,
                    "Average KPI attainment",
                )
            ),
        ),
        (
            "Open blockers",
            _format_number(
                metric_value(
                    summary,
                    "Open blockers",
                )
            ),
        ),
        (
            "High/Critical open blockers",
            _format_number(
                metric_value(
                    summary,
                    "High/Critical open blockers",
                )
            ),
        ),
        (
            "Pending decisions",
            _format_number(
                metric_value(
                    summary,
                    "Pending decisions",
                )
            ),
        ),
        (
            "Average days blocked",
            _format_number(
                metric_value(
                    summary,
                    "Average days blocked",
                )
            ),
        ),
    ]

    for label, value in snapshot_metrics:
        lines.append(
            f"- **{label}:** {value}"
        )


def _append_accomplishments(
    lines: list[str],
    updates: pd.DataFrame,
) -> None:
    """Add recent project accomplishments."""

    lines.extend(
        [
            "",
            "## Key Accomplishments",
            "",
        ]
    )

    if updates.empty:
        lines.append(
            "- No weekly accomplishment records are available."
        )
        return

    for _, row in updates.iterrows():
        accomplishment = str(
            row["accomplishment"]
        ).strip()

        lines.append(
            f"- **{row['project_name']}:** "
            f"{accomplishment}"
        )


def _append_priority_risks(
    lines: list[str],
    risk_register: pd.DataFrame,
) -> None:
    """Add critical or watch-level operational risks."""

    lines.extend(
        [
            "",
            "## Priority Risks",
            "",
        ]
    )

    priority_risks = risk_register[
        risk_register["health"].isin(
            [
                "Critical",
                "Watch",
            ]
        )
    ].head(5)

    if priority_risks.empty:
        lines.append(
            "- No material project risks are currently classified "
            "as Critical or Watch."
        )
        return

    for _, row in priority_risks.iterrows():
        blocker_text = str(
            row["blocker_titles"]
        ).strip()

        if blocker_text == "No open blockers":
            blocker_clause = "no open blockers"
        else:
            blocker_clause = (
                f"blockers: {blocker_text}"
            )

        lines.append(
            f"- **{row['project_name']}** "
            f"({row['health']}, risk score {row['risk_score']}) "
            f"— {row['health_reason']}; {blocker_clause}. "
            f"**Leadership action:** {row['leadership_action']}."
        )


def _append_decisions(
    lines: list[str],
    decisions: pd.DataFrame,
    projects: pd.DataFrame,
) -> None:
    """Add pending decisions requiring leadership attention."""

    lines.extend(
        [
            "",
            "## Decisions Required",
            "",
        ]
    )

    project_lookup = projects[
        [
            "project_id",
            "project_name",
        ]
    ].drop_duplicates(
        subset=["project_id"]
    )

    pending_decisions = decisions[
        decisions["status"].eq(
            "Pending"
        )
    ].copy()

    pending_decisions = pending_decisions.merge(
        project_lookup,
        on="project_id",
        how="left",
        validate="many_to_one",
    )

    pending_decisions["project_name"] = (
        pending_decisions["project_name"]
        .fillna("Unassigned Project")
    )

    pending_decisions = (
        pending_decisions
        .sort_values(
            by=[
                "project_name",
                "decision_title",
            ]
        )
        .head(5)
    )

    if pending_decisions.empty:
        lines.append(
            "- No pending leadership decisions."
        )
        return

    for _, row in pending_decisions.iterrows():
        lines.append(
            f"- **{row['decision_title']}** "
            f"for **{row['project_name']}** "
            f"— owner: {row['decision_owner']}; "
            f"next action: {row['follow_up_action']}."
        )


def _append_next_priorities(
    lines: list[str],
    updates: pd.DataFrame,
) -> None:
    """Add the next operating priorities."""

    lines.extend(
        [
            "",
            "## Next Priorities",
            "",
        ]
    )

    if updates.empty:
        lines.append(
            "- No next-priority records are available."
        )
        return

    for _, row in updates.iterrows():
        next_priority = str(
            row["next_priority"]
        ).strip()

        lines.append(
            f"- **{row['project_name']}:** "
            f"{next_priority}"
        )


def generate_summary(
    project_root: Path,
    pipeline_outputs: Mapping[str, pd.DataFrame] | None = None,
    risk_register: pd.DataFrame | None = None,
) -> str:
    """
    Generate a leadership-ready executive summary.

    Existing pipeline outputs and a risk register may be supplied
    to prevent the analytics pipeline from being executed repeatedly.
    """

    outputs = (
        dict(pipeline_outputs)
        if pipeline_outputs is not None
        else run_pipeline(project_root)
    )

    required_output_keys = {
        "summary",
        "projects",
        "decisions",
    }

    missing_output_keys = sorted(
        required_output_keys
        - set(outputs.keys())
    )

    if missing_output_keys:
        raise KeyError(
            "Pipeline outputs are missing required dataset(s): "
            f"{missing_output_keys}"
        )

    summary = outputs["summary"].copy()
    projects = outputs["projects"].copy()
    decisions = outputs["decisions"].copy()

    _validate_columns(
        summary,
        REQUIRED_SUMMARY_COLUMNS,
        "summary",
    )

    _validate_columns(
        projects,
        REQUIRED_PROJECT_COLUMNS,
        "projects",
    )

    _validate_columns(
        decisions,
        REQUIRED_DECISION_COLUMNS,
        "decisions",
    )

    resolved_risk_register = (
        risk_register.copy()
        if risk_register is not None
        else classify_risks(
            project_root,
            outputs,
        )
    )

    _validate_columns(
        resolved_risk_register,
        REQUIRED_RISK_COLUMNS,
        "risk_register",
    )

    updates = _load_weekly_updates(
        project_root,
        projects,
    )

    current_updates, latest_update_week = (
        _select_current_updates(
            updates
        )
    )

    reporting_date = _resolve_reporting_date(
        resolved_risk_register,
        latest_update_week,
    )

    lines = [
        "# Weekly Executive Summary",
        "",
        f"**Reporting date:** {reporting_date}",
        "",
        (
            "> Synthetic portfolio output generated from the "
            "public-safe Growth & Operations Command Center dataset."
        ),
        "",
        "## Portfolio Snapshot",
        "",
    ]

    _append_portfolio_snapshot(
        lines,
        summary,
    )

    _append_accomplishments(
        lines,
        current_updates,
    )

    _append_priority_risks(
        lines,
        resolved_risk_register,
    )

    _append_decisions(
        lines,
        decisions,
        projects,
    )

    _append_next_priorities(
        lines,
        current_updates,
    )

    lines.extend(
        [
            "",
            "## Data and Governance Notes",
            "",
            (
                "- The summary is generated from synthetic project, KPI, "
                "blocker, decision, and weekly-update records."
            ),
            (
                "- Risk classifications are based on project status, "
                "priority, schedule, blocker severity, KPI attainment, "
                "and validation status."
            ),
            (
                "- No confidential company, employee, client, tenant, "
                "owner, address, email, phone, or financial information "
                "is included."
            ),
            "",
            "---",
            "",
            (
                "*Generated automatically by the Growth & Operations "
                "Command Center.*"
            ),
        ]
    )

    return "\n".join(lines)


def main() -> None:
    """Generate and save the executive summary."""

    project_root = (
        Path(__file__)
        .resolve()
        .parents[1]
    )

    outputs = run_pipeline(
        project_root
    )

    risk_register = classify_risks(
        project_root,
        outputs,
    )

    text = generate_summary(
        project_root,
        outputs,
        risk_register,
    )

    output_dir = (
        project_root
        / "outputs"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        output_dir
        / "executive_summary.md"
    )

    output_path.write_text(
        text,
        encoding="utf-8",
    )

    print(text)


if __name__ == "__main__":
    main()
