"""Orchestration service for RotorLab propulsion analysis, parametric sweeps, and multi-config comparison."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import List

import numpy as np

from rotorlab.engine.compatibility import CompatibilityAnalysisResult, evaluate_compatibility
from rotorlab.engine.electrical import ElectricalAnalysisResult, analyze_electrical_system
from rotorlab.engine.thrust import (
    InterpolatedMotorState,
    ThrustAnalysisResult,
    analyze_thrust_and_twr,
    interpolate_at_throttle,
)
from rotorlab.models.domain import PerformanceDataset, PropulsionConfiguration, SeverityLevel


@dataclass(frozen=True)
class PayloadSweepPoint:
    """Single point on the payload mass vs. endurance and TWR trade-study envelope."""

    payload_mass_kg: float
    total_mass_kg: float
    twr_max: float
    hover_feasible: bool
    hover_throttle_pct: float
    hover_system_current_a: float
    hover_endurance_min: float


@dataclass(frozen=True)
class CompleteConfigurationAnalysis:
    """Unified output of Modules B, C, D, and E for a single propulsion configuration."""

    config: PropulsionConfiguration
    dataset: PerformanceDataset
    thrust: ThrustAnalysisResult
    electrical: ElectricalAnalysisResult
    compatibility: CompatibilityAnalysisResult
    throttle_curve_states: List[InterpolatedMotorState] = field(default_factory=list)
    payload_sweep: List[PayloadSweepPoint] = field(default_factory=list)


@dataclass(frozen=True)
class ComparisonRow:
    """Summary metrics for a single configuration inside Module F Configuration Comparison."""

    config_id: str
    config_name: str
    frame_type: str
    num_motors: int
    motor_label: str
    propeller_label: str
    battery_label: str
    provenance_label: str
    total_mass_kg: float
    payload_mass_kg: float
    max_total_thrust_n: float
    max_total_thrust_gf: float
    twr_max: float
    hover_throttle_pct: float
    hover_current_a: float
    operating_current_a: float
    peak_current_a: float
    operating_power_w: float
    peak_power_w: float
    battery_nominal_energy_wh: float
    usable_energy_wh: float
    hover_endurance_min: float
    operating_endurance_min: float
    max_additional_payload_target_twr_kg: float
    max_payload_twr_1_kg: float
    esc_compatibility_status: SeverityLevel
    esc_margin_str: str
    overall_compatibility_status: SeverityLevel


def evaluate_configuration(
    config: PropulsionConfiguration,
    dataset: PerformanceDataset,
    num_curve_samples: int = 25,
    num_payload_samples: int = 20,
) -> CompleteConfigurationAnalysis:
    """Perform a complete deterministic engineering evaluation of a propulsion configuration."""
    thrust_res = analyze_thrust_and_twr(
        airframe=config.airframe,
        propeller=config.propeller,
        dataset=dataset,
        target_twr_for_payload_margin=config.margins.recommended_agile_twr,
    )

    elec_res = analyze_electrical_system(
        battery=config.battery,
        motor=config.motor,
        airframe=config.airframe,
        thrust_result=thrust_res,
    )

    compat_res = evaluate_compatibility(
        config=config,
        dataset=dataset,
        thrust_res=thrust_res,
        elec_res=elec_res,
    )

    # Generate dense interpolated curve across the dataset's valid measured throttle domain
    min_th = dataset.min_throttle_pct
    max_th = dataset.max_throttle_pct
    sample_throttles = np.linspace(min_th, max_th, max(2, num_curve_samples))
    # Ensure exact dataset points are included
    exact_throttles = [p.throttle_pct for p in dataset.points]
    merged_throttles = sorted(set(np.round(np.concatenate([sample_throttles, exact_throttles]), 4)))

    curve_states = [
        interpolate_at_throttle(dataset, config.propeller, float(th), allow_extrapolation=False)
        for th in merged_throttles
    ]

    # Generate Payload vs Endurance & TWR Parametric Sweep (from 0 kg up to TWR=1.2 ceiling)
    max_lift_mass_kg = thrust_res.max_total_thrust_n / 9.80665
    max_sweep_payload_kg = max(
        config.airframe.payload_mass_kg * 1.5,
        (max_lift_mass_kg / 1.15) - config.airframe.aircraft_dry_mass_kg,
    )
    max_sweep_payload_kg = max(0.5, max_sweep_payload_kg)

    payload_grid = np.linspace(0.0, max_sweep_payload_kg, max(2, num_payload_samples))
    payload_sweep: List[PayloadSweepPoint] = []
    for pl_kg in payload_grid:
        swept_airframe = dataclasses.replace(config.airframe, payload_mass_kg=float(pl_kg))
        t_sweep = analyze_thrust_and_twr(
            airframe=swept_airframe,
            propeller=config.propeller,
            dataset=dataset,
            target_twr_for_payload_margin=config.margins.recommended_agile_twr,
        )
        e_sweep = analyze_electrical_system(
            battery=config.battery,
            motor=config.motor,
            airframe=swept_airframe,
            thrust_result=t_sweep,
        )
        if t_sweep.hover_feasible and t_sweep.hover_single_motor_state and e_sweep.hover_state:
            h_th = t_sweep.hover_single_motor_state.throttle_pct
            h_cur = e_sweep.hover_state.total_system_current_a
            h_end = e_sweep.hover_state.estimated_endurance_min
        else:
            h_th = 100.0
            h_cur = e_sweep.peak_state.total_system_current_a
            h_end = 0.0

        payload_sweep.append(
            PayloadSweepPoint(
                payload_mass_kg=float(pl_kg),
                total_mass_kg=swept_airframe.total_mass_kg,
                twr_max=t_sweep.twr_max,
                hover_feasible=t_sweep.hover_feasible,
                hover_throttle_pct=h_th,
                hover_system_current_a=h_cur,
                hover_endurance_min=h_end,
            )
        )

    return CompleteConfigurationAnalysis(
        config=config,
        dataset=dataset,
        thrust=thrust_res,
        electrical=elec_res,
        compatibility=compat_res,
        throttle_curve_states=curve_states,
        payload_sweep=payload_sweep,
    )


def compare_configurations(
    analyses: List[CompleteConfigurationAnalysis],
) -> List[ComparisonRow]:
    """Build structured side-by-side comparison rows for Module F Configuration Comparison."""
    rows: List[ComparisonRow] = []
    for item in analyses:
        cfg = item.config
        tr = item.thrust
        el = item.electrical
        cp = item.compatibility

        esc_check = next(
            (c for c in cp.items if c.check_id == "ESC_CURRENT_COMPAT"),
            cp.items[0],
        )

        hover_th = (
            tr.hover_single_motor_state.throttle_pct
            if tr.hover_feasible and tr.hover_single_motor_state is not None
            else 100.0
        )
        hover_cur = el.hover_state.total_system_current_a if el.hover_state is not None else 0.0
        hover_end = el.hover_state.estimated_endurance_min if el.hover_state is not None else 0.0

        rows.append(
            ComparisonRow(
                config_id=cfg.config_id,
                config_name=cfg.name,
                frame_type=cfg.airframe.frame_type,
                num_motors=cfg.airframe.num_motors,
                motor_label=cfg.motor.full_name,
                propeller_label=f"{cfg.propeller.code}\" {cfg.propeller.material}",
                battery_label=f"{cfg.battery.cell_count_s}S {cfg.battery.capacity_mah:.0f}mAh ({cfg.battery.operating_voltage_v:.1f}V)",
                provenance_label=item.dataset.provenance.value,
                total_mass_kg=tr.total_mass_kg,
                payload_mass_kg=tr.payload_mass_kg,
                max_total_thrust_n=tr.max_total_thrust_n,
                max_total_thrust_gf=tr.max_total_thrust_gf,
                twr_max=tr.twr_max,
                hover_throttle_pct=hover_th,
                hover_current_a=hover_cur,
                operating_current_a=el.operating_state.total_system_current_a,
                peak_current_a=el.peak_state.total_system_current_a,
                operating_power_w=el.operating_state.total_electrical_power_w,
                peak_power_w=el.peak_state.total_electrical_power_w,
                battery_nominal_energy_wh=el.nominal_energy_wh,
                usable_energy_wh=el.usable_energy_wh,
                hover_endurance_min=hover_end,
                operating_endurance_min=el.operating_state.estimated_endurance_min,
                max_additional_payload_target_twr_kg=tr.max_additional_payload_at_target_twr_kg,
                max_payload_twr_1_kg=tr.max_payload_at_twr_1_kg,
                esc_compatibility_status=esc_check.severity,
                esc_margin_str=esc_check.margin_str,
                overall_compatibility_status=cp.overall_status,
            )
        )
    return rows
