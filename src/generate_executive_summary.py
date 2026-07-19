"""Generate a leadership-ready weekly executive summary."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.calculate_kpis import run_pipeline
from src.classify_risks import classify_risks


def metric_value(summary: pd.DataFrame, metric: str):
    row = summary.loc[summary["metric"] == metric, "value"]
    return row.iloc[0] if not row.empty else "N/A"


def generate_summary(project_root: Path) -> str:
    outputs = run_pipeline(project_root)
    risk_register = classify_risks(project_root)

    summary = outputs["summary"]
    decisions = outputs["decisions"]
    updates = pd.read_csv(project_root / "data" / "synthetic_weekly_updates.csv")
    projects = outputs["projects"][["project_id", "project_name"]]
    updates = updates.merge(projects, on="project_id", how="left")

    critical = risk_register[risk_register["health"] == "Critical"].head(3)
    pending_decisions = decisions[decisions["status"] == "Pending"].head(5)

    lines = [
        "# Weekly Executive Summary",
        "",
        "> Synthetic portfolio output generated from the public-safe Command Center dataset.",
        "",
        "## Portfolio Snapshot",
        "",
        f"- **Projects tracked:** {metric_value(summary, 'Projects tracked')}",
        f"- **Active projects:** {metric_value(summary, 'Active projects')}",
        f"- **Projects on track:** {metric_value(summary, 'Projects on track')}",
        f"- **Projects at risk or blocked:** {metric_value(summary, 'Projects at risk or blocked')}",
        f"- **KPI target attainment rate:** {metric_value(summary, 'KPI target attainment rate')}%",
        f"- **Open blockers:** {metric_value(summary, 'Open blockers')}",
        f"- **Pending decisions:** {metric_value(summary, 'Pending decisions')}",
        "",
        "## Key Accomplishments",
        "",
    ]

    for _, row in updates.head(5).iterrows():
        lines.append(f"- **{row['project_name']}:** {row['accomplishment']}")

    lines.extend(["", "## Critical Risks", ""])
    if critical.empty:
        lines.append("- No projects are currently classified as critical.")
    else:
        for _, row in critical.iterrows():
            lines.append(
                f"- **{row['project_name']}** — {row['status']}; "
                f"risk score {row['risk_score']}; blockers: {row['blocker_titles']}."
            )

    lines.extend(["", "## Decisions Required", ""])
    if pending_decisions.empty:
        lines.append("- No pending decisions.")
    else:
        for _, row in pending_decisions.iterrows():
            lines.append(
                f"- **{row['decision_title']}** — owner: {row['decision_owner']}; "
                f"next action: {row['follow_up_action']}"
            )

    lines.extend(["", "## Next Priorities", ""])
    for _, row in updates.head(5).iterrows():
        lines.append(f"- **{row['project_name']}:** {row['next_priority']}")

    lines.extend(
        [
            "",
            "---",
            "",
            "*Generated from synthetic data. No confidential company or customer information is included.*",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    text = generate_summary(project_root)
    output_dir = project_root / "outputs"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "executive_summary.md"
    output_path.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
