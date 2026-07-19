"""Create a leadership-facing risk register from project and blocker data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.calculate_kpis import run_pipeline


def classify_risks(project_root: Path) -> pd.DataFrame:
    outputs = run_pipeline(project_root)
    health = outputs["project_health"].copy()
    blockers = outputs["blockers"].copy()

    open_blockers = blockers[blockers["status"].isin(["Open", "Escalated"])].copy()
    blocker_details = (
        open_blockers.groupby("project_id")
        .agg(
            blocker_titles=("blocker_title", lambda values: " | ".join(values)),
            highest_severity=("severity", lambda values: max(
                values,
                key={"Low": 1, "Medium": 2, "High": 3, "Critical": 4}.get,
            )),
        )
        .reset_index()
    )

    risk_register = health[
        [
            "project_id",
            "project_name",
            "owner",
            "priority",
            "status",
            "progress_pct",
            "days_to_due",
            "open_blockers",
            "risk_score",
            "health",
        ]
    ].merge(blocker_details, on="project_id", how="left")

    risk_register["highest_severity"] = risk_register["highest_severity"].fillna("None")
    risk_register["blocker_titles"] = risk_register["blocker_titles"].fillna("No open blockers")
    risk_register = risk_register.sort_values(
        ["risk_score", "priority"], ascending=[False, True]
    )

    output_dir = project_root / "outputs"
    output_dir.mkdir(exist_ok=True)
    risk_register.to_csv(output_dir / "risk_register.csv", index=False)
    return risk_register


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    risk_register = classify_risks(project_root)
    print(risk_register.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
