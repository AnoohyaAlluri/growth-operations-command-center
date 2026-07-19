"""Run the complete synthetic Command Center pipeline."""

from pathlib import Path

from src.calculate_kpis import run_pipeline
from src.classify_risks import classify_risks
from src.generate_executive_summary import generate_summary
from src.validate_data import validate_data


def main() -> None:
    project_root = Path(__file__).resolve().parent

    validation = validate_data(project_root / "data")
    if validation["status"] != "PASS":
        raise SystemExit(f"Validation failed: {validation['errors']}")

    run_pipeline(project_root)
    classify_risks(project_root)

    summary = generate_summary(project_root)
    (project_root / "outputs" / "executive_summary.md").write_text(
        summary, encoding="utf-8"
    )

    print("Pipeline completed successfully.")
    print("Outputs written to the outputs/ folder.")


if __name__ == "__main__":
    main()
