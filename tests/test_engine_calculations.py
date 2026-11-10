"""Automated tests for thrust, hover equilibrium, electrical power, endurance, and compatibility."""

from __future__ import annotations

import dataclasses
import math
import pytest

from rotorlab.data.datasets import get_builtin_datasets, get_default_configurations
from rotorlab.engine.compatibility import evaluate_compatibility
from rotorlab.engine.electrical import (
    analyze_electrical_system,
    calculate_battery_energy_wh,
    calculate_electrical_power_w,
    calculate_endurance_minutes,
)
from rotorlab.engine.thrust import (
    analyze_thrust_and_twr,
    interpolate_at_throttle,
    solve_hover_motor_state,
)
from rotorlab.models.domain import DataProvenance, SeverityLevel
from rotorlab.models.units import STANDARD_GRAVITY_M_S2, gf_to_newtons


def test_core_electrical_equations_exact_values() -> None:
    # Battery energy: E (Wh) = V (V) * Capacity (Ah)
    # 14.8 V * 6.0 Ah = 88.8 Wh
    assert math.isclose(calculate_battery_energy_wh(14.8, 6.0), 88.8, rel_tol=1e-9)

    # Electrical power: P (W) = V (V) * I (A)
    # 22.2 V * 15.0 A = 333.0 W
    assert math.isclose(calculate_electrical_power_w(22.2, 15.0), 333.0, rel_tol=1e-9)
    assert math.isclose(calculate_electrical_power_w(22.2, 0.0), 0.0, rel_tol=1e-9)

    # Estimated endurance: Time (minutes) = (Usable capacity (Ah) / Average current (A)) * 60
    # Usable capacity = 4.8 Ah, Average current = 12.0 A -> (4.8 / 12.0) * 60 = 24.0 minutes
    assert math.isclose(calculate_endurance_minutes(4.8, 12.0), 24.0, rel_tol=1e-9)
    assert math.isclose(calculate_endurance_minutes(4.8, 0.0), 0.0, rel_tol=1e-9)

    with pytest.raises(ValueError):
        calculate_battery_energy_wh(0.0, 5.0)
    with pytest.raises(ValueError):
        calculate_electrical_power_w(14.8, -1.0)
    with pytest.raises(ValueError):
        calculate_endurance_minutes(5.0, -2.0)


def test_thrust_interpolation_and_extrapolation_warnings() -> None:
    datasets = {d.dataset_id: d for d in get_builtin_datasets()}
    ds = datasets["tmotor_mn3508_kv380_14x48_14v8"]
    cfg = get_default_configurations()[0]

    # Exact dataset point at 65% throttle -> 560 gf, 2.9 A, 42.92 W, 3500 RPM
    st_65 = interpolate_at_throttle(ds, cfg.propeller, 65.0)
    assert not st_65.is_extrapolated
    assert st_65.extrapolation_warning is None
    assert st_65.provenance == DataProvenance.MANUFACTURER_DATASHEET
    assert math.isclose(st_65.thrust_gf, 560.0, rel_tol=1e-6)
    assert math.isclose(st_65.current_a, 2.9, rel_tol=1e-6)

    # Midpoint interpolation between 65% (560 gf, 2.9 A) and 75% (700 gf, 4.0 A) -> 70% (630 gf, 3.45 A)
    st_70 = interpolate_at_throttle(ds, cfg.propeller, 70.0)
    assert not st_70.is_extrapolated
    assert math.isclose(st_70.thrust_gf, 630.0, rel_tol=1e-6)
    assert math.isclose(st_70.current_a, 3.45, rel_tol=1e-6)

    # Below minimum measured point (50%) -> triggers explicit boundary warning & CALCULATED_ESTIMATE provenance
    st_25 = interpolate_at_throttle(ds, cfg.propeller, 25.0, allow_extrapolation=False)
    assert st_25.is_extrapolated
    assert st_25.extrapolation_warning is not None
    assert st_25.provenance == DataProvenance.CALCULATED_ESTIMATE
    # Anchored to (0% -> 0 gf) and (50% -> 350 gf) -> 25% is 175 gf
    assert math.isclose(st_25.thrust_gf, 175.0, rel_tol=1e-6)

    # Explicit linear extrapolation mode
    st_40_ext = interpolate_at_throttle(ds, cfg.propeller, 40.0, allow_extrapolation=True)
    assert st_40_ext.is_extrapolated
    assert "Linearly extrapolated" in (st_40_ext.extrapolation_warning or "")


def test_thrust_and_twr_independent_verification() -> None:
    # Reference verification on Surveyor-X4 Endurance Quad (4 motors, 1.35 kg dry + 0.35 kg payload = 1.70 kg)
    # Dataset: T-Motor MN3508 KV380 | 14x4.8 CF @ 14.8V -> 100% thrust = 940 gf per motor
    datasets = {d.dataset_id: d for d in get_builtin_datasets()}
    ds = datasets["tmotor_mn3508_kv380_14x48_14v8"]
    cfg = get_default_configurations()[0]

    res = analyze_thrust_and_twr(cfg.airframe, cfg.propeller, ds, target_twr_for_payload_margin=2.0)

    expected_total_mass_kg = 1.70
    expected_weight_n = 1.70 * STANDARD_GRAVITY_M_S2  # 16.671305 N
    expected_max_thrust_gf = 4 * 940.0  # 3760 gf
    expected_max_thrust_n = gf_to_newtons(3760.0)  # 36.873004 N
    expected_twr = expected_max_thrust_n / expected_weight_n  # 3760 / 1700 = 2.2117647

    assert math.isclose(res.total_mass_kg, expected_total_mass_kg, rel_tol=1e-9)
    assert math.isclose(res.aircraft_weight_n, expected_weight_n, rel_tol=1e-9)
    assert math.isclose(res.max_total_thrust_gf, expected_max_thrust_gf, rel_tol=1e-9)
    assert math.isclose(res.max_total_thrust_n, expected_max_thrust_n, rel_tol=1e-9)
    assert math.isclose(res.twr_max, expected_twr, rel_tol=1e-6)
    assert res.hover_feasible
    assert res.hover_single_motor_state is not None
    # Required hover thrust per motor = 1700 gf / 4 = 425 gf (lies between 50% [350 gf] and 65% [560 gf])
    assert math.isclose(res.hover_required_per_motor_gf, 425.0, rel_tol=1e-6)
    expected_hover_th = 50.0 + (425.0 - 350.0) / (560.0 - 350.0) * (65.0 - 50.0)
    assert math.isclose(res.hover_single_motor_state.throttle_pct, expected_hover_th, rel_tol=1e-6)


def test_infeasible_hover_heavy_aircraft() -> None:
    datasets = {d.dataset_id: d for d in get_builtin_datasets()}
    ds = datasets["tmotor_mn3508_kv380_14x48_14v8"]
    cfg = get_default_configurations()[0]

    # Overload aircraft with 5.0 kg payload -> total mass 6.35 kg > 3.76 kg max static lift
    overloaded_airframe = dataclasses.replace(cfg.airframe, payload_mass_kg=5.0)
    overloaded_cfg = dataclasses.replace(cfg, airframe=overloaded_airframe)

    t_res = analyze_thrust_and_twr(overloaded_cfg.airframe, overloaded_cfg.propeller, ds)
    assert not t_res.hover_feasible
    assert t_res.hover_single_motor_state is None
    assert t_res.twr_max < 1.0

    e_res = analyze_electrical_system(overloaded_cfg.battery, overloaded_cfg.motor, overloaded_cfg.airframe, t_res)
    assert e_res.hover_state is None

    c_res = evaluate_compatibility(overloaded_cfg, ds, t_res, e_res)
    assert c_res.overall_status == SeverityLevel.CRITICAL
    twr_check = next(i for i in c_res.items if i.check_id == "TWR_HOVER_MARGIN")
    assert twr_check.severity == SeverityLevel.CRITICAL


def test_incompatible_components_detection() -> None:
    datasets = {d.dataset_id: d for d in get_builtin_datasets()}
    ds = datasets["tmotor_u3_kv700_12x4_14v8"]  # Peak current = 16.8 A per motor
    cfg = get_default_configurations()[1]

    # Create undersized ESC (12A continuous < 16.8A peak motor current),
    # mismatched cell count (6S battery on 3S-4S motor), and low C-rating battery (2C on 8Ah = 16A max)
    bad_esc = dataclasses.replace(cfg.esc, continuous_current_a=12.0, peak_current_a=15.0)
    bad_batt = dataclasses.replace(
        cfg.battery,
        cell_count_s=6,
        nominal_voltage_v=22.2,
        operating_voltage_v=22.2,
        continuous_c_rating=2.0,
        burst_c_rating=3.0,
    )
    bad_cfg = dataclasses.replace(cfg, esc=bad_esc, battery=bad_batt)

    t_res = analyze_thrust_and_twr(bad_cfg.airframe, bad_cfg.propeller, ds)
    e_res = analyze_electrical_system(bad_cfg.battery, bad_cfg.motor, bad_cfg.airframe, t_res)
    c_res = evaluate_compatibility(bad_cfg, ds, t_res, e_res)

    assert c_res.overall_status == SeverityLevel.CRITICAL
    by_id = {item.check_id: item for item in c_res.items}
    assert by_id["ESC_CURRENT_COMPAT"].severity == SeverityLevel.CRITICAL
    assert by_id["BATTERY_DISCHARGE_COMPAT"].severity == SeverityLevel.CRITICAL
    assert by_id["VOLTAGE_CELL_COMPAT"].severity == SeverityLevel.CRITICAL
    assert by_id["DATASET_MATCH_COMPAT"].severity == SeverityLevel.WARNING
