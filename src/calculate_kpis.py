"""KPI and project-health calculations for the synthetic Command Center."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd

REPORTING_DATE = pd.Timestamp("2026-07-18")
PRIORITY_WEIGHT = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}
SEVERITY_WEIGHT = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}


def load_inputs(data_dir: Path) -> Dict[str, pd.DataFrame]:
    return {
        "projects": pd.read_csv(data_dir / "synthetic_projects.csv"),
        "kpis": pd.read_csv(data_dir / "synthetic_kpis.csv"),
        "blockers": pd.read_csv(data_dir / "synthetic_blockers.csv"),
        "decisions": pd.read_csv(data_dir / "synthetic_decisions.csv"),
    }


def calculate_kpi_attainment(kpis: pd.DataFrame) -> pd.DataFrame:
    result = kpis.copy()
    target = pd.to_numeric(result["target_value"])
    actual = pd.to_numeric(result["actual_value"])

    result["variance"] = actual - target
    higher = result["direction"].eq("higher_is_better")

    result["favorable_variance"] = result["variance"].where(higher, -result["variance"])
    result["attainment_pct"] = 0.0

    nonzero_target = target.ne(0)
    result.loc[higher & nonzero_target, "attainment_pct"] = (
        actual[higher & nonzero_target] / target[higher & nonzero_target] * 100
    )
    result.loc[~higher & actual.ne(0), "attainment_pct"] = (
        target[~higher & actual.ne(0)] / actual[~higher & actual.ne(0)] * 100
    )
    result.loc[~higher & actual.eq(0), "attainment_pct"] = 150.0

    result["attainment_pct"] = result["attainment_pct"].clip(lower=0, upper=150).round(1)
    result["target_met"] = result["favorable_variance"] >= 0
    return result


def calculate_project_health(
    projects: pd.DataFrame,
    blockers: pd.DataFrame,
    enriched_kpis: pd.DataFrame,
) -> pd.DataFrame:
    result = projects.copy()
    result["due_date"] = pd.to_datetime(result["due_date"])
    result["days_to_due"] = (result["due_date"] - REPORTING_DATE).dt.days

    open_blockers = blockers[blockers["status"].isin(["Open", "Escalated"])].copy()
    open_blockers["severity_score"] = open_blockers["severity"].map(SEVERITY_WEIGHT).fillna(0)

    blocker_summary = (
        open_blockers.groupby("project_id")
        .agg(open_blockers=("blocker_id", "count"), blocker_severity_score=("severity_score", "sum"))
        .reset_index()
    )

    kpi_summary = (
        enriched_kpis.groupby("project_id")
        .agg(
            avg_attainment_pct=("attainment_pct", "mean"),
            kpis_met=("target_met", "sum"),
            total_kpis=("kpi_id", "count"),
        )
        .reset_index()
    )

    result = result.merge(blocker_summary, on="project_id", how="left")
    result = result.merge(kpi_summary, on="project_id", how="left")
    result[["open_blockers", "blocker_severity_score"]] = (
        result[["open_blockers", "blocker_severity_score"]].fillna(0)
    )

    status_score = result["status"].map(
        {"Complete": 0, "On Track": 0, "Planning": 1, "At Risk": 3, "Blocked": 5}
    ).fillna(1)
    priority_score = result["priority"].map(PRIORITY_WEIGHT).fillna(0)
    overdue_score = ((result["days_to_due"] < 0) & (result["status"] != "Complete")).astype(int) * 3
    low_progress_score = (
        (pd.to_numeric(result["progress_pct"]) < 50)
        & result["status"].isin(["At Risk", "Blocked"])
    ).astype(int) * 2

    result["risk_score"] = (
        status_score
        + priority_score
        + result["blocker_severity_score"]
        + overdue_score
        + low_progress_score
    )

    result["health"] = pd.cut(
        result["risk_score"],
        bins=[-1, 2, 6, float("inf")],
        labels=["Healthy", "Watch", "Critical"],
    ).astype(str)

    return result


def build_summary(
    projects: pd.DataFrame,
    blockers: pd.DataFrame,
    decisions: pd.DataFrame,
    enriched_kpis: pd.DataFrame,
) -> pd.DataFrame:
    active = projects[projects["status"] != "Complete"]
    open_blockers = blockers[blockers["status"].isin(["Open", "Escalated"])]

    opened = pd.to_datetime(open_blockers["opened_date"])
    avg_days_blocked = (
        (REPORTING_DATE - opened).dt.days.mean() if not open_blockers.empty else 0
    )

    metrics = [
        ("Projects tracked", len(projects)),
        ("Active projects", len(active)),
        ("Projects on track", int((projects["status"] == "On Track").sum())),
        ("Projects at risk or blocked", int(projects["status"].isin(["At Risk", "Blocked"]).sum())),
        ("Average progress", round(pd.to_numeric(projects["progress_pct"]).mean(), 1)),
        ("KPIs tracked", len(enriched_kpis)),
        ("KPIs meeting target", int(enriched_kpis["target_met"].sum())),
        ("KPI target attainment rate", round(enriched_kpis["target_met"].mean() * 100, 1)),
        ("Open blockers", len(open_blockers)),
        ("High/Critical open blockers", int(open_blockers["severity"].isin(["High", "Critical"]).sum())),
        ("Pending decisions", int((decisions["status"] == "Pending").sum())),
        ("Average days blocked", round(float(avg_days_blocked), 1)),
    ]
    return pd.DataFrame(metrics, columns=["metric", "value"])


def run_pipeline(project_root: Path) -> Dict[str, pd.DataFrame]:
    data = load_inputs(project_root / "data")
    enriched_kpis = calculate_kpi_attainment(data["kpis"])
    project_health = calculate_project_health(data["projects"], data["blockers"], enriched_kpis)
    summary = build_summary(data["projects"], data["blockers"], data["decisions"], enriched_kpis)

    output_dir = project_root / "outputs"
    output_dir.mkdir(exist_ok=True)

    enriched_kpis.to_csv(output_dir / "enriched_kpis.csv", index=False)
    project_health.to_csv(output_dir / "project_health.csv", index=False)
    summary.to_csv(output_dir / "kpi_summary.csv", index=False)

    return {
        "summary": summary,
        "project_health": project_health,
        "enriched_kpis": enriched_kpis,
        **data,
    }


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    outputs = run_pipeline(project_root)
    print(outputs["summary"].to_string(index=False))


if __name__ == "__main__":
    main()
