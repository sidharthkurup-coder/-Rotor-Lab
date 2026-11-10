"""Thrust, hover equilibrium, payload margin, and actuator-disk momentum analysis.

CRITICAL ENGINEERING PRINCIPLE:
Accurate motor thrust cannot be calculated from KV rating and propeller dimensions
alone without empirical blade section / test-stand data. This module interpolates
documented motor-propeller performance datasets and flags any out-of-bounds
extrapolation requests explicitly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from rotorlab.models.domain import (
    AirframeSpec,
    DataProvenance,
    PerformanceDataset,
    PerformancePoint,
    PropellerSpec,
)
from rotorlab.models.units import (
    STANDARD_GRAVITY_M_S2,
    calculate_isa_air_density,
    calculate_rotor_disk_area_m2,
    calculate_tip_speed_m_s,
    gf_to_newtons,
    mass_kg_to_weight_n,
    newtons_to_gf,
    newtons_to_kgf,
)


@dataclass(frozen=True)
class InterpolatedMotorState:
    """Interpolated performance state of a single motor at a specific throttle or thrust."""

    throttle_pct: float
    thrust_gf: float
    thrust_n: float
    current_a: float
    power_w: float
    rpm: float
    efficiency_gf_w: float
    tip_speed_m_s: float
    provenance: DataProvenance
    is_extrapolated: bool = False
    extrapolation_warning: Optional[str] = None


@dataclass(frozen=True)
class ThrustAnalysisResult:
    """Comprehensive thrust, hover equilibrium, and actuator-disk analysis result."""

    # Aircraft mass & weight
    aircraft_dry_mass_kg: float
    payload_mass_kg: float
    total_mass_kg: float
    aircraft_weight_n: float
    aircraft_weight_gf: float

    # Single motor & total thrust at 100% (or dataset max) throttle
    max_single_motor_state: InterpolatedMotorState
    max_total_thrust_n: float
    max_total_thrust_gf: float
    max_total_thrust_kgf: float

    # Operating throttle state
    operating_single_motor_state: InterpolatedMotorState
    operating_total_thrust_n: float
    operating_total_thrust_gf: float

    # Hover equilibrium state (Thrust == Aircraft Weight)
    hover_feasible: bool
    hover_required_per_motor_n: float
    hover_required_per_motor_gf: float
    hover_single_motor_state: Optional[InterpolatedMotorState]

    # Thrust-to-Weight Ratio & Margins
    twr_max: float
    twr_operating: float
    available_thrust_margin_n: float
    available_thrust_margin_gf: float
    available_thrust_margin_pct: float
    max_payload_at_twr_1_kg: float
    max_additional_payload_at_target_twr_kg: float
    target_twr_used: float

    # Actuator Disk & Rotor Aerodynamics (at Hover if feasible, else Operating)
    air_density_kg_m3: float
    single_disk_area_m2: float
    total_disk_area_m2: float
    disk_loading_n_m2: float
    disk_loading_kg_m2: float
    hover_induced_velocity_m_s: float
    ideal_hover_power_per_motor_w: float
    figure_of_merit_hover: float

    # Redundancy (N-1 motor-out static thrust ratio)
    motor_out_max_thrust_n: float
    motor_out_twr: float

    # Provenance & Warnings
    provenance: DataProvenance
    source_reference: str
    warnings: List[str] = field(default_factory=list)


def interpolate_at_throttle(
    dataset: PerformanceDataset,
    propeller: PropellerSpec,
    target_throttle_pct: float,
    allow_extrapolation: bool = False,
) -> InterpolatedMotorState:
    """Interpolate motor performance metrics at a specified throttle percentage.

    Uses piecewise linear interpolation across measured points. If target_throttle_pct
    lies outside [min_throttle_pct, max_throttle_pct], raises a warning and either
    clamps or linearly extrapolates only when explicitly requested.
    """
    if not (0.0 <= target_throttle_pct <= 100.0):
        raise ValueError(f"Target throttle ({target_throttle_pct}%) must be between 0% and 100%.")

    throttles = np.array([p.throttle_pct for p in dataset.points], dtype=float)
    thrusts_gf = np.array([p.thrust_gf for p in dataset.points], dtype=float)
    currents_a = np.array([p.current_a for p in dataset.points], dtype=float)
    powers_w = np.array([p.power_w for p in dataset.points], dtype=float)
    rpms = np.array([p.rpm for p in dataset.points], dtype=float)

    min_th = float(throttles[0])
    max_th = float(throttles[-1])

    is_extrapolated = False
    warning_msg: Optional[str] = None

    if target_throttle_pct < min_th or target_throttle_pct > max_th:
        is_extrapolated = True
        warning_msg = (
            f"Requested throttle ({target_throttle_pct:.1f}%) lies outside the dataset's "
            f"measured throttle domain [{min_th:.1f}%, {max_th:.1f}%]."
        )
        if not allow_extrapolation:
            # Extrapolation below min_th down to 0% throttle can be anchored to (0% -> 0 thrust)
            # ONLY as an explicit estimate with a warning. Above max_th, clamp to max_th.
            if target_throttle_pct < min_th:
                warning_msg += (
                    " Anchoring lower bound to zero-throttle origin (0% -> 0 gf, no-load current) "
                    "as a calculated boundary estimate; low-throttle measurements should be added for higher fidelity."
                )
                throttles_ext = np.insert(throttles, 0, 0.0)
                thrusts_ext = np.insert(thrusts_gf, 0, 0.0)
                currents_ext = np.insert(currents_a, 0, 0.0)
                powers_ext = np.insert(powers_w, 0, 0.0)
                rpms_ext = np.insert(rpms, 0, 0.0)
                th_val = float(np.interp(target_throttle_pct, throttles_ext, thrusts_ext))
                cur_val = float(np.interp(target_throttle_pct, throttles_ext, currents_ext))
                pwr_val = float(np.interp(target_throttle_pct, throttles_ext, powers_ext))
                rpm_val = float(np.interp(target_throttle_pct, throttles_ext, rpms_ext))
            else:
                warning_msg += f" Clamped to maximum available measurement point ({max_th:.1f}%)."
                th_val = float(thrusts_gf[-1])
                cur_val = float(currents_a[-1])
                pwr_val = float(powers_w[-1])
                rpm_val = float(rpms[-1])
        else:
            # Explicit linear extrapolation from nearest segment
            if target_throttle_pct < min_th:
                idx0, idx1 = 0, 1
            else:
                idx0, idx1 = len(throttles) - 2, len(throttles) - 1
            dt = throttles[idx1] - throttles[idx0]
            frac = (target_throttle_pct - throttles[idx0]) / dt
            th_val = max(0.0, float(thrusts_gf[idx0] + frac * (thrusts_gf[idx1] - thrusts_gf[idx0])))
            cur_val = max(0.0, float(currents_a[idx0] + frac * (currents_a[idx1] - currents_a[idx0])))
            pwr_val = max(0.0, float(powers_w[idx0] + frac * (powers_w[idx1] - powers_w[idx0])))
            rpm_val = max(0.0, float(rpms[idx0] + frac * (rpms[idx1] - rpms[idx0])))
            warning_msg += " Linearly extrapolated beyond dataset bounds — treat with caution."
    else:
        th_val = float(np.interp(target_throttle_pct, throttles, thrusts_gf))
        cur_val = float(np.interp(target_throttle_pct, throttles, currents_a))
        pwr_val = float(np.interp(target_throttle_pct, throttles, powers_w))
        rpm_val = float(np.interp(target_throttle_pct, throttles, rpms))

    thrust_n = gf_to_newtons(th_val)
    eff_gf_w = th_val / pwr_val if pwr_val > 1e-6 else 0.0
    tip_speed = calculate_tip_speed_m_s(propeller.diameter_in, rpm_val)

    effective_provenance = (
        DataProvenance.CALCULATED_ESTIMATE if is_extrapolated else dataset.provenance
    )

    return InterpolatedMotorState(
        throttle_pct=target_throttle_pct,
        thrust_gf=th_val,
        thrust_n=thrust_n,
        current_a=cur_val,
        power_w=pwr_val,
        rpm=rpm_val,
        efficiency_gf_w=eff_gf_w,
        tip_speed_m_s=tip_speed,
        provenance=effective_provenance,
        is_extrapolated=is_extrapolated,
        extrapolation_warning=warning_msg,
    )


def solve_hover_motor_state(
    dataset: PerformanceDataset,
    propeller: PropellerSpec,
    required_thrust_per_motor_gf: float,
) -> tuple[bool, Optional[InterpolatedMotorState], Optional[str]]:
    """Solve for the motor operating state that produces `required_thrust_per_motor_gf`.

    Returns:
        (hover_feasible, state, warning_message)
    """
    if required_thrust_per_motor_gf <= 0:
        raise ValueError("Required thrust per motor must be strictly positive.")

    throttles = np.array([p.throttle_pct for p in dataset.points], dtype=float)
    thrusts_gf = np.array([p.thrust_gf for p in dataset.points], dtype=float)

    max_avail_gf = float(np.max(thrusts_gf))
    min_avail_gf = float(np.min(thrusts_gf))

    if required_thrust_per_motor_gf > max_avail_gf:
        return (
            False,
            None,
            (
                f"Hover equilibrium is infeasible: required thrust per motor "
                f"({required_thrust_per_motor_gf:.1f} gf) exceeds maximum measured "
                f"single-motor thrust ({max_avail_gf:.1f} gf)."
            ),
        )

    warning_msg: Optional[str] = None
    is_extrap = False

    if required_thrust_per_motor_gf < min_avail_gf:
        is_extrap = True
        warning_msg = (
            f"Required hover thrust per motor ({required_thrust_per_motor_gf:.1f} gf) is below "
            f"the lowest measured dataset point ({min_avail_gf:.1f} gf at {throttles[0]:.0f}% throttle). "
            f"Hover throttle is estimated by anchoring the lower bound to (0% throttle, 0 gf)."
        )
        throttles_lookup = np.insert(throttles, 0, 0.0)
        thrusts_lookup = np.insert(thrusts_gf, 0, 0.0)
        hover_throttle_pct = float(np.interp(required_thrust_per_motor_gf, thrusts_lookup, throttles_lookup))
    else:
        hover_throttle_pct = float(np.interp(required_thrust_per_motor_gf, thrusts_gf, throttles))

    state = interpolate_at_throttle(
        dataset=dataset,
        propeller=propeller,
        target_throttle_pct=hover_throttle_pct,
        allow_extrapolation=False,
    )

    if is_extrap and warning_msg:
        state = InterpolatedMotorState(
            throttle_pct=state.throttle_pct,
            thrust_gf=required_thrust_per_motor_gf,
            thrust_n=gf_to_newtons(required_thrust_per_motor_gf),
            current_a=state.current_a,
            power_w=state.power_w,
            rpm=state.rpm,
            efficiency_gf_w=state.efficiency_gf_w,
            tip_speed_m_s=state.tip_speed_m_s,
            provenance=DataProvenance.CALCULATED_ESTIMATE,
            is_extrapolated=True,
            extrapolation_warning=warning_msg,
        )

    return True, state, warning_msg


def analyze_thrust_and_twr(
    airframe: AirframeSpec,
    propeller: PropellerSpec,
    dataset: PerformanceDataset,
    target_twr_for_payload_margin: float = 2.0,
) -> ThrustAnalysisResult:
    """Execute complete Module B (Thrust Analysis) and Module D (Thrust-to-Weight Analysis).

    All force equations are evaluated in Newtons (SI) before deriving gram-force/kgf equivalents:
        W_aircraft [N] = (m_dry + m_payload) [kg] * g [m/s^2]
        T_total [N] = N_motors * T_single [N]
        TWR [-] = T_total [N] / W_aircraft [N]
    """
    if target_twr_for_payload_margin <= 0:
        raise ValueError("Target TWR for payload margin must be strictly positive.")

    warnings: List[str] = []

    total_mass_kg = airframe.total_mass_kg
    aircraft_weight_n = mass_kg_to_weight_n(total_mass_kg)
    aircraft_weight_gf = newtons_to_gf(aircraft_weight_n)

    # 1. Maximum available thrust state (at max measured throttle in dataset, typically 100%)
    max_th_pct = dataset.max_throttle_pct
    max_single_state = interpolate_at_throttle(dataset, propeller, max_th_pct)
    if max_th_pct < 100.0:
        warnings.append(
            f"Dataset maximum throttle is {max_th_pct:.1f}% (below 100%). Peak thrust is evaluated "
            f"at {max_th_pct:.1f}% to avoid unverified extrapolation."
        )

    max_total_thrust_n = airframe.num_motors * max_single_state.thrust_n
    max_total_thrust_gf = airframe.num_motors * max_single_state.thrust_gf
    max_total_thrust_kgf = newtons_to_kgf(max_total_thrust_n)

    # 2. Operating point thrust state
    op_single_state = interpolate_at_throttle(dataset, propeller, airframe.operating_throttle_pct)
    if op_single_state.extrapolation_warning:
        warnings.append(op_single_state.extrapolation_warning)

    op_total_thrust_n = airframe.num_motors * op_single_state.thrust_n
    op_total_thrust_gf = airframe.num_motors * op_single_state.thrust_gf

    # 3. Hover equilibrium state (Total Thrust == Aircraft Weight)
    req_hover_per_motor_n = aircraft_weight_n / airframe.num_motors
    req_hover_per_motor_gf = newtons_to_gf(req_hover_per_motor_n)

    hover_feasible, hover_state, hover_warn = solve_hover_motor_state(
        dataset=dataset,
        propeller=propeller,
        required_thrust_per_motor_gf=req_hover_per_motor_gf,
    )
    if hover_warn:
        warnings.append(hover_warn)

    # 4. Thrust-to-Weight Ratio (TWR) in strict SI units [N / N]
    twr_max = max_total_thrust_n / aircraft_weight_n
    twr_operating = op_total_thrust_n / aircraft_weight_n

    # Available thrust margin above hover weight
    available_margin_n = max_total_thrust_n - aircraft_weight_n
    available_margin_gf = newtons_to_gf(available_margin_n)
    available_margin_pct = (available_margin_n / aircraft_weight_n) * 100.0

    # Payload margins:
    # (a) Absolute static lift ceiling (TWR = 1.0): m_max_1 = (T_max / g) - m_dry
    max_total_mass_twr1_kg = max_total_thrust_n / STANDARD_GRAVITY_M_S2
    max_payload_at_twr_1_kg = max(0.0, max_total_mass_twr1_kg - airframe.aircraft_dry_mass_kg)

    # (b) Additional payload margin while maintaining target TWR (e.g., TWR = 2.0):
    #     m_max_target = T_max / (target_TWR * g)
    #     additional_payload = m_max_target - m_total_current
    max_total_mass_target_twr_kg = max_total_thrust_n / (
        target_twr_for_payload_margin * STANDARD_GRAVITY_M_S2
    )
    max_additional_payload_target_kg = max_total_mass_target_twr_kg - total_mass_kg

    # 5. Actuator Disk Momentum Theory & Rotor Aerodynamics
    rho = calculate_isa_air_density(airframe.altitude_m, airframe.temp_offset_c)
    single_disk_area_m2 = calculate_rotor_disk_area_m2(propeller.diameter_in)
    total_disk_area_m2 = airframe.num_motors * single_disk_area_m2

    # Disk loading based on aircraft hover weight over total rotor area
    disk_loading_n_m2 = aircraft_weight_n / total_disk_area_m2
    disk_loading_kg_m2 = total_mass_kg / total_disk_area_m2

    # Induced velocity at hover per motor: v_i = sqrt(T_hover / (2 * rho * A_single))
    hover_induced_v = math.sqrt(req_hover_per_motor_n / (2.0 * rho * single_disk_area_m2))
    # Ideal actuator-disk induced power per motor: P_ideal = T_hover * v_i
    ideal_hover_power_w = req_hover_per_motor_n * hover_induced_v

    if hover_feasible and hover_state is not None and hover_state.power_w > 1e-6:
        fm_hover = ideal_hover_power_w / hover_state.power_w
    else:
        fm_hover = 0.0

    # 6. Single-motor failure (N-1) static thrust capability
    motor_out_count = max(0, airframe.num_motors - 1)
    motor_out_max_thrust_n = motor_out_count * max_single_state.thrust_n
    motor_out_twr = motor_out_max_thrust_n / aircraft_weight_n

    if dataset.provenance == DataProvenance.ILLUSTRATIVE_SYNTHETIC:
        warnings.append(
            "Selected dataset uses ILLUSTRATIVE SYNTHETIC DATA for demonstration. "
            "Replace with manufacturer or thrust-stand measurements before hardware build."
        )

    return ThrustAnalysisResult(
        aircraft_dry_mass_kg=airframe.aircraft_dry_mass_kg,
        payload_mass_kg=airframe.payload_mass_kg,
        total_mass_kg=total_mass_kg,
        aircraft_weight_n=aircraft_weight_n,
        aircraft_weight_gf=aircraft_weight_gf,
        max_single_motor_state=max_single_state,
        max_total_thrust_n=max_total_thrust_n,
        max_total_thrust_gf=max_total_thrust_gf,
        max_total_thrust_kgf=max_total_thrust_kgf,
        operating_single_motor_state=op_single_state,
        operating_total_thrust_n=op_total_thrust_n,
        operating_total_thrust_gf=op_total_thrust_gf,
        hover_feasible=hover_feasible,
        hover_required_per_motor_n=req_hover_per_motor_n,
        hover_required_per_motor_gf=req_hover_per_motor_gf,
        hover_single_motor_state=hover_state,
        twr_max=twr_max,
        twr_operating=twr_operating,
        available_thrust_margin_n=available_margin_n,
        available_thrust_margin_gf=available_margin_gf,
        available_thrust_margin_pct=available_margin_pct,
        max_payload_at_twr_1_kg=max_payload_at_twr_1_kg,
        max_additional_payload_at_target_twr_kg=max_additional_payload_target_kg,
        target_twr_used=target_twr_for_payload_margin,
        air_density_kg_m3=rho,
        single_disk_area_m2=single_disk_area_m2,
        total_disk_area_m2=total_disk_area_m2,
        disk_loading_n_m2=disk_loading_n_m2,
        disk_loading_kg_m2=disk_loading_kg_m2,
        hover_induced_velocity_m_s=hover_induced_v,
        ideal_hover_power_per_motor_w=ideal_hover_power_w,
        figure_of_merit_hover=fm_hover,
        motor_out_max_thrust_n=motor_out_max_thrust_n,
        motor_out_twr=motor_out_twr,
        provenance=dataset.provenance,
        source_reference=dataset.source_reference,
        warnings=warnings,
    )
