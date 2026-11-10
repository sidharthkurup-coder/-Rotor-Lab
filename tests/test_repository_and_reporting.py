"""Automated tests for SQLite configuration persistence, CSV parsing, comparison, and report generation."""

from __future__ import annotations

import pytest

from rotorlab.data.datasets import parse_csv_performance_dataset
from rotorlab.data.repository import RotorLabRepository
from rotorlab.models.domain import DataProvenance
from rotorlab.reporting.exporter import (
    generate_comparison_csv,
    generate_markdown_report,
    generate_pdf_report,
    generate_single_analysis_csv,
)
from rotorlab.services.analyzer import compare_configurations, evaluate_configuration
from rotorlab.ui.charts import (
    build_battery_utilisation_chart,
    build_configuration_comparison_chart,
    build_current_vs_throttle_chart,
    build_payload_tradeoff_chart,
    build_power_vs_throttle_chart,
    build_thrust_vs_throttle_chart,
)


def test_sqlite_repository_crud_and_duplication() -> None:
    repo = RotorLabRepository(":memory:")
    configs = repo.list_configurations()
    assert len(configs) == 4

    first = configs[0]
    fetched = repo.get_configuration(first.config_id)
    assert fetched is not None
    assert fetched.name == first.name

    # Duplicate configuration
    dup = repo.duplicate_configuration(first.config_id, new_name="Cloned Surveyor Quad")
    assert dup.config_id != first.config_id
    assert dup.name == "Cloned Surveyor Quad"
    assert len(repo.list_configurations()) == 5

    # Delete configuration
    deleted = repo.delete_configuration(dup.config_id)
    assert deleted is True
    assert repo.get_configuration(dup.config_id) is None
    assert len(repo.list_configurations()) == 4


def test_csv_dataset_import_and_persistence() -> None:
    repo = RotorLabRepository(":memory:")
    csv_sample = """# Comment header line
throttle_pct,voltage_v,current_a,thrust_gf,power_w,rpm
35,14.8,1.2,220,17.76,2500
55,14.8,2.8,460,41.44,3600
75,14.8,5.1,740,75.48,4700
100,14.8,8.4,1080,124.32,5800
"""
    ds = parse_csv_performance_dataset(
        csv_content=csv_sample,
        dataset_id="custom_test_ds",
        motor_manufacturer="SunnySky",
        motor_model="X3108S",
        motor_kv=720.0,
        propeller_model="APC 11x4.7",
        propeller_diameter_in=11.0,
        propeller_pitch_in=4.7,
        test_voltage_v=14.8,
        provenance=DataProvenance.USER_MEASURED,
        source_reference="Lab Dynamometer Run #12",
    )
    assert len(ds.points) == 4
    assert ds.min_throttle_pct == 35.0
    assert ds.max_throttle_pct == 100.0

    repo.save_custom_dataset(ds)
    loaded = repo.get_dataset("custom_test_ds")
    assert loaded is not None
    assert loaded.motor_manufacturer == "SunnySky"
    assert loaded.provenance == DataProvenance.USER_MEASURED

    # Missing required columns raises ValueError
    with pytest.raises(ValueError):
        parse_csv_performance_dataset(
            csv_content="throttle_pct,thrust_gf\n50,400\n100,800",
            dataset_id="bad_csv",
            motor_manufacturer="X",
            motor_model="Y",
            motor_kv=500,
            propeller_model="P",
            propeller_diameter_in=10,
            propeller_pitch_in=4.5,
            test_voltage_v=14.8,
        )


def test_end_to_end_analysis_comparison_and_reporting() -> None:
    repo = RotorLabRepository(":memory:")
    configs = repo.list_configurations()
    datasets = {d.dataset_id: d for d in repo.list_all_datasets()}

    analyses = [evaluate_configuration(c, datasets[c.dataset_id]) for c in configs]
    assert len(analyses) == 4

    # Check comparison rows
    cmp_rows = compare_configurations(analyses)
    assert len(cmp_rows) == 4
    cmp_csv = generate_comparison_csv(cmp_rows)
    assert "Surveyor-X4 Endurance Quad" in cmp_csv
    assert "Atlas-X6 Heavy-Lift Hexa" in cmp_csv

    # Check single configuration reports (Markdown, PDF, CSV)
    primary = analyses[0]
    md_report = generate_markdown_report(primary)
    assert "ROTORLAB 1.0" in md_report
    assert "Manufacturer Measurements" in md_report

    curve_csv = generate_single_analysis_csv(primary)
    assert "single_motor_thrust_gf" in curve_csv

    pdf_bytes = generate_pdf_report(primary)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000

    # Verify all Plotly engineering charts construct valid figures with traces and axis labels
    fig_thrust = build_thrust_vs_throttle_chart(primary)
    fig_current = build_current_vs_throttle_chart(primary)
    fig_power = build_power_vs_throttle_chart(primary)
    fig_batt = build_battery_utilisation_chart(primary)
    fig_payload = build_payload_tradeoff_chart(primary)
    fig_cmp = build_configuration_comparison_chart(cmp_rows)

    for fig in [fig_thrust, fig_current, fig_power, fig_batt, fig_payload, fig_cmp]:
        assert len(fig.data) >= 2
        assert fig.layout.title.text is not None
        assert "Source:" in fig.layout.title.text or "Provenance:" in fig.layout.title.text


def test_streamlit_workstation_apptest_smoke() -> None:
    from pathlib import Path
    from streamlit.testing.v1 import AppTest

    app_path = Path(__file__).resolve().parent.parent / "app.py"
    at = AppTest.from_file(str(app_path), default_timeout=30).run()
    assert not at.exception
    assert len(at.tabs) == 5
    # Verify interactive throttle slider and configuration switcher work without exceptions
    if at.slider:
        at.slider[0].set_value(75.0).run()
        assert not at.exception
