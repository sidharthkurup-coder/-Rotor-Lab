"""Automated tests for RotorLab AI Copilot deterministic engineering tools."""

import pytest
from rotorlab.ai import tools
from rotorlab.data.repository import RotorLabRepository


@pytest.fixture(autouse=True)
def fresh_db():
    repo = RotorLabRepository(":memory:")
    # Ensure tool execution logger is cleared
    tools.get_tool_logger().clear()
    return repo


def test_run_propulsion_analysis_returns_verified_metrics():
    res = tools.run_propulsion_analysis("cfg_endurance_quad_4s")
    assert res["status"] == "success"
    assert res["config_name"] == "Surveyor-X4 Endurance Quad (4S 14in)"
    assert res["thrust_to_weight_ratio"] > 1.8
    assert 40.0 <= res["hover_throttle_pct"] <= 70.0
    assert res["hover_flight_time_minutes"] > 20.0
    assert "data_provenance" in res
    assert res["data_provenance"] == "Manufacturer Measurements"


def test_calculate_thrust_to_weight_with_custom_payload():
    # Baseline
    base = tools.calculate_thrust_to_weight("cfg_heavylift_hexa_6s")
    assert base["status"] == "success"
    base_twr = base["thrust_to_weight_ratio"]

    # Increased payload reduces TWR
    loaded = tools.calculate_thrust_to_weight("cfg_heavylift_hexa_6s", custom_payload_kg=10.0)
    assert loaded["status"] == "success"
    assert loaded["thrust_to_weight_ratio"] < base_twr
    assert loaded["total_mass_kg"] > base["total_mass_kg"]


def test_calculate_hover_throttle():
    res = tools.calculate_hover_throttle("cfg_industrial_u3_quad_4s")
    assert res["status"] == "success"
    assert res["hover_feasible"] is True
    assert 40.0 <= res["hover_throttle_pct"] <= 65.0
    assert res["hover_required_thrust_per_motor_gf"] > 0


def test_calculate_battery_endurance_reserve_scaling():
    res_20 = tools.calculate_battery_endurance("cfg_endurance_quad_4s", reserve_percentage=20.0)
    res_40 = tools.calculate_battery_endurance("cfg_endurance_quad_4s", reserve_percentage=40.0)
    assert res_20["status"] == "success"
    assert res_40["status"] == "success"
    # Higher reserve means less usable flight time
    assert res_20["hover_endurance_minutes"] > res_40["hover_endurance_minutes"]


def test_check_component_compatibility():
    res = tools.check_component_compatibility("cfg_endurance_quad_4s")
    assert res["status"] == "success"
    assert res["overall_status"] in ("PASS", "INFO", "WARNING", "CRITICAL")
    assert len(res["checks"]) > 0


def test_compare_aircraft_configurations():
    res = tools.compare_aircraft_configurations(["cfg_endurance_quad_4s", "cfg_heavylift_hexa_6s"])
    assert isinstance(res, list)
    assert len(res) == 2
    assert res[0]["twr_max"] > 0
    assert res[1]["twr_max"] > 0


def test_analyse_motor_failure_quad_vs_hexa():
    # Quadcopters should highlight catastrophic lack of attitude control
    quad_fail = tools.analyse_motor_failure("cfg_endurance_quad_4s")
    assert quad_fail["status"] == "success"
    assert quad_fail["remaining_active_rotors"] == 3
    assert "Quadcopters" in quad_fail["aerodynamic_control_evaluation"]
    assert "CRITICAL" in quad_fail["aerodynamic_control_evaluation"]

    # Hexacopters have 5 active rotors remaining
    hexa_fail = tools.analyse_motor_failure("cfg_heavylift_hexa_6s")
    assert hexa_fail["status"] == "success"
    assert hexa_fail["remaining_active_rotors"] == 5
    assert hexa_fail["single_motor_failure_twr"] > 1.0


def test_retrieve_component_specifications():
    res = tools.retrieve_component_specifications(component_type="motor", query="T-Motor")
    assert res["status"] == "success"
    assert res["count"] > 0
    for r in res["results"]:
        assert r["component_type"] == "motor"
        assert "provenance" in r


def test_create_or_modify_aircraft_configuration():
    res = tools.create_or_modify_aircraft_configuration(
        name="Test Octo Titan",
        frame_type="Octocopter (X8)",
        num_motors=8,
        dry_mass_kg=4.0,
        payload_mass_kg=3.0,
        motor_manufacturer="T-Motor",
        motor_model="MN6007",
        motor_kv=320,
        motor_max_current_a=35.0,
        motor_max_power_w=850.0,
        prop_model="18x6.1 CF",
        prop_diameter_in=18.0,
        prop_pitch_in=6.1,
        esc_continuous_a=50.0,
        esc_peak_a=65.0,
        battery_cells_s=6,
        battery_capacity_mah=16000.0,
        battery_continuous_c=25.0,
    )
    assert res["status"] == "success"
    assert res["config_id"].startswith("cfg_ai_")
    assert res["initial_analysis"]["status"] == "success"
    assert res["initial_analysis"]["rotor_count"] == 8
