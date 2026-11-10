"""Electrical power, battery energy, C-rate utilization, and flight endurance engine.

All equations are dimensionally consistent:
- Battery Nominal Energy: E [Wh] = V_nominal [V] * Capacity [Ah]
- Usable Energy: E_usable [Wh] = E [Wh] * f_usable
- Electrical Power: P [W] = V [V] * I [A]
- Flight Endurance: t [min] = (Capacity_usable [Ah] / I_average [A]) * 60

Real battery behavior disclaimer:
Real LiPo/Li-Ion cell voltage sags under load (V_term = V_oc - I * R_internal) and
decays non-linearly over discharge, while effective capacity decreases at high
C-rates (Peukert effect) and low ambient temperatures. RotorLab models both
nominal constant-current endurance and internal-resistance voltage sag.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from rotorlab.engine.thrust import ThrustAnalysisResult
from rotorlab.models.domain import AirframeSpec, BatterySpec, MotorSpec
from rotorlab.models.units import SECONDS_PER_MINUTE, mah_to_ah


@dataclass(frozen=True)
class OperatingPointElectricalState:
    """Electrical demand and endurance state at a specific flight regime (Hover, Operating, Peak)."""

    regime_name: str
    per_motor_current_a: float
    total_motor_current_a: float
    avionics_current_a: float
    total_system_current_a: float
    estimated_voltage_sag_v: float
    loaded_bus_voltage_v: float
    total_motor_power_w: float
    avionics_power_w: float
    total_electrical_power_w: float
    motor_copper_loss_per_motor_w: float
    effective_c_rate: float
    battery_continuous_utilization_pct: float
    estimated_endurance_min: float


@dataclass(frozen=True)
class ElectricalAnalysisResult:
    """Complete Module C electrical analysis result."""

    # Battery core specifications & capacities
    nominal_voltage_v: float
    operating_voltage_v: float
    capacity_mah: float
    capacity_ah: float
    usable_capacity_fraction: float
    reserve_capacity_fraction: float
    usable_capacity_ah: float
    usable_capacity_mah: float
    nominal_energy_wh: float
    usable_energy_wh: float
    specific_energy_wh_kg: float

    # Battery discharge limits
    max_continuous_discharge_a: float
    max_burst_discharge_a: float
    pack_internal_resistance_mohm: float

    # Regime states
    hover_state: Optional[OperatingPointElectricalState]
    operating_state: OperatingPointElectricalState
    peak_state: OperatingPointElectricalState

    # Engineering notes & assumptions
    assumptions: List[str] = field(default_factory=list)


def calculate_battery_energy_wh(voltage_v: float, capacity_ah: float) -> float:
    """Calculate nominal electrical energy stored in a battery pack [Wh].

    Formula: E (Wh) = V (V) * Capacity (Ah)
    """
    if voltage_v <= 0:
        raise ValueError("Voltage must be strictly positive.")
    if capacity_ah <= 0:
        raise ValueError("Capacity (Ah) must be strictly positive.")
    return voltage_v * capacity_ah


def calculate_electrical_power_w(voltage_v: float, current_a: float) -> float:
    """Calculate DC electrical power [W].

    Formula: P (W) = V (V) * I (A)
    """
    if voltage_v <= 0:
        raise ValueError("Voltage must be strictly positive.")
    if current_a < 0:
        raise ValueError("Current cannot be negative.")
    return voltage_v * current_a


def calculate_endurance_minutes(usable_capacity_ah: float, average_current_a: float) -> float:
    """Calculate estimated flight endurance in minutes.

    Formula: Time (minutes) = (Usable capacity (Ah) / Average current (A)) * 60
    """
    if usable_capacity_ah <= 0:
        raise ValueError("Usable capacity (Ah) must be strictly positive.")
    if average_current_a < 0:
        raise ValueError("Average current cannot be negative.")
    if average_current_a == 0.0:
        return 0.0
    return (usable_capacity_ah / average_current_a) * SECONDS_PER_MINUTE


def _evaluate_regime_state(
    regime_name: str,
    per_motor_current_a: float,
    airframe: AirframeSpec,
    battery: BatterySpec,
    motor: MotorSpec,
    usable_capacity_ah: float,
    capacity_ah: float,
    max_continuous_discharge_a: float,
    pack_resistance_ohm: float,
) -> OperatingPointElectricalState:
    """Evaluate complete system electrical metrics for a single flight regime."""
    total_motor_current_a = airframe.num_motors * per_motor_current_a
    avionics_current_a = airframe.avionics_power_w / battery.operating_voltage_v
    total_system_current_a = total_motor_current_a + avionics_current_a

    # Voltage sag across series cells: V_sag = I_total * R_pack
    voltage_sag_v = total_system_current_a * pack_resistance_ohm
    loaded_bus_v = max(0.0, battery.operating_voltage_v - voltage_sag_v)

    # Electrical power: P (W) = V (V) * I (A) using configured operating voltage
    total_motor_power_w = calculate_electrical_power_w(
        battery.operating_voltage_v, total_motor_current_a
    )
    total_electrical_power_w = calculate_electrical_power_w(
        battery.operating_voltage_v, total_system_current_a
    )

    # Resistive copper loss per motor: P_Cu = I_motor^2 * R_motor
    motor_r_ohm = motor.internal_resistance_mohm / 1000.0
    copper_loss_w = (per_motor_current_a ** 2) * motor_r_ohm

    effective_c_rate = total_system_current_a / capacity_ah if capacity_ah > 0 else 0.0
    utilization_pct = (
        (total_system_current_a / max_continuous_discharge_a) * 100.0
        if max_continuous_discharge_a > 0
        else 0.0
    )

    endurance_min = calculate_endurance_minutes(usable_capacity_ah, total_system_current_a)

    return OperatingPointElectricalState(
        regime_name=regime_name,
        per_motor_current_a=per_motor_current_a,
        total_motor_current_a=total_motor_current_a,
        avionics_current_a=avionics_current_a,
        total_system_current_a=total_system_current_a,
        estimated_voltage_sag_v=voltage_sag_v,
        loaded_bus_voltage_v=loaded_bus_v,
        total_motor_power_w=total_motor_power_w,
        avionics_power_w=airframe.avionics_power_w,
        total_electrical_power_w=total_electrical_power_w,
        motor_copper_loss_per_motor_w=copper_loss_w,
        effective_c_rate=effective_c_rate,
        battery_continuous_utilization_pct=utilization_pct,
        estimated_endurance_min=endurance_min,
    )


def analyze_electrical_system(
    battery: BatterySpec,
    motor: MotorSpec,
    airframe: AirframeSpec,
    thrust_result: ThrustAnalysisResult,
) -> ElectricalAnalysisResult:
    """Execute complete Module C Electrical Analysis."""
    capacity_ah = mah_to_ah(battery.capacity_mah)
    usable_capacity_ah = capacity_ah * battery.usable_capacity_fraction
    usable_capacity_mah = battery.capacity_mah * battery.usable_capacity_fraction

    nominal_energy_wh = calculate_battery_energy_wh(battery.nominal_voltage_v, capacity_ah)
    usable_energy_wh = nominal_energy_wh * battery.usable_capacity_fraction

    battery_mass_kg = battery.mass_g / 1000.0
    specific_energy_wh_kg = nominal_energy_wh / battery_mass_kg if battery_mass_kg > 0 else 0.0

    max_continuous_discharge_a = capacity_ah * battery.continuous_c_rating
    max_burst_discharge_a = capacity_ah * battery.burst_c_rating

    pack_resistance_mohm = battery.cell_count_s * battery.internal_resistance_per_cell_mohm
    pack_resistance_ohm = pack_resistance_mohm / 1000.0

    # 1. Hover regime electrical state (if hover is physically feasible)
    hover_elec_state: Optional[OperatingPointElectricalState] = None
    if thrust_result.hover_feasible and thrust_result.hover_single_motor_state is not None:
        hover_elec_state = _evaluate_regime_state(
            regime_name="Hover Equilibrium",
            per_motor_current_a=thrust_result.hover_single_motor_state.current_a,
            airframe=airframe,
            battery=battery,
            motor=motor,
            usable_capacity_ah=usable_capacity_ah,
            capacity_ah=capacity_ah,
            max_continuous_discharge_a=max_continuous_discharge_a,
            pack_resistance_ohm=pack_resistance_ohm,
        )

    # 2. Configured operating throttle electrical state
    operating_elec_state = _evaluate_regime_state(
        regime_name=f"Operating Point ({airframe.operating_throttle_pct:.0f}% Throttle)",
        per_motor_current_a=thrust_result.operating_single_motor_state.current_a,
        airframe=airframe,
        battery=battery,
        motor=motor,
        usable_capacity_ah=usable_capacity_ah,
        capacity_ah=capacity_ah,
        max_continuous_discharge_a=max_continuous_discharge_a,
        pack_resistance_ohm=pack_resistance_ohm,
    )

    # 3. Peak (100% / max dataset throttle) electrical state
    peak_elec_state = _evaluate_regime_state(
        regime_name=f"Peak Full-Throttle ({thrust_result.max_single_motor_state.throttle_pct:.0f}%)",
        per_motor_current_a=thrust_result.max_single_motor_state.current_a,
        airframe=airframe,
        battery=battery,
        motor=motor,
        usable_capacity_ah=usable_capacity_ah,
        capacity_ah=capacity_ah,
        max_continuous_discharge_a=max_continuous_discharge_a,
        pack_resistance_ohm=pack_resistance_ohm,
    )

    assumptions = [
        f"Battery usable capacity fraction is set to {battery.usable_capacity_fraction * 100:.0f}% "
        f"({battery.reserve_fraction * 100:.0f}% safety reserve retained to prevent deep-discharge LiPo damage).",
        f"Continuous auxiliary/avionics load of {airframe.avionics_power_w:.1f} W "
        f"({airframe.avionics_power_w / battery.operating_voltage_v:.2f} A @ {battery.operating_voltage_v:.1f} V) "
        f"is added to total propulsion bus current.",
        "Real battery terminal voltage, current draw, and effective capacity vary dynamically during flight due to "
        "state-of-charge (SoC) voltage decay, internal resistance ohmic sag (V_sag = I * R_pack), Peukert capacity "
        "reduction at high C-rates, and cell temperature changes.",
    ]

    return ElectricalAnalysisResult(
        nominal_voltage_v=battery.nominal_voltage_v,
        operating_voltage_v=battery.operating_voltage_v,
        capacity_mah=battery.capacity_mah,
        capacity_ah=capacity_ah,
        usable_capacity_fraction=battery.usable_capacity_fraction,
        reserve_capacity_fraction=battery.reserve_fraction,
        usable_capacity_ah=usable_capacity_ah,
        usable_capacity_mah=usable_capacity_mah,
        nominal_energy_wh=nominal_energy_wh,
        usable_energy_wh=usable_energy_wh,
        specific_energy_wh_kg=specific_energy_wh_kg,
        max_continuous_discharge_a=max_continuous_discharge_a,
        max_burst_discharge_a=max_burst_discharge_a,
        pack_internal_resistance_mohm=pack_resistance_mohm,
        hover_state=hover_elec_state,
        operating_state=operating_elec_state,
        peak_state=peak_elec_state,
        assumptions=assumptions,
    )
