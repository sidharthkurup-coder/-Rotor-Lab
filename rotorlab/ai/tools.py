"""Deterministic engineering tools exposed to Google Gemini via function calling.

Every numerical result returned here originates from validated aerodynamic,
electrical, and mechanical equations in rotorlab.engine and rotorlab.services.
Gemini is never allowed to fabricate or invent numbers.
"""

from __future__ import annotations

import dataclasses
import re
from typing import Any, Callable, Dict, List, Optional

from rotorlab.data.repository import RotorLabRepository
from rotorlab.engine.compatibility import evaluate_compatibility
from rotorlab.engine.electrical import analyze_electrical_system
from rotorlab.engine.thrust import analyze_thrust_and_twr
from rotorlab.models.domain import (
    AirframeSpec,
    BatterySpec,
    DataProvenance,
    EngineeringMargins,
    ESCSpec,
    MotorSpec,
    PropellerSpec,
    PropulsionConfiguration,
)
from rotorlab.services.analyzer import evaluate_configuration


class ToolExecutionLogger:
    """Thread-local / session tracker for engineering tool calls executed during AI inference."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def record(self, tool_name: str, args: Dict[str, Any], result: Any) -> None:
        self.calls.append({
            "tool_name": tool_name,
            "args": args,
            "result": result,
        })

    def clear(self) -> None:
        self.calls.clear()


# Default singleton logger for tool execution tracking
_GLOBAL_TOOL_LOGGER = ToolExecutionLogger()


def get_tool_logger() -> ToolExecutionLogger:
    return _GLOBAL_TOOL_LOGGER


def _get_active_repo(db_path: str = "rotorlab_workspace.db") -> RotorLabRepository:
    return RotorLabRepository(db_path)


def run_propulsion_analysis(config_id: str, custom_payload_kg: float = -1.0) -> dict:
    """Run a complete multirotor propulsion analysis evaluating static thrust, hover throttle, power draw, battery endurance, and component safety margins.

    Args:
        config_id: Unique identifier of the aircraft configuration in RotorLab (e.g. 'cfg_endurance_quad_4s', 'cfg_heavylift_hexa_6s').
        custom_payload_kg: Optional mission payload override in kilograms. Pass -1.0 to use the configuration's designed payload.

    Returns:
        Dictionary containing verified thrust, electrical, and compatibility metrics.
    """
    repo = _get_active_repo()
    config = repo.get_configuration(config_id)
    if not config:
        res = {"status": "error", "message": f"Configuration '{config_id}' not found in database."}
        _GLOBAL_TOOL_LOGGER.record("run_propulsion_analysis", {"config_id": config_id, "custom_payload_kg": custom_payload_kg}, res)
        return res

    dataset = repo.get_dataset(config.dataset_id)
    if not dataset:
        res = {"status": "error", "message": f"Dataset '{config.dataset_id}' for configuration '{config_id}' not found."}
        _GLOBAL_TOOL_LOGGER.record("run_propulsion_analysis", {"config_id": config_id, "custom_payload_kg": custom_payload_kg}, res)
        return res

    eval_config = config
    if custom_payload_kg >= 0.0:
        new_airframe = dataclasses.replace(config.airframe, payload_mass_kg=custom_payload_kg)
        eval_config = dataclasses.replace(config, airframe=new_airframe)

    analysis = evaluate_configuration(eval_config, dataset)
    tr = analysis.thrust
    el = analysis.electrical
    cp = analysis.compatibility

    hov_st = el.hover_state
    op_st = el.operating_state
    pk_st = el.peak_state

    esc_item = next((c for c in cp.items if c.check_id == "ESC_CURRENT_COMPAT"), None)

    result = {
        "status": "success",
        "config_id": config.config_id,
        "config_name": config.name,
        "frame_architecture": config.airframe.frame_type,
        "rotor_count": config.airframe.num_motors,
        "aircraft_dry_mass_kg": config.airframe.aircraft_dry_mass_kg,
        "payload_mass_kg": eval_config.airframe.payload_mass_kg,
        "total_takeoff_mass_kg": round(tr.total_mass_kg, 3),
        "aircraft_weight_n": round(tr.aircraft_weight_n, 2),
        "max_total_thrust_n": round(tr.max_total_thrust_n, 2),
        "max_total_thrust_gf": round(tr.max_total_thrust_gf, 1),
        "thrust_to_weight_ratio": round(tr.twr_max, 2),
        "hover_feasible": tr.hover_feasible,
        "hover_throttle_pct": round(tr.hover_single_motor_state.throttle_pct, 1) if tr.hover_feasible and tr.hover_single_motor_state else None,
        "hover_thrust_per_motor_gf": round(tr.hover_required_per_motor_gf, 1),
        "hover_system_current_a": round(hov_st.total_system_current_a, 2) if hov_st else 0.0,
        "hover_system_power_w": round(hov_st.total_electrical_power_w, 1) if hov_st else 0.0,
        "hover_flight_time_minutes": round(hov_st.estimated_endurance_min, 2) if hov_st else 0.0,
        "operating_throttle_pct": round(config.airframe.operating_throttle_pct, 1),
        "operating_system_current_a": round(op_st.total_system_current_a, 2),
        "operating_flight_time_minutes": round(op_st.estimated_endurance_min, 2),
        "peak_system_current_a": round(pk_st.total_system_current_a, 2),
        "battery_usable_capacity_mah": round(el.usable_capacity_mah, 0),
        "voltage_sag_at_hover_v": round(hov_st.estimated_voltage_sag_v, 2) if hov_st else 0.0,
        "max_additional_payload_at_twr_2_kg": round(tr.max_additional_payload_at_target_twr_kg, 2),
        "max_payload_limit_twr_1_kg": round(tr.max_payload_at_twr_1_kg, 2),
        "overall_compatibility_status": cp.overall_status.value,
        "esc_status": esc_item.severity.value if esc_item else "PASS",
        "esc_margin": esc_item.margin_str if esc_item else "N/A",
        "data_provenance": dataset.provenance.value,
        "source_reference": dataset.source_reference,
    }
    _GLOBAL_TOOL_LOGGER.record("run_propulsion_analysis", {"config_id": config_id, "custom_payload_kg": custom_payload_kg}, result)
    return result


def calculate_thrust_to_weight(config_id: str, custom_payload_kg: float = -1.0) -> dict:
    """Calculate the static thrust, total all-up weight (AUW), and thrust-to-weight ratio (TWR) of a multirotor UAV configuration.

    Args:
        config_id: Unique identifier of the aircraft configuration.
        custom_payload_kg: Optional mission payload mass in kilograms. Pass -1.0 for default.

    Returns:
        Dictionary with verified maximum thrust, weight, TWR, and aerospace agile design margin evaluation.
    """
    repo = _get_active_repo()
    config = repo.get_configuration(config_id)
    if not config:
        res = {"status": "error", "message": f"Configuration '{config_id}' not found."}
        _GLOBAL_TOOL_LOGGER.record("calculate_thrust_to_weight", {"config_id": config_id, "custom_payload_kg": custom_payload_kg}, res)
        return res

    dataset = repo.get_dataset(config.dataset_id)
    if not dataset:
        res = {"status": "error", "message": f"Dataset '{config.dataset_id}' not found."}
        _GLOBAL_TOOL_LOGGER.record("calculate_thrust_to_weight", {"config_id": config_id, "custom_payload_kg": custom_payload_kg}, res)
        return res

    eval_airframe = config.airframe
    if custom_payload_kg >= 0.0:
        eval_airframe = dataclasses.replace(config.airframe, payload_mass_kg=custom_payload_kg)

    tr = analyze_thrust_and_twr(
        airframe=eval_airframe,
        propeller=config.propeller,
        dataset=dataset,
        target_twr_for_payload_margin=config.margins.recommended_agile_twr,
    )

    twr_rating = "EXCELLENT" if tr.twr_max >= 2.0 else ("ADEQUATE" if tr.twr_max >= 1.5 else "CRITICAL_INSUFFICIENT")

    res = {
        "status": "success",
        "config_name": config.name,
        "rotor_count": eval_airframe.num_motors,
        "total_mass_kg": round(tr.total_mass_kg, 3),
        "aircraft_weight_n": round(tr.aircraft_weight_n, 2),
        "max_single_motor_thrust_n": round(tr.max_single_motor_state.thrust_n, 2),
        "max_single_motor_thrust_gf": round(tr.max_single_motor_state.thrust_gf, 1),
        "max_total_thrust_n": round(tr.max_total_thrust_n, 2),
        "max_total_thrust_gf": round(tr.max_total_thrust_gf, 1),
        "thrust_to_weight_ratio": round(tr.twr_max, 2),
        "twr_rating": twr_rating,
        "minimum_hover_margin_target": 1.50,
        "recommended_aerospace_target": 2.00,
        "max_additional_payload_at_twr_2_kg": round(tr.max_additional_payload_at_target_twr_kg, 2),
        "max_payload_at_twr_1_kg": round(tr.max_payload_at_twr_1_kg, 2),
        "data_provenance": dataset.provenance.value,
    }
    _GLOBAL_TOOL_LOGGER.record("calculate_thrust_to_weight", {"config_id": config_id, "custom_payload_kg": custom_payload_kg}, res)
    return res


def calculate_hover_throttle(config_id: str, custom_payload_kg: float = -1.0) -> dict:
    """Calculate hover feasibility, required thrust per rotor, hover throttle percentage, and single-rotor power at hover equilibrium.

    Args:
        config_id: Unique identifier of the aircraft configuration.
        custom_payload_kg: Optional mission payload mass in kilograms. Pass -1.0 for default.

    Returns:
        Dictionary with hover equilibrium throttle percentage, thrust per motor, and electrical draw.
    """
    repo = _get_active_repo()
    config = repo.get_configuration(config_id)
    if not config:
        res = {"status": "error", "message": f"Configuration '{config_id}' not found."}
        _GLOBAL_TOOL_LOGGER.record("calculate_hover_throttle", {"config_id": config_id, "custom_payload_kg": custom_payload_kg}, res)
        return res

    dataset = repo.get_dataset(config.dataset_id)
    if not dataset:
        res = {"status": "error", "message": f"Dataset '{config.dataset_id}' not found."}
        _GLOBAL_TOOL_LOGGER.record("calculate_hover_throttle", {"config_id": config_id, "custom_payload_kg": custom_payload_kg}, res)
        return res

    eval_airframe = config.airframe
    if custom_payload_kg >= 0.0:
        eval_airframe = dataclasses.replace(config.airframe, payload_mass_kg=custom_payload_kg)

    tr = analyze_thrust_and_twr(
        airframe=eval_airframe,
        propeller=config.propeller,
        dataset=dataset,
        target_twr_for_payload_margin=config.margins.recommended_agile_twr,
    )

    hover_state = tr.hover_single_motor_state
    res = {
        "status": "success",
        "config_name": config.name,
        "hover_feasible": tr.hover_feasible,
        "hover_throttle_pct": round(hover_state.throttle_pct, 1) if tr.hover_feasible and hover_state else None,
        "hover_required_thrust_per_motor_n": round(tr.hover_required_per_motor_n, 2),
        "hover_required_thrust_per_motor_gf": round(tr.hover_required_per_motor_gf, 1),
        "hover_single_motor_current_a": round(hover_state.current_a, 2) if tr.hover_feasible and hover_state else None,
        "hover_single_motor_power_w": round(hover_state.power_w, 1) if tr.hover_feasible and hover_state else None,
        "hover_single_motor_rpm": round(hover_state.rpm, 0) if tr.hover_feasible and hover_state else None,
        "hover_single_motor_efficiency_gf_w": round(hover_state.efficiency_gf_w, 2) if tr.hover_feasible and hover_state else None,
        "hover_throttle_assessment": (
            "OPTIMAL (<55% throttle offers wide control headroom for wind disturbance rejection)"
            if (tr.hover_feasible and hover_state and hover_state.throttle_pct <= 55.0)
            else (
                "ACCEPTABLE (55-65% throttle has adequate hover authority)"
                if (tr.hover_feasible and hover_state and hover_state.throttle_pct <= 65.0)
                else "HIGH (>65% throttle risks motor thermal saturation or lack of pitch/roll dynamic authority)"
            )
        ),
        "data_provenance": dataset.provenance.value,
    }
    _GLOBAL_TOOL_LOGGER.record("calculate_hover_throttle", {"config_id": config_id, "custom_payload_kg": custom_payload_kg}, res)
    return res


def calculate_battery_endurance(
    config_id: str, custom_payload_kg: float = -1.0, reserve_percentage: float = 20.0
) -> dict:
    """Calculate flight endurance (in minutes) at hover equilibrium and cruise/operating throttle, accounting for battery capacity, DoD reserve, and avionics auxiliary power.

    Args:
        config_id: Unique identifier of the aircraft configuration.
        custom_payload_kg: Optional mission payload in kilograms. Pass -1.0 for default.
        reserve_percentage: Safety reserve capacity percentage to leave in battery at landing (default 20%).

    Returns:
        Dictionary containing hover flight time, cruise flight time, total power consumption, and voltage sag.
    """
    repo = _get_active_repo()
    config = repo.get_configuration(config_id)
    if not config:
        res = {"status": "error", "message": f"Configuration '{config_id}' not found."}
        _GLOBAL_TOOL_LOGGER.record("calculate_battery_endurance", {"config_id": config_id, "custom_payload_kg": custom_payload_kg, "reserve_percentage": reserve_percentage}, res)
        return res

    dataset = repo.get_dataset(config.dataset_id)
    if not dataset:
        res = {"status": "error", "message": f"Dataset '{config.dataset_id}' not found."}
        _GLOBAL_TOOL_LOGGER.record("calculate_battery_endurance", {"config_id": config_id, "custom_payload_kg": custom_payload_kg, "reserve_percentage": reserve_percentage}, res)
        return res

    usable_fraction = max(0.1, min(1.0, (100.0 - reserve_percentage) / 100.0))
    eval_battery = dataclasses.replace(config.battery, usable_capacity_fraction=usable_fraction)

    eval_airframe = config.airframe
    if custom_payload_kg >= 0.0:
        eval_airframe = dataclasses.replace(config.airframe, payload_mass_kg=custom_payload_kg)

    eval_config = dataclasses.replace(config, battery=eval_battery, airframe=eval_airframe)
    analysis = evaluate_configuration(eval_config, dataset)
    el = analysis.electrical
    hov_st = el.hover_state
    op_st = el.operating_state
    pk_st = el.peak_state

    res = {
        "status": "success",
        "config_name": config.name,
        "battery_spec": f"{config.battery.name} ({config.battery.cell_count_s}S {config.battery.capacity_mah:g} mAh)",
        "nominal_voltage_v": config.battery.nominal_voltage_v,
        "usable_capacity_mah": round(el.usable_capacity_mah, 0),
        "reserve_percentage": round(reserve_percentage, 1),
        "hover_system_current_a": round(hov_st.total_system_current_a, 2) if hov_st else 0.0,
        "hover_system_power_w": round(hov_st.total_electrical_power_w, 1) if hov_st else 0.0,
        "hover_endurance_minutes": round(hov_st.estimated_endurance_min, 2) if hov_st else 0.0,
        "operating_throttle_pct": round(config.airframe.operating_throttle_pct, 1),
        "operating_system_current_a": round(op_st.total_system_current_a, 2),
        "operating_system_power_w": round(op_st.total_electrical_power_w, 1),
        "operating_endurance_minutes": round(op_st.estimated_endurance_min, 2),
        "voltage_sag_at_hover_v": round(hov_st.estimated_voltage_sag_v, 2) if hov_st else 0.0,
        "voltage_sag_at_peak_v": round(pk_st.estimated_voltage_sag_v, 2),
        "data_provenance": dataset.provenance.value,
    }
    _GLOBAL_TOOL_LOGGER.record("calculate_battery_endurance", {"config_id": config_id, "custom_payload_kg": custom_payload_kg, "reserve_percentage": reserve_percentage}, res)
    return res


def check_component_compatibility(config_id: str) -> dict:
    """Evaluate electrical, thermal, and voltage safety margins between motor, ESC, battery, and operating throttle.

    Args:
        config_id: Unique identifier of the aircraft configuration.

    Returns:
        Dictionary containing safety margins (ESC margin, motor margin, battery C-rate headroom) and diagnostic findings.
    """
    repo = _get_active_repo()
    config = repo.get_configuration(config_id)
    if not config:
        res = {"status": "error", "message": f"Configuration '{config_id}' not found."}
        _GLOBAL_TOOL_LOGGER.record("check_component_compatibility", {"config_id": config_id}, res)
        return res

    dataset = repo.get_dataset(config.dataset_id)
    if not dataset:
        res = {"status": "error", "message": f"Dataset '{config.dataset_id}' not found."}
        _GLOBAL_TOOL_LOGGER.record("check_component_compatibility", {"config_id": config_id}, res)
        return res

    analysis = evaluate_configuration(config, dataset)
    cp = analysis.compatibility
    esc_item = next((c for c in cp.items if c.check_id == "ESC_CURRENT_COMPAT"), None)

    res = {
        "status": "success",
        "config_name": config.name,
        "overall_status": cp.overall_status.value,
        "pass_count": cp.pass_count,
        "warning_count": cp.warning_count,
        "critical_count": cp.critical_count,
        "esc_compatibility_status": esc_item.severity.value if esc_item else "PASS",
        "esc_margin": esc_item.margin_str if esc_item else "N/A",
        "checks": [
            {
                "check_id": item.check_id,
                "category": item.category,
                "title": item.title,
                "severity": item.severity.value,
                "measured": item.measured_value_str,
                "limit": item.limit_value_str,
                "margin": item.margin_str,
                "explanation": item.explanation,
            }
            for item in cp.items
        ],
        "engineering_disclaimer": cp.engineering_disclaimer,
        "data_provenance": dataset.provenance.value,
    }
    _GLOBAL_TOOL_LOGGER.record("check_component_compatibility", {"config_id": config_id}, res)
    return res


def compare_aircraft_configurations(config_ids: list[str]) -> list[dict]:
    """Compare multiple UAV aircraft configurations side-by-side across thrust, weight, TWR, hover throttle, flight time, and ESC margins.

    Args:
        config_ids: List of configuration IDs to compare (e.g. ['cfg_endurance_quad_4s', 'cfg_heavylift_hexa_6s']).

    Returns:
        List of dictionaries with comparative engineering metrics for each configuration.
    """
    repo = _get_active_repo()
    results = []

    for cid in config_ids:
        cfg = repo.get_configuration(cid)
        if not cfg:
            continue
        ds = repo.get_dataset(cfg.dataset_id)
        if not ds:
            continue
        analysis = evaluate_configuration(cfg, ds)
        tr = analysis.thrust
        el = analysis.electrical
        cp = analysis.compatibility
        esc_item = next((c for c in cp.items if c.check_id == "ESC_CURRENT_COMPAT"), None)

        results.append({
            "config_id": cfg.config_id,
            "name": cfg.name,
            "architecture": cfg.airframe.frame_type,
            "rotor_count": cfg.airframe.num_motors,
            "dry_mass_kg": cfg.airframe.aircraft_dry_mass_kg,
            "payload_mass_kg": cfg.airframe.payload_mass_kg,
            "total_mass_kg": round(tr.total_mass_kg, 2),
            "max_thrust_n": round(tr.max_total_thrust_n, 2),
            "twr_max": round(tr.twr_max, 2),
            "hover_throttle_pct": round(tr.hover_single_motor_state.throttle_pct, 1) if tr.hover_feasible and tr.hover_single_motor_state else None,
            "hover_endurance_min": round(el.hover_state.estimated_endurance_min, 1) if el.hover_state else 0.0,
            "operating_endurance_min": round(el.operating_state.estimated_endurance_min, 1),
            "esc_margin": esc_item.margin_str if esc_item else "N/A",
            "compatibility_overall": cp.overall_status.value,
            "data_provenance": ds.provenance.value,
        })

    _GLOBAL_TOOL_LOGGER.record("compare_aircraft_configurations", {"config_ids": config_ids}, results)
    return results


def analyse_motor_failure(config_id: str) -> dict:
    """Analyze static thrust capability and aerodynamic controllability when a single rotor experiences in-flight failure (N-1 condition).

    Args:
        config_id: Unique identifier of the aircraft configuration.

    Returns:
        Dictionary with remaining thrust, degraded TWR(N-1), hover feasibility, and flight dynamics controllability evaluation.
    """
    repo = _get_active_repo()
    config = repo.get_configuration(config_id)
    if not config:
        res = {"status": "error", "message": f"Configuration '{config_id}' not found."}
        _GLOBAL_TOOL_LOGGER.record("analyse_motor_failure", {"config_id": config_id}, res)
        return res

    dataset = repo.get_dataset(config.dataset_id)
    if not dataset:
        res = {"status": "error", "message": f"Dataset '{config.dataset_id}' not found."}
        _GLOBAL_TOOL_LOGGER.record("analyse_motor_failure", {"config_id": config_id}, res)
        return res

    tr = analyze_thrust_and_twr(
        airframe=config.airframe,
        propeller=config.propeller,
        dataset=dataset,
        target_twr_for_payload_margin=config.margins.recommended_agile_twr,
    )

    num_rotors = config.airframe.num_motors
    remaining_rotors = max(0, num_rotors - 1)
    motor_out_twr = tr.motor_out_twr
    hover_possible_n_minus_1 = motor_out_twr >= 1.0

    if num_rotors <= 4:
        control_analysis = (
            "CRITICAL: Quadcopters (4 rotors) lack control redundancy after single motor loss. "
            "Opposing rotors must cancel yaw reaction torque and maintain roll/pitch equilibrium. "
            "A failed motor induces unrecoverable yaw spin and tumbling unless equipped with variable-pitch blades "
            "or an autonomous emergency parachute recovery system."
        )
    elif num_rotors == 6:
        if motor_out_twr >= 1.2:
            control_analysis = (
                "CAPABLE WITH REDUCED MARGIN: Standard hexacopter geometry (X6) can maintain controlled flight "
                "with 5 rotors if the flight controller mixer (PX4 / ArduPilot non-orthogonal mixer) "
                "re-allocates motor outputs. The remaining TWR of {twr:.2f} allows controlled descent and emergency landing.".format(twr=motor_out_twr)
            )
        else:
            control_analysis = (
                "MARGINAL: Hexacopter has geometric rotor redundancy, but degraded TWR (N-1) of {twr:.2f} is close "
                "to or below 1.0. Sustained hover is unlikely; aircraft will enter a descending trajectory.".format(twr=motor_out_twr)
            )
    else:  # Octocopter or higher
        control_analysis = (
            "HIGH REDUNDANCY: Octocopter architecture (8 rotors, X8 or flat-8) provides robust single-motor failure tolerance. "
            "The remaining 7 rotors retain {pct:.1f}% of total thrust with TWR_(N-1) = {twr:.2f}. "
            "Full attitude and altitude control can be maintained with minimal pilot intervention.".format(
                pct=(remaining_rotors / num_rotors) * 100.0, twr=motor_out_twr
            )
        )

    res = {
        "status": "success",
        "config_name": config.name,
        "frame_architecture": config.airframe.frame_type,
        "total_rotors": num_rotors,
        "remaining_active_rotors": remaining_rotors,
        "normal_twr_max": round(tr.twr_max, 2),
        "single_motor_failure_twr": round(motor_out_twr, 2),
        "single_motor_failure_thrust_n": round(tr.motor_out_max_thrust_n, 2),
        "thrust_capacity_loss_pct": round((1.0 / num_rotors) * 100.0, 1),
        "static_hover_possible_n_minus_1": hover_possible_n_minus_1,
        "aerodynamic_control_evaluation": control_analysis,
        "data_provenance": dataset.provenance.value,
    }
    _GLOBAL_TOOL_LOGGER.record("analyse_motor_failure", {"config_id": config_id}, res)
    return res


def retrieve_component_specifications(component_type: str = "all", query: str = "") -> dict:
    """Retrieve specifications, provenance, and electrical limits of UAV components (motors, propellers, ESCs, batteries) from the RotorLab database.

    Args:
        component_type: Type of component to search ('all', 'motor', 'propeller', 'esc', 'battery', or 'aircraft').
        query: Optional text filter matching component name or manufacturer (e.g. 'T-Motor', 'APC', 'Tattu').

    Returns:
        Dictionary containing matching component records with provenance tags.
    """
    repo = _get_active_repo()
    ctype = component_type.lower().strip()
    q = query.lower().strip()

    if ctype in ("aircraft", "config", "configurations"):
        configs = repo.list_configurations()
        filtered = [
            {
                "config_id": c.config_id,
                "name": c.name,
                "description": c.description,
                "frame": c.airframe.frame_type,
                "num_motors": c.airframe.num_motors,
                "dry_mass_kg": c.airframe.aircraft_dry_mass_kg,
                "payload_mass_kg": c.airframe.payload_mass_kg,
                "motor": c.motor.full_name,
                "propeller": f"{c.propeller.manufacturer} {c.propeller.code}",
                "esc": c.esc.name,
                "battery": c.battery.name,
            }
            for c in configs
            if (not q or q in c.name.lower() or q in c.description.lower() or q in c.motor.full_name.lower())
        ]
        res = {"status": "success", "count": len(filtered), "results": filtered}
        _GLOBAL_TOOL_LOGGER.record("retrieve_component_specifications", {"component_type": component_type, "query": query}, res)
        return res

    filter_type = None if ctype == "all" else ctype
    components = repo.list_components(component_type=filter_type)
    if q:
        components = [
            c for c in components
            if q in c["name"].lower() or q in c["manufacturer"].lower() or q in c["component_type"].lower()
        ]

    res = {
        "status": "success",
        "count": len(components),
        "results": [
            {
                "component_id": c["component_id"],
                "component_type": c["component_type"],
                "name": c["name"],
                "manufacturer": c["manufacturer"],
                "provenance": c["provenance"],
                "source_reference": c["source_reference"],
                "specs": c["spec"],
            }
            for c in components
        ],
    }
    _GLOBAL_TOOL_LOGGER.record("retrieve_component_specifications", {"component_type": component_type, "query": query}, res)
    return res


def create_or_modify_aircraft_configuration(
    name: str,
    frame_type: str,
    num_motors: int,
    dry_mass_kg: float,
    payload_mass_kg: float,
    motor_manufacturer: str,
    motor_model: str,
    motor_kv: float,
    motor_max_current_a: float,
    motor_max_power_w: float,
    prop_model: str,
    prop_diameter_in: float,
    prop_pitch_in: float,
    esc_continuous_a: float,
    esc_peak_a: float,
    battery_cells_s: int,
    battery_capacity_mah: float,
    battery_continuous_c: float,
    dataset_id: str = "",
) -> dict:
    """Create a brand new custom UAV aircraft configuration or update an existing one in the RotorLab database.

    Args:
        name: Human-readable name for the aircraft (e.g. 'SkySurveyor 2kg Hexacopter').
        frame_type: Airframe architecture (e.g. 'Quadcopter (X4)', 'Hexacopter (X6)', 'Octocopter (X8)').
        num_motors: Total number of propulsion rotors (typically 4, 6, or 8).
        dry_mass_kg: Aircraft empty mass including frame, wiring, motors, and battery (without payload) in kg.
        payload_mass_kg: Designed mission payload mass in kg.
        motor_manufacturer: Motor brand (e.g. 'T-Motor', 'KDE Direct').
        motor_model: Motor model name (e.g. 'MN4006', 'U8 II').
        motor_kv: Motor velocity constant KV in RPM/V.
        motor_max_current_a: Motor continuous current rating limit in Amperes.
        motor_max_power_w: Motor maximum power limit in Watts.
        prop_model: Propeller model (e.g. '14x4.8 CF', 'APC 11x4.5').
        prop_diameter_in: Propeller diameter in inches.
        prop_pitch_in: Propeller pitch in inches.
        esc_continuous_a: Electronic speed controller continuous current rating in Amperes.
        esc_peak_a: ESC burst/peak current rating in Amperes.
        battery_cells_s: Battery series cell count (e.g. 4 for 4S 14.8V, 6 for 6S 22.2V).
        battery_capacity_mah: Battery nominal capacity in milliampere-hours (mAh).
        battery_continuous_c: Battery continuous discharge C-rating (e.g. 25.0).
        dataset_id: Optional ID of a performance dataset to link. If omitted, links to the closest matching dataset.

    Returns:
        Dictionary confirming creation, returning the assigned config_id and initial engineering analysis.
    """
    repo = _get_active_repo()

    # Determine default dataset if not provided
    active_dataset_id = dataset_id.strip() if dataset_id else ""
    if not active_dataset_id:
        all_datasets = repo.list_all_datasets()
        # Find closest match by cell voltage and rotor count
        target_v = battery_cells_s * 3.7
        best_ds = min(all_datasets, key=lambda d: abs(d.test_voltage_v - target_v))
        active_dataset_id = best_ds.dataset_id

    # Create domain specs with SI validation
    motor_spec = MotorSpec(
        manufacturer=motor_manufacturer.strip() or "Generic",
        model=motor_model.strip() or "CustomMotor",
        kv_rating=float(motor_kv),
        max_continuous_current_a=float(motor_max_current_a),
        max_continuous_power_w=float(motor_max_power_w),
        min_cells_s=max(1, battery_cells_s - 1),
        max_cells_s=battery_cells_s + 2,
    )

    prop_spec = PropellerSpec(
        manufacturer=motor_manufacturer.strip() or "AeroProp",
        model=prop_model.strip() or f"{prop_diameter_in}x{prop_pitch_in}",
        diameter_in=float(prop_diameter_in),
        pitch_in=float(prop_pitch_in),
    )

    esc_spec = ESCSpec(
        name=f"{motor_manufacturer} {int(round(esc_continuous_a))}A ESC",
        continuous_current_a=float(esc_continuous_a),
        peak_current_a=float(esc_peak_a),
        min_cells_s=max(1, battery_cells_s - 1),
        max_cells_s=battery_cells_s + 2,
    )

    nominal_v = round(battery_cells_s * 3.7, 1)
    bat_spec = BatterySpec(
        name=f"{battery_cells_s}S {int(round(battery_capacity_mah))}mAh LiPo",
        cell_count_s=int(battery_cells_s),
        nominal_voltage_v=nominal_v,
        operating_voltage_v=nominal_v,
        capacity_mah=float(battery_capacity_mah),
        continuous_c_rating=float(battery_continuous_c),
        burst_c_rating=float(battery_continuous_c * 1.5),
    )

    airframe_spec = AirframeSpec(
        frame_type=frame_type.strip() or "Quadcopter (X4)",
        num_motors=int(num_motors),
        aircraft_dry_mass_kg=float(dry_mass_kg),
        payload_mass_kg=float(payload_mass_kg),
    )

    safe_name_slug = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower()).strip("_")[:16]
    new_config_id = f"cfg_ai_{safe_name_slug}_{uuid.uuid4().hex[:6]}" if "uuid" in globals() else f"cfg_ai_{safe_name_slug}"

    import uuid
    new_config_id = f"cfg_ai_{safe_name_slug}_{uuid.uuid4().hex[:6]}"

    new_cfg = PropulsionConfiguration(
        config_id=new_config_id,
        name=name.strip(),
        description=f"AI-Generated configuration: {frame_type} with {motor_manufacturer} {motor_model}",
        motor=motor_spec,
        propeller=prop_spec,
        esc=esc_spec,
        battery=bat_spec,
        airframe=airframe_spec,
        dataset_id=active_dataset_id,
        margins=EngineeringMargins(),
    )

    saved_cfg = repo.save_configuration(new_cfg)

    # Also register components into catalog
    repo.save_component("motor", motor_spec, DataProvenance.USER_MEASURED, f"Config: {name}")
    repo.save_component("propeller", prop_spec, DataProvenance.USER_MEASURED, f"Config: {name}")
    repo.save_component("esc", esc_spec, DataProvenance.USER_MEASURED, f"Config: {name}")
    repo.save_component("battery", bat_spec, DataProvenance.USER_MEASURED, f"Config: {name}")

    # Run initial analysis
    initial_analysis = run_propulsion_analysis(new_config_id)

    res = {
        "status": "success",
        "message": f"Successfully created and persisted UAV configuration '{name}' (ID: {new_config_id}).",
        "config_id": new_config_id,
        "name": saved_cfg.name,
        "linked_dataset_id": active_dataset_id,
        "initial_analysis": initial_analysis,
    }
    _GLOBAL_TOOL_LOGGER.record("create_or_modify_aircraft_configuration", {"name": name, "frame_type": frame_type}, res)
    return res


def get_rotorlab_tools() -> list[Callable[..., Any]]:
    """Return the official list of callable Python functions for Google Gemini function calling."""
    return [
        run_propulsion_analysis,
        calculate_thrust_to_weight,
        calculate_hover_throttle,
        calculate_battery_endurance,
        check_component_compatibility,
        compare_aircraft_configurations,
        analyse_motor_failure,
        retrieve_component_specifications,
        create_or_modify_aircraft_configuration,
    ]
