"""Automated tests for SI unit conversions and domain model input validation."""

from __future__ import annotations

import math
import pytest

from rotorlab.models.domain import (
    AirframeSpec,
    BatterySpec,
    DataProvenance,
    EngineeringMargins,
    ESCSpec,
    MotorSpec,
    PerformanceDataset,
    PerformancePoint,
    PropellerSpec,
)
from rotorlab.models.units import (
    STANDARD_GRAVITY_M_S2,
    ah_to_mah,
    calculate_isa_air_density,
    calculate_rotor_disk_area_m2,
    calculate_tip_speed_m_s,
    gf_to_newtons,
    grams_to_kg,
    inches_to_meters,
    inches_to_mm,
    kg_to_grams,
    kg_to_lbs,
    kgf_to_newtons,
    lbf_to_newtons,
    lbs_to_kg,
    mah_to_ah,
    mass_kg_to_weight_n,
    meters_to_inches,
    mm_to_inches,
    newtons_to_gf,
    newtons_to_kgf,
    newtons_to_lbf,
    rad_s_to_rpm,
    rpm_to_rad_s,
)


def test_force_and_mass_conversions_roundtrip() -> None:
    # 1000 gf == 1 kgf == 9.80665 N
    assert math.isclose(gf_to_newtons(1000.0), STANDARD_GRAVITY_M_S2, rel_tol=1e-9)
    assert math.isclose(newtons_to_gf(STANDARD_GRAVITY_M_S2), 1000.0, rel_tol=1e-9)
    assert math.isclose(kgf_to_newtons(2.5), 2.5 * STANDARD_GRAVITY_M_S2, rel_tol=1e-9)
    assert math.isclose(newtons_to_kgf(2.5 * STANDARD_GRAVITY_M_S2), 2.5, rel_tol=1e-9)

    f_n = lbf_to_newtons(10.0)
    assert math.isclose(newtons_to_lbf(f_n), 10.0, rel_tol=1e-9)

    assert math.isclose(grams_to_kg(1500.0), 1.5, rel_tol=1e-9)
    assert math.isclose(kg_to_grams(1.5), 1500.0, rel_tol=1e-9)
    assert math.isclose(kg_to_lbs(lbs_to_kg(5.0)), 5.0, rel_tol=1e-9)
    assert math.isclose(mass_kg_to_weight_n(2.0), 2.0 * STANDARD_GRAVITY_M_S2, rel_tol=1e-9)


def test_length_and_electrical_conversions() -> None:
    assert math.isclose(inches_to_meters(10.0), 0.254, rel_tol=1e-9)
    assert math.isclose(meters_to_inches(0.254), 10.0, rel_tol=1e-9)
    assert math.isclose(inches_to_mm(1.0), 25.4, rel_tol=1e-9)
    assert math.isclose(mm_to_inches(25.4), 1.0, rel_tol=1e-9)

    assert math.isclose(mah_to_ah(6000.0), 6.0, rel_tol=1e-9)
    assert math.isclose(ah_to_mah(6.0), 6000.0, rel_tol=1e-9)

    assert math.isclose(rpm_to_rad_s(60.0), 2.0 * math.pi, rel_tol=1e-9)
    assert math.isclose(rad_s_to_rpm(2.0 * math.pi), 60.0, rel_tol=1e-9)


def test_rotor_disk_area_and_tip_speed() -> None:
    # 10 inch diameter -> 0.254 m diameter -> radius = 0.127 m
    expected_area = math.pi * (0.127 ** 2)
    assert math.isclose(calculate_rotor_disk_area_m2(10.0), expected_area, rel_tol=1e-9)

    # Tip speed at 6000 RPM (100 rev/s -> 200*pi rad/s) * 0.127 m
    expected_tip = (6000.0 * 2.0 * math.pi / 60.0) * 0.127
    assert math.isclose(calculate_tip_speed_m_s(10.0, 6000.0), expected_tip, rel_tol=1e-9)


def test_isa_air_density_sea_level_and_altitude() -> None:
    # Standard sea level density is ~1.225 kg/m^3
    rho_0 = calculate_isa_air_density(0.0, 0.0)
    assert math.isclose(rho_0, 1.2250, rel_tol=1e-3)

    # Higher altitude or higher temperature reduces air density
    rho_2000m = calculate_isa_air_density(2000.0, 0.0)
    rho_hot = calculate_isa_air_density(0.0, 20.0)
    assert rho_2000m < rho_0
    assert rho_hot < rho_0

    with pytest.raises(ValueError):
        calculate_isa_air_density(15000.0, 0.0)


def test_unit_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        mass_kg_to_weight_n(-1.0)
    with pytest.raises(ValueError):
        gf_to_newtons(100.0, g=0.0)
    with pytest.raises(ValueError):
        calculate_rotor_disk_area_m2(0.0)
    with pytest.raises(ValueError):
        calculate_tip_speed_m_s(12.0, -100.0)


def test_domain_models_validation_boundaries() -> None:
    # Motor validation
    with pytest.raises(ValueError):
        MotorSpec(manufacturer="", model="M1", kv_rating=400, max_continuous_current_a=20, max_continuous_power_w=300)
    with pytest.raises(ValueError):
        MotorSpec(manufacturer="T-Motor", model="M1", kv_rating=0, max_continuous_current_a=20, max_continuous_power_w=300)
    with pytest.raises(ValueError):
        MotorSpec(manufacturer="T-Motor", model="M1", kv_rating=-500, max_continuous_current_a=20, max_continuous_power_w=300)
    with pytest.raises(ValueError):
        MotorSpec(
            manufacturer="T-Motor",
            model="M1",
            kv_rating=400,
            max_continuous_current_a=20,
            max_continuous_power_w=300,
            min_cells_s=6,
            max_cells_s=4,
        )

    # Propeller validation
    with pytest.raises(ValueError):
        PropellerSpec(manufacturer="T-Motor", model="P1", diameter_in=0.0, pitch_in=4.5)
    with pytest.raises(ValueError):
        PropellerSpec(manufacturer="T-Motor", model="P1", diameter_in=14.0, pitch_in=-4.5)

    # ESC validation
    with pytest.raises(ValueError):
        ESCSpec(name="ESC", continuous_current_a=0.0, peak_current_a=30.0)
    with pytest.raises(ValueError):
        ESCSpec(name="ESC", continuous_current_a=40.0, peak_current_a=30.0)

    # Battery validation
    with pytest.raises(ValueError):
        BatterySpec(
            name="B1",
            cell_count_s=4,
            nominal_voltage_v=14.8,
            operating_voltage_v=0.0,
            capacity_mah=5000,
            continuous_c_rating=25,
        )
    with pytest.raises(ValueError):
        BatterySpec(
            name="B1",
            cell_count_s=4,
            nominal_voltage_v=14.8,
            operating_voltage_v=14.8,
            capacity_mah=5000,
            continuous_c_rating=25,
            usable_capacity_fraction=1.2,
        )

    # Airframe validation
    with pytest.raises(ValueError):
        AirframeSpec(frame_type="Quad", num_motors=0, aircraft_dry_mass_kg=1.5, payload_mass_kg=0.5)
    with pytest.raises(ValueError):
        AirframeSpec(frame_type="Quad", num_motors=4, aircraft_dry_mass_kg=0.0, payload_mass_kg=0.5)
    with pytest.raises(ValueError):
        AirframeSpec(frame_type="Quad", num_motors=4, aircraft_dry_mass_kg=1.5, payload_mass_kg=-0.1)

    # Dataset requires >= 2 unique points
    pt1 = PerformancePoint(throttle_pct=50, voltage_v=14.8, current_a=2.0, thrust_gf=400, power_w=29.6, rpm=3000)
    with pytest.raises(ValueError):
        PerformanceDataset(
            dataset_id="bad_ds",
            motor_manufacturer="M",
            motor_model="X",
            motor_kv=400,
            propeller_model="P",
            propeller_diameter_in=12,
            propeller_pitch_in=4,
            test_voltage_v=14.8,
            provenance=DataProvenance.USER_MEASURED,
            source_reference="Test",
            measurement_conditions="Bench",
            points=[pt1],
        )

    # Engineering margins validation
    with pytest.raises(ValueError):
        EngineeringMargins(esc_current_safety_factor=0.8)
