from pathlib import Path

from src.calculate_kpis import run_pipeline
from src.validate_data import validate_data


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_synthetic_data_passes_validation():
    report = validate_data(PROJECT_ROOT / "data")
    assert report["status"] == "PASS"
    assert report["error_count"] == 0


def test_expected_source_row_counts():
    outputs = run_pipeline(PROJECT_ROOT)
    assert len(outputs["projects"]) == 12
    assert len(outputs["kpis"]) == 24
    assert len(outputs["blockers"]) == 8
    assert len(outputs["decisions"]) == 8


def test_project_health_is_calculated():
    outputs = run_pipeline(PROJECT_ROOT)
    project_health = outputs["project_health"]
    assert project_health["risk_score"].notna().all()
    assert set(project_health["health"]).issubset({"Healthy", "Watch", "Critical"})


def test_kpi_attainment_is_bounded():
    outputs = run_pipeline(PROJECT_ROOT)
    attainment = outputs["enriched_kpis"]["attainment_pct"]
    assert attainment.between(0, 150).all()
