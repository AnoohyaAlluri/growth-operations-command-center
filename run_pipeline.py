"""Run the complete synthetic Growth & Operations Command Center pipeline."""

from pathlib import Path

from src.calculate_kpis import run_pipeline
from src.classify_risks import classify_risks
from src.generate_executive_summary import generate_summary
from src.validate_data import validate_data


def main() -> None:
    """Validate source data, run analytics, and generate project outputs."""

    project_root = Path(__file__).resolve().parent
    data_directory = project_root / "data"
    outputs_directory = project_root / "outputs"

    # Ensure the outputs directory exists.
    outputs_directory.mkdir(parents=True, exist_ok=True)

    # Validate the synthetic input datasets before processing.
    validation = validate_data(data_directory)

    if validation.get("status") != "PASS":
        errors = validation.get("errors", ["Unknown validation error"])
        raise SystemExit(f"Validation failed: {errors}")

    # Calculate project and KPI metrics.
    run_pipeline(project_root)

    # Classify operational risks and blockers.
    classify_risks(project_root)

    # Generate the leadership-ready executive summary.
    summary = generate_summary(project_root)

    executive_summary_path = outputs_directory / "executive_summary.md"
    executive_summary_path.write_text(summary, encoding="utf-8")

    print("Pipeline completed successfully.")
    print(f"Outputs written to: {outputs_directory}")
    print(f"Executive summary created at: {executive_summary_path}")


if __name__ == "__main__":
    main()
