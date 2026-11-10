"""Module E — Propulsion Component Compatibility and Margin Evaluation Engine.

Evaluates electrical, thermal, aerodynamic, and dataset consistency across:
1. Motor and ESC continuous & peak current compatibility.
2. Motor current and power ratings vs. peak/operating load.
3. Battery continuous & burst discharge capability.
4. Operating voltage and LiPo series cell-count compatibility across Motor, ESC, Battery, and Dataset.
5. Thrust-to-Weight Ratio (TWR) and hover throttle equilibrium margins.
6. Performance dataset match and provenance checks.

All warnings provide detailed engineering explanations and reference the user's
configurable `EngineeringMargins` rather than presenting unexplained red indicators
or claiming universal flight safety.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from rotorlab.engine.electrical import ElectricalAnalysisResult
from rotorlab.engine.thrust import ThrustAnalysisResult
from rotorlab.models.domain import (
    DataProvenance,
    PerformanceDataset,
    PropulsionConfiguration,
    SeverityLevel,
)


@dataclass(frozen=True)
class CompatibilityCheckItem:
    """Single engineering compatibility check result with full explanation."""

    check_id: str
    category: str
    title: str
    severity: SeverityLevel
    measured_value_str: str
    limit_value_str: str
    margin_str: str
    explanation: str


@dataclass(frozen=True)
class CompatibilityAnalysisResult:
    """Aggregate compatibility evaluation across all subsystem checks."""

    overall_status: SeverityLevel
    pass_count: int
    info_count: int
    warning_count: int
    critical_count: int
    items: List[CompatibilityCheckItem] = field(default_factory=list)
    engineering_disclaimer: str = (
        "Satisfying static thrust, TWR, and electrical current margins is a necessary preliminary "
        "condition for multirotor sizing, but does NOT guarantee flight safety. Dynamic control authority, "
        "propeller structural integrity, vibration modes, ESC thermal dissipation, CG alignment, and "
        "environmental wind gusts must be verified through ground testing before flight."
    )


def evaluate_compatibility(
    config: PropulsionConfiguration,
    dataset: PerformanceDataset,
    thrust_res: ThrustAnalysisResult,
    elec_res: ElectricalAnalysisResult,
) -> CompatibilityAnalysisResult:
    """Run all subsystem compatibility checks using configurable `EngineeringMargins`."""
    items: List[CompatibilityCheckItem] = []
    margins = config.margins
    motor = config.motor
    prop = config.propeller
    esc = config.esc
    batt = config.battery

    peak_motor_i = elec_res.peak_state.per_motor_current_a
    op_motor_i = elec_res.operating_state.per_motor_current_a
    peak_motor_p = thrust_res.max_single_motor_state.power_w

    # 1. ESC Continuous Current vs Motor Peak Current
    req_esc_cont_a = peak_motor_i * margins.esc_current_safety_factor
    esc_headroom_a = esc.continuous_current_a - peak_motor_i
    esc_ratio = esc.continuous_current_a / peak_motor_i if peak_motor_i > 0 else 999.0

    if peak_motor_i > esc.continuous_current_a:
        esc_sev = SeverityLevel.CRITICAL
        esc_exp = (
            f"Full-throttle per-motor current ({peak_motor_i:.1f} A) exceeds the ESC continuous rating "
            f"({esc.continuous_current_a:.1f} A) by {peak_motor_i - esc.continuous_current_a:.1f} A. "
            "Sustained full-throttle climb or high-load recovery risks MOSFET thermal failure or ESC desync."
        )
    elif esc.continuous_current_a < req_esc_cont_a:
        esc_sev = SeverityLevel.WARNING
        esc_exp = (
            f"ESC continuous rating ({esc.continuous_current_a:.1f} A) exceeds peak motor current "
            f"({peak_motor_i:.1f} A), but provides a {esc_ratio:.2f}x ratio, which is below the configured "
            f"{margins.esc_current_safety_factor:.2f}x engineering safety factor ({req_esc_cont_a:.1f} A recommended)."
        )
    else:
        esc_sev = SeverityLevel.PASS
        esc_exp = (
            f"ESC continuous current ({esc.continuous_current_a:.1f} A) satisfies the configured "
            f"{margins.esc_current_safety_factor:.2f}x safety factor over peak motor current ({peak_motor_i:.1f} A), "
            f"providing {esc_headroom_a:.1f} A ({esc_ratio:.2f}x) continuous thermal headroom."
        )

    items.append(
        CompatibilityCheckItem(
            check_id="ESC_CURRENT_COMPAT",
            category="ESC & Motor Electrical",
            title="ESC Continuous Current Rating vs. Peak Motor Demand",
            severity=esc_sev,
            measured_value_str=f"{peak_motor_i:.2f} A (Peak/Motor)",
            limit_value_str=f"{esc.continuous_current_a:.1f} A (ESC Cont) / {req_esc_cont_a:.1f} A (w/ {margins.esc_current_safety_factor:.2f}x SF)",
            margin_str=f"{esc_headroom_a:+.2f} A ({esc_ratio:.2f}x)",
            explanation=esc_exp,
        )
    )

    # 2. Motor Max Continuous Current Limit
    motor_i_warn_limit = motor.max_continuous_current_a * margins.motor_current_margin_ratio
    motor_i_margin = motor.max_continuous_current_a - peak_motor_i
    if peak_motor_i > motor.max_continuous_current_a:
        m_i_sev = SeverityLevel.CRITICAL
        m_i_exp = (
            f"Peak motor current ({peak_motor_i:.1f} A) exceeds the motor's maximum continuous rating "
            f"({motor.max_continuous_current_a:.1f} A). Prolonged high-throttle operation risks stator winding "
            "insulation breakdown and permanent neodymium magnet demagnetization."
        )
    elif peak_motor_i > motor_i_warn_limit or op_motor_i > motor_i_warn_limit:
        m_i_sev = SeverityLevel.WARNING
        m_i_exp = (
            f"Peak motor current ({peak_motor_i:.1f} A) exceeds {margins.motor_current_margin_ratio * 100:.0f}% "
            f"of the motor's maximum continuous rating ({motor.max_continuous_current_a:.1f} A). "
            "Monitor motor bell temperature and ensure adequate propwash cooling."
        )
    else:
        m_i_sev = SeverityLevel.PASS
        m_i_exp = (
            f"Peak motor current ({peak_motor_i:.1f} A) and operating current ({op_motor_i:.1f} A) remain safely "
            f"within the motor's {motor.max_continuous_current_a:.1f} A continuous specification."
        )

    items.append(
        CompatibilityCheckItem(
            check_id="MOTOR_CURRENT_LIMIT",
            category="ESC & Motor Electrical",
            title="Motor Stator Continuous Current Limit",
            severity=m_i_sev,
            measured_value_str=f"{peak_motor_i:.2f} A Peak / {op_motor_i:.2f} A Op",
            limit_value_str=f"{motor.max_continuous_current_a:.1f} A Max ({motor_i_warn_limit:.1f} A Warn)",
            margin_str=f"{motor_i_margin:+.2f} A",
            explanation=m_i_exp,
        )
    )

    # 3. Motor Max Continuous Power Limit
    motor_p_warn_limit = motor.max_continuous_power_w * margins.motor_current_margin_ratio
    motor_p_margin = motor.max_continuous_power_w - peak_motor_p
    if peak_motor_p > motor.max_continuous_power_w:
        m_p_sev = SeverityLevel.CRITICAL
        m_p_exp = (
            f"Peak per-motor electrical input power ({peak_motor_p:.1f} W) exceeds the motor's rated maximum "
            f"continuous power ({motor.max_continuous_power_w:.1f} W)."
        )
    elif peak_motor_p > motor_p_warn_limit:
        m_p_sev = SeverityLevel.WARNING
        m_p_exp = (
            f"Peak per-motor electrical power ({peak_motor_p:.1f} W) exceeds {margins.motor_current_margin_ratio * 100:.0f}% "
            f"of rated maximum power ({motor.max_continuous_power_w:.1f} W)."
        )
    else:
        m_p_sev = SeverityLevel.PASS
        m_p_exp = (
            f"Peak per-motor electrical power ({peak_motor_p:.1f} W) is within the motor's "
            f"{motor.max_continuous_power_w:.1f} W continuous rating."
        )

    items.append(
        CompatibilityCheckItem(
            check_id="MOTOR_POWER_LIMIT",
            category="ESC & Motor Electrical",
            title="Motor Continuous Electrical Power Rating",
            severity=m_p_sev,
            measured_value_str=f"{peak_motor_p:.1f} W",
            limit_value_str=f"{motor.max_continuous_power_w:.1f} W",
            margin_str=f"{motor_p_margin:+.1f} W",
            explanation=m_p_exp,
        )
    )

    # 4. Battery Discharge Capability vs System Current
    max_batt_cont_a = elec_res.max_continuous_discharge_a
    max_batt_burst_a = elec_res.max_burst_discharge_a
    warn_batt_cont_a = max_batt_cont_a * margins.battery_c_margin_ratio

    op_sys_i = elec_res.operating_state.total_system_current_a
    peak_sys_i = elec_res.peak_state.total_system_current_a
    batt_cont_margin = max_batt_cont_a - op_sys_i

    if op_sys_i > max_batt_cont_a or peak_sys_i > max_batt_burst_a:
        b_sev = SeverityLevel.CRITICAL
        b_exp = (
            f"System current demand (Operating: {op_sys_i:.1f} A, Peak: {peak_sys_i:.1f} A) exceeds battery "
            f"discharge limits (Continuous: {max_batt_cont_a:.1f} A @ {batt.continuous_c_rating:g}C, "
            f"Burst: {max_batt_burst_a:.1f} A @ {batt.burst_c_rating:g}C). Severe voltage sag, cell swelling, "
            "and thermal runaway hazard."
        )
    elif peak_sys_i > max_batt_cont_a or op_sys_i > warn_batt_cont_a:
        b_sev = SeverityLevel.WARNING
        b_exp = (
            f"Operating current ({op_sys_i:.1f} A) or peak current ({peak_sys_i:.1f} A) exceeds the configured "
            f"{margins.battery_c_margin_ratio * 100:.0f}% continuous discharge threshold ({warn_batt_cont_a:.1f} A) "
            f"or relies on burst C-rating ({max_batt_burst_a:.1f} A) at full throttle."
        )
    else:
        b_sev = SeverityLevel.PASS
        b_exp = (
            f"System current (Operating: {op_sys_i:.1f} A, Peak: {peak_sys_i:.1f} A) is comfortably within "
            f"the battery's continuous discharge rating ({max_batt_cont_a:.1f} A @ {batt.continuous_c_rating:g}C)."
        )

    items.append(
        CompatibilityCheckItem(
            check_id="BATTERY_DISCHARGE_COMPAT",
            category="Battery & Power Bus",
            title="Battery Continuous & Burst Discharge Capability",
            severity=b_sev,
            measured_value_str=f"{op_sys_i:.1f} A Op / {peak_sys_i:.1f} A Peak",
            limit_value_str=f"{max_batt_cont_a:.1f} A Cont / {max_batt_burst_a:.1f} A Burst",
            margin_str=f"{batt_cont_margin:+.1f} A (Op vs Cont)",
            explanation=b_exp,
        )
    )

    # 5. Operating Voltage & Series Cell Count Compatibility (Battery vs Motor & ESC)
    cell_s = batt.cell_count_s
    motor_cell_ok = motor.min_cells_s <= cell_s <= motor.max_cells_s
    esc_cell_ok = esc.min_cells_s <= cell_s <= esc.max_cells_s

    if not motor_cell_ok or not esc_cell_ok:
        v_sev = SeverityLevel.CRITICAL
        v_exp = (
            f"Battery cell count ({cell_s}S, {batt.nominal_voltage_v:.1f} V nominal) is outside component cell ratings: "
            f"Motor rated for {motor.min_cells_s}S–{motor.max_cells_s}S; "
            f"ESC rated for {esc.min_cells_s}S–{esc.max_cells_s}S."
        )
    else:
        # Also check if operating voltage is physically plausible for a LiPo/Li-Ion pack of `cell_s` cells (3.0V to 4.35V/cell)
        v_per_cell = batt.operating_voltage_v / cell_s
        if v_per_cell < 3.0 or v_per_cell > 4.35:
            v_sev = SeverityLevel.WARNING
            v_exp = (
                f"Component cell counts match ({cell_s}S), but configured operating voltage ({batt.operating_voltage_v:.2f} V, "
                f"or {v_per_cell:.2f} V/cell) lies outside typical LiPo/Li-Ion cell operating range (3.00–4.35 V/cell)."
            )
        else:
            v_sev = SeverityLevel.PASS
            v_exp = (
                f"Battery ({cell_s}S, {batt.operating_voltage_v:.1f} V, {v_per_cell:.2f} V/cell) matches "
                f"Motor ({motor.min_cells_s}S–{motor.max_cells_s}S) and ESC ({esc.min_cells_s}S–{esc.max_cells_s}S) voltage ratings."
            )

    items.append(
        CompatibilityCheckItem(
            check_id="VOLTAGE_CELL_COMPAT",
            category="Battery & Power Bus",
            title="Component Voltage & Series Cell Count Compatibility",
            severity=v_sev,
            measured_value_str=f"{cell_s}S ({batt.operating_voltage_v:.1f} V)",
            limit_value_str=f"Motor: {motor.min_cells_s}-{motor.max_cells_s}S | ESC: {esc.min_cells_s}-{esc.max_cells_s}S",
            margin_str="In Spec" if v_sev == SeverityLevel.PASS else "Check Bounds",
            explanation=v_exp,
        )
    )

    # 6. Performance Dataset Match & Voltage Consistency
    v_diff_pct = abs(batt.operating_voltage_v - dataset.test_voltage_v) / dataset.test_voltage_v * 100.0
    kv_diff_pct = abs(motor.kv_rating - dataset.motor_kv) / dataset.motor_kv * 100.0
    diam_diff = abs(prop.diameter_in - dataset.propeller_diameter_in)
    pitch_diff = abs(prop.pitch_in - dataset.propeller_pitch_in)

    mismatch_reasons: List[str] = []
    if v_diff_pct > margins.voltage_mismatch_tolerance_pct:
        mismatch_reasons.append(
            f"operating voltage ({batt.operating_voltage_v:.1f} V) differs from dataset test voltage "
            f"({dataset.test_voltage_v:.1f} V) by {v_diff_pct:.1f}% (tolerance: {margins.voltage_mismatch_tolerance_pct:.1f}%)"
        )
    if kv_diff_pct > 5.0:
        mismatch_reasons.append(
            f"configured motor KV ({motor.kv_rating:.0f}) differs from dataset motor KV ({dataset.motor_kv:.0f}) by {kv_diff_pct:.1f}%"
        )
    if diam_diff > 0.1 or pitch_diff > 0.1:
        mismatch_reasons.append(
            f"configured propeller ({prop.diameter_in:g}x{prop.pitch_in:g}\") differs from dataset propeller "
            f"({dataset.propeller_diameter_in:g}x{dataset.propeller_pitch_in:g}\")"
        )

    if mismatch_reasons:
        ds_sev = SeverityLevel.WARNING
        ds_exp = (
            "Propulsion configuration parameters diverge from the active performance dataset test conditions: "
            + "; ".join(mismatch_reasons)
            + ". Because static thrust and current cannot be accurately scaled from KV and propeller dimensions alone, "
            "measured predictions are only strictly valid at the dataset's test configuration."
        )
    elif dataset.provenance == DataProvenance.ILLUSTRATIVE_SYNTHETIC:
        ds_sev = SeverityLevel.INFO
        ds_exp = (
            f"Active dataset matches motor/propeller/voltage specifications, but provenance is "
            f"'{dataset.provenance.value}'. Verify on a physical thrust stand before critical mission deployment."
        )
    else:
        ds_sev = SeverityLevel.PASS
        ds_exp = (
            f"Configuration matches dataset test conditions ({dataset.test_voltage_v:.1f} V, "
            f"KV{dataset.motor_kv:.0f}, {dataset.propeller_diameter_in:g}x{dataset.propeller_pitch_in:g}\") "
            f"with provenance '{dataset.provenance.value}'."
        )

    items.append(
        CompatibilityCheckItem(
            check_id="DATASET_MATCH_COMPAT",
            category="Data Provenance & Fidelity",
            title="Motor-Propeller Performance Dataset Alignment",
            severity=ds_sev,
            measured_value_str=f"{batt.operating_voltage_v:.1f} V, KV{motor.kv_rating:.0f}, {prop.code}\"",
            limit_value_str=f"Dataset: {dataset.test_voltage_v:.1f} V, KV{dataset.motor_kv:.0f}, {dataset.propeller_diameter_in:g}x{dataset.propeller_pitch_in:g}\"",
            margin_str=f"ΔV = {v_diff_pct:.1f}%",
            explanation=ds_exp,
        )
    )

    # 7. Thrust-to-Weight Ratio (TWR) & Hover Equilibrium Margin
    twr_max = thrust_res.twr_max
    hover_th_str = (
        f"{thrust_res.hover_single_motor_state.throttle_pct:.1f}%"
        if thrust_res.hover_feasible and thrust_res.hover_single_motor_state is not None
        else "Infeasible (>100%)"
    )

    if not thrust_res.hover_feasible or twr_max < 1.0:
        twr_sev = SeverityLevel.CRITICAL
        twr_exp = (
            f"Maximum total thrust ({thrust_res.max_total_thrust_n:.2f} N / {thrust_res.max_total_thrust_gf:.0f} gf) "
            f"is less than aircraft weight ({thrust_res.aircraft_weight_n:.2f} N / {thrust_res.aircraft_weight_gf:.0f} gf), "
            f"yielding TWR = {twr_max:.2f}. The aircraft cannot achieve vertical liftoff."
        )
    elif twr_max < margins.min_hover_twr:
        twr_sev = SeverityLevel.CRITICAL
        twr_exp = (
            f"Maximum TWR ({twr_max:.2f}) is below the configured minimum hover margin threshold "
            f"({margins.min_hover_twr:.2f}). Insufficient thrust reserve exists for attitude stabilization, "
            "altitude hold in turbulence, or descent arrest."
        )
    elif twr_max < margins.recommended_agile_twr or (
        thrust_res.hover_single_motor_state is not None
        and thrust_res.hover_single_motor_state.throttle_pct > margins.max_hover_throttle_pct
    ):
        twr_sev = SeverityLevel.WARNING
        twr_exp = (
            f"Maximum TWR is {twr_max:.2f} (Hover throttle: {hover_th_str}). While above the minimum hover threshold "
            f"({margins.min_hover_twr:.2f}), it is below the recommended engineering design target "
            f"(TWR >= {margins.recommended_agile_twr:.2f}, Hover throttle <= {margins.max_hover_throttle_pct:.0f}%). "
            "Expect sluggish climb performance and reduced control margin in wind."
        )
    else:
        twr_sev = SeverityLevel.PASS
        twr_exp = (
            f"Maximum TWR is {twr_max:.2f} with hover equilibrium at {hover_th_str} throttle, satisfying both "
            f"the minimum hover threshold ({margins.min_hover_twr:.2f}) and the recommended design target "
            f"({margins.recommended_agile_twr:.2f}). Note: High TWR alone does not guarantee flight safety."
        )

    items.append(
        CompatibilityCheckItem(
            check_id="TWR_HOVER_MARGIN",
            category="Aeromechanical & Flight Envelope",
            title="Thrust-to-Weight Ratio (TWR) & Hover Equilibrium Authority",
            severity=twr_sev,
            measured_value_str=f"TWR {twr_max:.2f} (Hover @ {hover_th_str})",
            limit_value_str=f"Min: {margins.min_hover_twr:.2f} | Target: {margins.recommended_agile_twr:.2f}",
            margin_str=f"{twr_max - margins.recommended_agile_twr:+.2f} vs Target",
            explanation=twr_exp,
        )
    )

    # Tally counts and determine overall status
    pass_count = sum(1 for i in items if i.severity == SeverityLevel.PASS)
    info_count = sum(1 for i in items if i.severity == SeverityLevel.INFO)
    warning_count = sum(1 for i in items if i.severity == SeverityLevel.WARNING)
    critical_count = sum(1 for i in items if i.severity == SeverityLevel.CRITICAL)

    if critical_count > 0:
        overall = SeverityLevel.CRITICAL
    elif warning_count > 0:
        overall = SeverityLevel.WARNING
    elif info_count > 0:
        overall = SeverityLevel.INFO
    else:
        overall = SeverityLevel.PASS

    return CompatibilityAnalysisResult(
        overall_status=overall,
        pass_count=pass_count,
        info_count=info_count,
        warning_count=warning_count,
        critical_count=critical_count,
        items=items,
    )
