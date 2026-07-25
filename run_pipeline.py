"""Run the complete synthetic Growth & Operations Command Center pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.calculate_kpis import run_pipeline as run_kpi_pipeline
from src.classify_risks import classify_risks
from src.generate_executive_summary import generate_summary
from src.validate_data import validate_data


def _write_json(
    output_path: Path,
    payload: dict[str, Any],
) -> None:
    """Write a dictionary to a formatted JSON file."""

    output_path.write_text(
        json.dumps(
            payload,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )


def main() -> None:
    """Validate data, run analytics, classify risks, and generate reporting."""

    project_root = Path(__file__).resolve().parent
    data_directory = project_root / "data"
    outputs_directory = project_root / "outputs"

    outputs_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("1. Validating synthetic source data...")

    validation_report = validate_data(
        data_directory
    )

    _write_json(
        outputs_directory / "validation_report.json",
        validation_report,
    )

    if validation_report.get("status") != "PASS":
        errors = validation_report.get(
            "errors",
            ["Unknown validation error"],
        )

        raise SystemExit(
            "Validation failed. "
            f"Review outputs/validation_report.json. Errors: {errors}"
        )

    print("   Validation passed.")

    print("2. Calculating KPIs and project health...")

    pipeline_outputs = run_kpi_pipeline(
        project_root
    )

    print("   KPI and project-health outputs created.")

    print("3. Building leadership risk register...")

    risk_register = classify_risks(
        project_root,
        pipeline_outputs,
    )

    print("   Risk register created.")

    print("4. Generating executive summary...")

    executive_summary = generate_summary(
        project_root,
        pipeline_outputs,
        risk_register,
    )

    executive_summary_path = (
        outputs_directory
        / "executive_summary.md"
    )

    executive_summary_path.write_text(
        executive_summary,
        encoding="utf-8",
    )

    run_manifest = {
        "pipeline_status": "SUCCESS",
        "validation_status": validation_report.get("status"),
        "validation_errors": validation_report.get(
            "error_count",
            0,
        ),
        "validation_warnings": validation_report.get(
            "warning_count",
            0,
        ),
        "projects_processed": int(
            len(pipeline_outputs["projects"])
        ),
        "kpis_processed": int(
            len(pipeline_outputs["enriched_kpis"])
        ),
        "risk_records_created": int(
            len(risk_register)
        ),
        "outputs_created": [
            "validation_report.json",
            "enriched_kpis.csv",
            "project_health.csv",
            "kpi_summary.csv",
            "pipeline_metadata.json",
            "risk_register.csv",
            "executive_summary.md",
            "run_manifest.json",
        ],
    }

    _write_json(
        outputs_directory / "run_manifest.json",
        run_manifest,
    )

    print("5. Pipeline completed successfully.")
    print(f"   Outputs directory: {outputs_directory}")
    print(f"   Executive summary: {executive_summary_path}")


if __name__ == "__main__":
    main()
