"""Module H — Engineering Reports Exporter (PDF, CSV, and Markdown Dossier).

Generates downloadable engineering reports containing:
- Configuration information
- Component specifications
- Engineering calculations & equations
- Results (Thrust, TWR, Hover Equilibrium, Electrical, Actuator Disk)
- Compatibility warnings and margin checks
- Data sources and provenance
- Assumptions and limitations
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import List

from fpdf import FPDF

from rotorlab.services.analyzer import ComparisonRow, CompleteConfigurationAnalysis


def _ascii_clean(text: str) -> str:
    """Sanitize Unicode mathematical symbols into Latin-1/ASCII equivalents for core PDF fonts."""
    replacements = {
        "—": "-",
        "–": "-",
        "×": "x",
        "Δ": "Delta ",
        "Ω": "Ohm",
        "μ": "u",
        "≥": ">=",
        "≤": "<=",
        "±": "+/-",
        "″": '"',
        "“": '"',
        "”": '"',
        "’": "'",
    }
    out = text
    for k, v in replacements.items():
        out = out.replace(k, v)
    return out.encode("latin-1", errors="replace").decode("latin-1")


def generate_markdown_report(analysis: CompleteConfigurationAnalysis) -> str:
    """Generate a structured Markdown engineering report for a single propulsion configuration."""
    cfg = analysis.config
    ds = analysis.dataset
    tr = analysis.thrust
    el = analysis.electrical
    cp = analysis.compatibility
    ts_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    hover_str = (
        f"{tr.hover_single_motor_state.throttle_pct:.1f}% throttle "
        f"({tr.hover_single_motor_state.thrust_gf:.1f} gf / {tr.hover_single_motor_state.thrust_n:.2f} N per motor, "
        f"{el.hover_state.total_system_current_a:.2f} A system current, "
        f"{el.hover_state.estimated_endurance_min:.1f} min hover endurance)"
        if tr.hover_feasible and tr.hover_single_motor_state and el.hover_state
        else "INFEASIBLE (Required hover thrust exceeds maximum available static thrust)"
    )

    lines = [
        f"# ROTORLAB 1.0 — ENGINEERING PROPULSION ANALYSIS REPORT",
        f"**Configuration Name:** {cfg.name} (`{cfg.config_id}`)  ",
        f"**Generated:** {ts_str}  ",
        f"**Overall Compatibility Status:** `{cp.overall_status.value}` "
        f"(Pass: {cp.pass_count}, Info: {cp.info_count}, Warning: {cp.warning_count}, Critical: {cp.critical_count})",
        "",
        "---",
        "## 1. Configuration & Component Specifications",
        f"- **Airframe Architecture:** {cfg.airframe.frame_type} ({cfg.airframe.num_motors} motors)",
        f"- **Mass Breakdown:** Dry Mass = {tr.aircraft_dry_mass_kg:.3f} kg | Payload Mass = {tr.payload_mass_kg:.3f} kg | **Total Takeoff Mass = {tr.total_mass_kg:.3f} kg** ({tr.aircraft_weight_n:.2f} N)",
        f"- **Atmospheric Conditions:** Altitude = {cfg.airframe.altitude_m:.0f} m MSL, ISA ΔT = {cfg.airframe.temp_offset_c:+.1f} °C, Air Density ρ = {tr.air_density_kg_m3:.4f} kg/m³",
        f"- **BLDC Motor:** {cfg.motor.full_name} | Max Cont Current = {cfg.motor.max_continuous_current_a:.1f} A | Max Power = {cfg.motor.max_continuous_power_w:.1f} W | R_int = {cfg.motor.internal_resistance_mohm:.1f} mΩ | Cell Range = {cfg.motor.min_cells_s}S–{cfg.motor.max_cells_s}S",
        f"- **Propeller:** {cfg.propeller.manufacturer} {cfg.propeller.model} ({cfg.propeller.diameter_in:g}×{cfg.propeller.pitch_in:g}\", {cfg.propeller.num_blades}-blade {cfg.propeller.material})",
        f"- **ESC:** {cfg.esc.name} | Continuous = {cfg.esc.continuous_current_a:.1f} A | Peak = {cfg.esc.peak_current_a:.1f} A | Cell Range = {cfg.esc.min_cells_s}S–{cfg.esc.max_cells_s}S",
        f"- **Battery Pack:** {cfg.battery.name} | {cfg.battery.cell_count_s}S | Nominal = {cfg.battery.nominal_voltage_v:.1f} V | Operating = {cfg.battery.operating_voltage_v:.1f} V | Capacity = {cfg.battery.capacity_mah:.0f} mAh ({el.capacity_ah:.2f} Ah) | Discharge = {cfg.battery.continuous_c_rating:g}C Cont / {cfg.battery.burst_c_rating:g}C Burst | Usable Fraction = {cfg.battery.usable_capacity_fraction * 100:.0f}%",
        "",
        "---",
        "## 2. Governing Engineering Equations",
        "- **Aircraft Gravitational Weight (SI):** `W [N] = (m_dry + m_payload) [kg] * 9.80665 [m/s^2]`",
        "- **Thrust-to-Weight Ratio (SI):** `TWR = T_total [N] / W [N]`",
        "- **Battery Nominal Energy:** `E [Wh] = V_nominal [V] * Capacity [Ah]`",
        "- **Electrical Power:** `P [W] = V_operating [V] * I [A]`",
        "- **Estimated Endurance:** `Time [min] = (Usable_Capacity [Ah] / I_average [A]) * 60`",
        "- **Actuator Disk Induced Velocity & Ideal Hover Power:** `v_i = sqrt(T_hover / (2 * rho * A_disk))`, `P_ideal = T_hover * v_i`, `FM = P_ideal / P_elec`",
        "",
        "---",
        "## 3. Thrust, Hover Equilibrium & Aerodynamic Results",
        f"- **Peak Single-Motor Thrust ({tr.max_single_motor_state.throttle_pct:.0f}% Throttle):** {tr.max_single_motor_state.thrust_gf:.1f} gf ({tr.max_single_motor_state.thrust_n:.2f} N) @ {tr.max_single_motor_state.rpm:.0f} RPM (Tip speed: {tr.max_single_motor_state.tip_speed_m_s:.1f} m/s)",
        f"- **Maximum Total Propulsion Thrust:** {tr.max_total_thrust_gf:.0f} gf ({tr.max_total_thrust_kgf:.2f} kgf / **{tr.max_total_thrust_n:.2f} N**)",
        f"- **Maximum Thrust-to-Weight Ratio (TWR):** **{tr.twr_max:.2f}** (Operating TWR @ {cfg.airframe.operating_throttle_pct:.0f}% throttle: {tr.twr_operating:.2f})",
        f"- **Available Thrust Margin Above Weight:** {tr.available_thrust_margin_n:+.2f} N ({tr.available_thrust_margin_gf:+.0f} gf / {tr.available_thrust_margin_pct:+.1f}%)",
        f"- **Hover Equilibrium Operating Point:** {hover_str}",
        f"- **Max Additional Payload Margin (at Target TWR = {tr.target_twr_used:.2f}):** {tr.max_additional_payload_at_target_twr_kg:+.3f} kg",
        f"- **Static Lift Ceiling Payload (at TWR = 1.0):** {tr.max_payload_at_twr_1_kg:.3f} kg",
        f"- **Rotor Disk Loading:** {tr.disk_loading_kg_m2:.2f} kg/m² ({tr.disk_loading_n_m2:.1f} N/m²) across {tr.total_disk_area_m2:.4f} m² total swept area",
        f"- **Hover Induced Velocity & Electro-Propulsive Figure of Merit:** v_i = {tr.hover_induced_velocity_m_s:.2f} m/s | Ideal Power = {tr.ideal_hover_power_per_motor_w:.1f} W/motor | FM = {tr.figure_of_merit_hover:.3f}",
        f"- **Single-Motor Failure (N-1) Static Thrust Ratio:** TWR_(N-1) = {tr.motor_out_twr:.2f} ({tr.motor_out_max_thrust_n:.2f} N)",
        "",
        "---",
        "## 4. Electrical Power & Endurance Analysis",
        f"- **Battery Nominal / Usable Energy:** {el.nominal_energy_wh:.2f} Wh nominal / **{el.usable_energy_wh:.2f} Wh usable** ({el.usable_capacity_ah:.2f} Ah usable, {el.reserve_capacity_fraction * 100:.0f}% reserve)",
        f"- **Max Continuous / Burst Battery Current Limit:** {el.max_continuous_discharge_a:.1f} A continuous / {el.max_burst_discharge_a:.1f} A burst",
        f"- **Avionics & Auxiliary Load:** {cfg.airframe.avionics_power_w:.1f} W ({el.operating_state.avionics_current_a:.2f} A)",
    ]

    if el.hover_state:
        lines.append(
            f"- **Hover Equilibrium Regime:** System Current = {el.hover_state.total_system_current_a:.2f} A "
            f"({el.hover_state.per_motor_current_a:.2f} A/motor) | Total Power = {el.hover_state.total_electrical_power_w:.1f} W | "
            f"Effective C-Rate = {el.hover_state.effective_c_rate:.2f}C ({el.hover_state.battery_continuous_utilization_pct:.1f}% of cont limit) | "
            f"Est. Voltage Sag = {el.hover_state.estimated_voltage_sag_v:.2f} V | **Hover Endurance = {el.hover_state.estimated_endurance_min:.1f} min**"
        )
    lines.extend(
        [
            f"- **Operating Regime ({cfg.airframe.operating_throttle_pct:.0f}% Throttle):** System Current = {el.operating_state.total_system_current_a:.2f} A "
            f"({el.operating_state.per_motor_current_a:.2f} A/motor) | Total Power = {el.operating_state.total_electrical_power_w:.1f} W | "
            f"Effective C-Rate = {el.operating_state.effective_c_rate:.2f}C ({el.operating_state.battery_continuous_utilization_pct:.1f}% of cont limit) | "
            f"**Operating Endurance = {el.operating_state.estimated_endurance_min:.1f} min**",
            f"- **Peak Full-Throttle Regime ({tr.max_single_motor_state.throttle_pct:.0f}% Throttle):** System Current = {el.peak_state.total_system_current_a:.2f} A "
            f"({el.peak_state.per_motor_current_a:.2f} A/motor) | Total Power = {el.peak_state.total_electrical_power_w:.1f} W | "
            f"Effective C-Rate = {el.peak_state.effective_c_rate:.2f}C | Full-Throttle Endurance = {el.peak_state.estimated_endurance_min:.1f} min",
            "",
            "---",
            "## 5. Component Compatibility & Engineering Margin Checks",
        ]
    )

    for item in cp.items:
        lines.append(
            f"- **[{item.severity.value}] {item.title}** (`{item.category}`): "
            f"Measured `{item.measured_value_str}` vs Limit `{item.limit_value_str}` (Margin: `{item.margin_str}`). "
            f"{item.explanation}"
        )

    lines.extend(
        [
            "",
            "---",
            "## 6. Data Provenance, Assumptions & Limitations",
            f"- **Dataset ID:** `{ds.dataset_id}`",
            f"- **Data Provenance Classification:** **{ds.provenance.value}**",
            f"- **Source Reference:** {ds.source_reference}",
            f"- **Measurement Conditions:** {ds.measurement_conditions}",
        ]
    )

    for warn in tr.warnings:
        lines.append(f"- **Thrust/Interpolation Note:** {warn}")
    for assumption in el.assumptions:
        lines.append(f"- **Electrical Assumption:** {assumption}")
    lines.append(f"- **Safety Disclaimer:** {cp.engineering_disclaimer}")

    return "\n".join(lines)


def generate_pdf_report(analysis: CompleteConfigurationAnalysis) -> bytes:
    """Generate a formatted downloadable PDF engineering dossier using `fpdf2`."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()

    cfg = analysis.config
    ds = analysis.dataset
    tr = analysis.thrust
    el = analysis.electrical
    cp = analysis.compatibility
    ts_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Header Banner
    pdf.set_fill_color(15, 23, 42)
    pdf.set_text_color(248, 250, 252)
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 10, _ascii_clean("ROTORLAB 1.0 - UAV PROPULSION ENGINEERING DOSSIER"), new_x="LMARGIN", new_y="NEXT", fill=True)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(
        0,
        6,
        _ascii_clean(
            f"Configuration: {cfg.name} ({cfg.config_id}) | Generated: {ts_str} | Status: {cp.overall_status.value}"
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(2)

    def _section_header(title: str) -> None:
        pdf.set_fill_color(226, 232, 240)
        pdf.set_text_color(15, 23, 42)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 7, _ascii_clean(title), new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.set_text_color(30, 41, 59)
        pdf.set_font("Helvetica", "", 9)
        pdf.ln(1)

    def _kv_line(label: str, value: str) -> None:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.cell(58, 5, _ascii_clean(label))
        pdf.set_font("Helvetica", "", 8.5)
        pdf.multi_cell(0, 5, _ascii_clean(value), new_x="LMARGIN", new_y="NEXT")

    # Section 1
    _section_header("1. CONFIGURATION & COMPONENT SPECIFICATIONS")
    _kv_line("Airframe & Rotor Count:", f"{cfg.airframe.frame_type} ({cfg.airframe.num_motors} Motors)")
    _kv_line(
        "Mass Budget:",
        f"Dry: {tr.aircraft_dry_mass_kg:.3f} kg | Payload: {tr.payload_mass_kg:.3f} kg | Total: {tr.total_mass_kg:.3f} kg ({tr.aircraft_weight_n:.2f} N)",
    )
    _kv_line(
        "BLDC Motor:",
        f"{cfg.motor.full_name} | Max Cont: {cfg.motor.max_continuous_current_a:.1f} A, {cfg.motor.max_continuous_power_w:.0f} W | R_int: {cfg.motor.internal_resistance_mohm:.1f} mOhm",
    )
    _kv_line(
        "Propeller:",
        f"{cfg.propeller.manufacturer} {cfg.propeller.model} ({cfg.propeller.diameter_in:g}x{cfg.propeller.pitch_in:g} in, {cfg.propeller.num_blades}-blade {cfg.propeller.material})",
    )
    _kv_line(
        "ESC:",
        f"{cfg.esc.name} | Cont: {cfg.esc.continuous_current_a:.1f} A | Peak: {cfg.esc.peak_current_a:.1f} A ({cfg.esc.min_cells_s}S-{cfg.esc.max_cells_s}S)",
    )
    _kv_line(
        "Battery Pack:",
        f"{cfg.battery.name} ({cfg.battery.cell_count_s}S) | Nom: {cfg.battery.nominal_voltage_v:.1f} V | Op: {cfg.battery.operating_voltage_v:.1f} V | {cfg.battery.capacity_mah:.0f} mAh ({cfg.battery.continuous_c_rating:g}C)",
    )
    pdf.ln(2)

    # Section 2
    _section_header("2. THRUST, HOVER EQUILIBRIUM & TWR ANALYSIS (MODULES B & D)")
    _kv_line(
        "Peak Single-Motor Thrust:",
        f"{tr.max_single_motor_state.thrust_gf:.1f} gf ({tr.max_single_motor_state.thrust_n:.2f} N) @ {tr.max_single_motor_state.throttle_pct:.0f}% Throttle, {tr.max_single_motor_state.rpm:.0f} RPM",
    )
    _kv_line(
        "Max Total Thrust:",
        f"{tr.max_total_thrust_gf:.0f} gf ({tr.max_total_thrust_kgf:.2f} kgf / {tr.max_total_thrust_n:.2f} N)",
    )
    _kv_line(
        "Thrust-to-Weight Ratio (TWR):",
        f"Max TWR = {tr.twr_max:.2f} | Operating TWR ({cfg.airframe.operating_throttle_pct:.0f}% Th) = {tr.twr_operating:.2f}",
    )
    _kv_line(
        "Available Thrust Margin:",
        f"{tr.available_thrust_margin_n:+.2f} N ({tr.available_thrust_margin_gf:+.0f} gf / {tr.available_thrust_margin_pct:+.1f}%)",
    )
    if tr.hover_feasible and tr.hover_single_motor_state and el.hover_state:
        _kv_line(
            "Hover Equilibrium Point:",
            f"{tr.hover_single_motor_state.throttle_pct:.1f}% Throttle | {tr.hover_required_per_motor_gf:.1f} gf/motor | {el.hover_state.total_system_current_a:.2f} A total",
        )
    else:
        _kv_line("Hover Equilibrium Point:", "INFEASIBLE (Aircraft weight exceeds total available thrust)")
    _kv_line(
        "Payload Margins:",
        f"Additional @ Target TWR ({tr.target_twr_used:.1f}): {tr.max_additional_payload_at_target_twr_kg:+.3f} kg | Max Payload @ TWR=1.0: {tr.max_payload_at_twr_1_kg:.3f} kg",
    )
    _kv_line(
        "Rotor Aerodynamics:",
        f"Disk Loading: {tr.disk_loading_kg_m2:.2f} kg/m^2 | Hover v_i: {tr.hover_induced_velocity_m_s:.2f} m/s | Figure of Merit: {tr.figure_of_merit_hover:.3f}",
    )
    pdf.ln(2)

    # Section 3
    _section_header("3. ELECTRICAL POWER & FLIGHT ENDURANCE ANALYSIS (MODULE C)")
    _kv_line(
        "Battery Stored Energy:",
        f"Nominal: {el.nominal_energy_wh:.2f} Wh | Usable ({el.usable_capacity_fraction * 100:.0f}%): {el.usable_energy_wh:.2f} Wh ({el.usable_capacity_ah:.2f} Ah)",
    )
    _kv_line(
        "Battery Current Limits:",
        f"Continuous: {el.max_continuous_discharge_a:.1f} A | Burst: {el.max_burst_discharge_a:.1f} A | Avionics Load: {cfg.airframe.avionics_power_w:.1f} W",
    )
    if el.hover_state:
        _kv_line(
            "Hover Regime Electrical:",
            f"Current: {el.hover_state.total_system_current_a:.2f} A | Power: {el.hover_state.total_electrical_power_w:.1f} W | Endurance: {el.hover_state.estimated_endurance_min:.1f} min",
        )
    _kv_line(
        f"Operating Regime ({cfg.airframe.operating_throttle_pct:.0f}%):",
        f"Current: {el.operating_state.total_system_current_a:.2f} A | Power: {el.operating_state.total_electrical_power_w:.1f} W | Endurance: {el.operating_state.estimated_endurance_min:.1f} min",
    )
    _kv_line(
        f"Peak Regime ({tr.max_single_motor_state.throttle_pct:.0f}%):",
        f"Current: {el.peak_state.total_system_current_a:.2f} A | Power: {el.peak_state.total_electrical_power_w:.1f} W | Endurance: {el.peak_state.estimated_endurance_min:.1f} min",
    )
    pdf.ln(2)

    # Section 4
    _section_header("4. SUBSYSTEM COMPATIBILITY & ENGINEERING MARGINS (MODULE E)")
    for item in cp.items:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.multi_cell(
            0,
            4.8,
            _ascii_clean(
                f"[{item.severity.value}] {item.title} | Measured: {item.measured_value_str} | Limit: {item.limit_value_str} ({item.margin_str})"
            ),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "", 8)
        pdf.multi_cell(0, 4.5, _ascii_clean(f"   -> {item.explanation}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    # Section 5
    _section_header("5. DATA PROVENANCE, ASSUMPTIONS & LIMITATIONS")
    _kv_line("Dataset Provenance:", f"{ds.provenance.value} (ID: {ds.dataset_id})")
    _kv_line("Source Reference:", ds.source_reference)
    _kv_line("Test Conditions:", ds.measurement_conditions)
    for warn in tr.warnings:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "I", 8)
        pdf.multi_cell(0, 4.5, _ascii_clean(f"* Warning: {warn}"), new_x="LMARGIN", new_y="NEXT")
    for assumption in el.assumptions:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "", 8)
        pdf.multi_cell(0, 4.5, _ascii_clean(f"* Assumption: {assumption}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 8)
    pdf.multi_cell(0, 4.5, _ascii_clean(f"Engineering Disclaimer: {cp.engineering_disclaimer}"), new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())


def generate_single_analysis_csv(analysis: CompleteConfigurationAnalysis) -> str:
    """Export the interpolated throttle performance curve and key metrics of a single configuration to CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    cfg = analysis.config
    ds = analysis.dataset

    writer.writerow(["# RotorLab 1.0 - Propulsion Performance Curve Export"])
    writer.writerow(["# Configuration", cfg.name, cfg.config_id])
    writer.writerow(["# Motor", cfg.motor.full_name, "Propeller", cfg.propeller.model])
    writer.writerow(["# Provenance", ds.provenance.value, "Source", ds.source_reference])
    writer.writerow(
        [
            "throttle_pct",
            "single_motor_thrust_gf",
            "single_motor_thrust_n",
            "total_thrust_gf",
            "total_thrust_n",
            "twr",
            "single_motor_current_a",
            "total_system_current_a",
            "single_motor_power_w",
            "total_electrical_power_w",
            "rpm",
            "efficiency_gf_w",
            "tip_speed_m_s",
            "provenance",
        ]
    )

    num_m = cfg.airframe.num_motors
    w_n = analysis.thrust.aircraft_weight_n
    av_i = cfg.airframe.avionics_power_w / cfg.battery.operating_voltage_v

    for st in analysis.throttle_curve_states:
        tot_gf = num_m * st.thrust_gf
        tot_n = num_m * st.thrust_n
        twr_pt = tot_n / w_n if w_n > 0 else 0.0
        tot_i = num_m * st.current_a + av_i
        tot_p = cfg.battery.operating_voltage_v * tot_i
        writer.writerow(
            [
                f"{st.throttle_pct:.2f}",
                f"{st.thrust_gf:.2f}",
                f"{st.thrust_n:.3f}",
                f"{tot_gf:.2f}",
                f"{tot_n:.3f}",
                f"{twr_pt:.3f}",
                f"{st.current_a:.3f}",
                f"{tot_i:.3f}",
                f"{st.power_w:.2f}",
                f"{tot_p:.2f}",
                f"{st.rpm:.1f}",
                f"{st.efficiency_gf_w:.3f}",
                f"{st.tip_speed_m_s:.2f}",
                st.provenance.value,
            ]
        )

    return output.getvalue()


def generate_comparison_csv(rows: List[ComparisonRow]) -> str:
    """Export side-by-side configuration comparison table to CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "config_id",
            "config_name",
            "frame_type",
            "num_motors",
            "motor",
            "propeller",
            "battery",
            "data_provenance",
            "total_mass_kg",
            "payload_mass_kg",
            "max_total_thrust_n",
            "max_total_thrust_gf",
            "twr_max",
            "hover_throttle_pct",
            "hover_current_a",
            "operating_current_a",
            "peak_current_a",
            "operating_power_w",
            "peak_power_w",
            "battery_nominal_energy_wh",
            "usable_energy_wh",
            "hover_endurance_min",
            "operating_endurance_min",
            "max_additional_payload_target_twr_kg",
            "max_payload_twr_1_kg",
            "esc_compatibility_status",
            "esc_margin",
            "overall_compatibility_status",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r.config_id,
                r.config_name,
                r.frame_type,
                r.num_motors,
                r.motor_label,
                r.propeller_label,
                r.battery_label,
                r.provenance_label,
                f"{r.total_mass_kg:.3f}",
                f"{r.payload_mass_kg:.3f}",
                f"{r.max_total_thrust_n:.2f}",
                f"{r.max_total_thrust_gf:.0f}",
                f"{r.twr_max:.2f}",
                f"{r.hover_throttle_pct:.1f}",
                f"{r.hover_current_a:.2f}",
                f"{r.operating_current_a:.2f}",
                f"{r.peak_current_a:.2f}",
                f"{r.operating_power_w:.1f}",
                f"{r.peak_power_w:.1f}",
                f"{r.battery_nominal_energy_wh:.2f}",
                f"{r.usable_energy_wh:.2f}",
                f"{r.hover_endurance_min:.1f}",
                f"{r.operating_endurance_min:.1f}",
                f"{r.max_additional_payload_target_twr_kg:.3f}",
                f"{r.max_payload_twr_1_kg:.3f}",
                r.esc_compatibility_status.value,
                r.esc_margin_str,
                r.overall_compatibility_status.value,
            ]
        )
    return output.getvalue()
