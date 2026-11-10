"""Automated tests for dynamic component database, provenance tracking, and CSV bulk operations."""

import pytest
from rotorlab.data.repository import RotorLabRepository
from rotorlab.models.domain import (
    BatterySpec,
    DataProvenance,
    ESCSpec,
    MotorSpec,
    PropellerSpec,
)


@pytest.fixture
def repo():
    return RotorLabRepository(":memory:")


def test_default_components_seeded(repo):
    motors = repo.list_components("motor")
    props = repo.list_components("propeller")
    escs = repo.list_components("esc")
    bats = repo.list_components("battery")

    assert len(motors) >= 4
    assert len(props) >= 4
    assert len(escs) >= 4
    assert len(bats) >= 4

    # Check manufacturer provenance preservation
    for m in motors:
        assert m["provenance"] == DataProvenance.MANUFACTURER_DATASHEET.value


def test_save_and_retrieve_custom_motor_with_provenance(repo):
    ms = MotorSpec(
        manufacturer="Sunnysky",
        model="V2216",
        kv_rating=800.0,
        max_continuous_current_a=18.0,
        max_continuous_power_w=240.0,
        mass_g=75.0,
    )
    cid = repo.save_component(
        component_type="motor",
        spec=ms,
        provenance=DataProvenance.USER_MEASURED,
        source_reference="RCBenchmark 1580 Dynamometer Test",
    )
    assert cid.startswith("cmp_motor_")

    retrieved = repo.get_component(cid)
    assert retrieved is not None
    assert retrieved["name"] == "Sunnysky V2216 (KV800)"
    assert retrieved["provenance"] == DataProvenance.USER_MEASURED.value
    assert retrieved["source_reference"] == "RCBenchmark 1580 Dynamometer Test"
    assert retrieved["spec"]["kv_rating"] == 800.0


def test_delete_component(repo):
    ms = MotorSpec(
        manufacturer="Generic",
        model="DisposableMotor",
        kv_rating=1000.0,
        max_continuous_current_a=10.0,
        max_continuous_power_w=100.0,
        mass_g=50.0,
    )
    cid = repo.save_component("motor", ms)
    assert repo.get_component(cid) is not None

    deleted = repo.delete_component(cid)
    assert deleted is True
    assert repo.get_component(cid) is None


def test_import_and_export_motor_csv(repo):
    csv_data = """manufacturer,model,kv_rating,max_continuous_current_a,max_continuous_power_w,internal_resistance_mohm,no_load_current_a,min_cells_s,max_cells_s,mass_g
KDE,KDE2315,885,25.0,450.0,45.0,0.7,3,6,85.0
TMotor,MN2212,920,15.0,220.0,90.0,0.5,3,4,55.0
"""
    imported_count = repo.import_components_csv(
        csv_text=csv_data,
        component_type="motor",
        provenance=DataProvenance.USER_MEASURED,
        source_reference="Bench Test Batch A",
    )
    assert imported_count == 2

    # Export CSV
    exported = repo.export_components_csv("motor")
    assert "KDE" in exported
    assert "TMotor" in exported
    assert "kv_rating" in exported
