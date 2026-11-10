"""ROTORLAB 1.0 — Professional UAV Propulsion Analysis and Configuration Platform.

Main Streamlit Engineering Workstation Interface.
All mathematical calculations are strictly delegated to `rotorlab.engine` and `rotorlab.services`.
"""

from __future__ import annotations

import uuid
from typing import List

import pandas as pd
import streamlit as st

from rotorlab.data.datasets import parse_csv_performance_dataset
from rotorlab.data.repository import RotorLabRepository
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
    PropulsionConfiguration,
    SeverityLevel,
)
from rotorlab.models.units import (
    ah_to_mah,
    grams_to_kg,
    inches_to_mm,
    kg_to_grams,
    kg_to_lbs,
    lbs_to_kg,
    mah_to_ah,
    mm_to_inches,
)
from rotorlab.reporting.exporter import (
    generate_comparison_csv,
    generate_markdown_report,
    generate_pdf_report,
    generate_single_analysis_csv,
)
from rotorlab.services.analyzer import (
    CompleteConfigurationAnalysis,
    compare_configurations,
    evaluate_configuration,
)
from rotorlab.ui.charts import (
    build_battery_utilisation_chart,
    build_configuration_comparison_chart,
    build_current_vs_throttle_chart,
    build_payload_tradeoff_chart,
    build_power_vs_throttle_chart,
    build_thrust_vs_throttle_chart,
)

st.set_page_config(
    page_title="RotorLab 1.0 | UAV Propulsion Engineering Workstation",
    page_icon="🛸",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Professional Dark Aerospace Workstation Styling
st.markdown(
    """
    <style>
    .stApp {
        background-color: #0B0F19;
        color: #F3F4F6;
    }
    .workstation-header {
        background: linear-gradient(90deg, #0F172A 0%, #1E293B 100%);
        border: 1px solid #334155;
        border-left: 4px solid #38BDF8;
        padding: 16px 22px;
        border-radius: 6px;
        margin-bottom: 18px;
    }
    .workstation-title {
        font-size: 1.55rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        color: #F8FAFC;
        margin: 0;
    }
    .workstation-subtitle {
        font-size: 0.88rem;
        color: #94A3B8;
        margin-top: 4px;
    }
    .metric-card {
        background-color: #111827;
        border: 1px solid #1E293B;
        border-radius: 6px;
        padding: 14px 16px;
        margin-bottom: 10px;
    }
    .metric-label {
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #94A3B8;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 1.45rem;
        font-weight: 700;
        color: #F8FAFC;
    }
    .metric-sub {
        font-size: 0.78rem;
        color: #38BDF8;
        margin-top: 2px;
    }
    .badge-pass {
        background-color: rgba(16, 185, 129, 0.15);
        color: #34D399;
        border: 1px solid #059669;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-warn {
        background-color: rgba(245, 158, 11, 0.15);
        color: #FBBF24;
        border: 1px solid #D97706;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-crit {
        background-color: rgba(244, 63, 94, 0.15);
        color: #FB7185;
        border: 1px solid #E11D48;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-info {
        background-color: rgba(56, 189, 248, 0.15);
        color: #38BDF8;
        border: 1px solid #0284C7;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_repo() -> RotorLabRepository:
    return RotorLabRepository("rotorlab_workspace.db")


def _severity_badge_html(sev: SeverityLevel) -> str:
    if sev == SeverityLevel.PASS:
        return "<span class='badge-pass'>PASS</span>"
    if sev == SeverityLevel.WARNING:
        return "<span class='badge-warn'>WARNING</span>"
    if sev == SeverityLevel.CRITICAL:
        return "<span class='badge-crit'>CRITICAL</span>"
    return "<span class='badge-info'>INFO</span>"


def _render_metric_card(label: str, value: str, sub: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    repo = get_repo()
    all_configs = repo.list_configurations()
    all_datasets = repo.list_all_datasets()
    datasets_by_id = {d.dataset_id: d for d in all_datasets}

    # Initialize session state
    if "active_config_id" not in st.session_state or st.session_state["active_config_id"] not in {
        c.config_id for c in all_configs
    }:
        st.session_state["active_config_id"] = all_configs[0].config_id

    # Sidebar — Configuration Management & Unit Preferences
    with st.sidebar:
        st.markdown("### 🛸 ROTORLAB 1.0")
        st.caption("Deterministic UAV Propulsion Analysis & Configuration Workstation")
        st.divider()

        st.markdown("#### 1. Active Configuration")
        config_options = {c.config_id: f"{c.name}" for c in all_configs}
        selected_cfg_id = st.selectbox(
            "Select Saved Configuration",
            options=list(config_options.keys()),
            format_func=lambda cid: config_options[cid],
            index=list(config_options.keys()).index(st.session_state["active_config_id"]),
        )
        if selected_cfg_id != st.session_state["active_config_id"]:
            st.session_state["active_config_id"] = selected_cfg_id
            st.rerun()

        active_cfg = repo.get_configuration(st.session_state["active_config_id"])
        if active_cfg is None:
            active_cfg = all_configs[0]

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if st.button("Duplicate", width="stretch"):
                dup = repo.duplicate_configuration(active_cfg.config_id)
                st.session_state["active_config_id"] = dup.config_id
                st.toast(f"Duplicated as '{dup.name}'")
                st.rerun()
        with col_s2:
            can_delete = len(all_configs) > 1
            if st.button("Delete", width="stretch", disabled=not can_delete):
                repo.delete_configuration(active_cfg.config_id)
                remaining = repo.list_configurations()
                st.session_state["active_config_id"] = remaining[0].config_id
                st.toast("Configuration deleted.")
                st.rerun()

        st.divider()
        st.markdown("#### 2. Display Unit System")
        mass_unit = st.selectbox("Mass Input/Display Unit", ["kg", "g", "lb"], index=0)
        prop_unit = st.selectbox("Propeller Dimension Unit", ["inch", "mm"], index=0)
        cap_unit = st.selectbox("Battery Capacity Unit", ["mAh", "Ah"], index=0)

        st.divider()
        st.markdown("#### 3. Active Dataset Provenance")
        active_ds = datasets_by_id.get(active_cfg.dataset_id, all_datasets[0])
        st.info(
            f"**{active_ds.provenance.value}**\n\n"
            f"Motor: `{active_ds.motor_manufacturer} {active_ds.motor_model} KV{active_ds.motor_kv:.0f}`\n\n"
            f"Prop: `{active_ds.propeller_diameter_in:g}x{active_ds.propeller_pitch_in:g}\"` @ `{active_ds.test_voltage_v:g} V`"
        )

    # Evaluate active configuration through deterministic engine
    analysis: CompleteConfigurationAnalysis = evaluate_configuration(active_cfg, active_ds)
    tr = analysis.thrust
    el = analysis.electrical
    cp = analysis.compatibility

    # Top Workstation Header
    st.markdown(
        f"""
        <div class="workstation-header">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <p class="workstation-title">ROTORLAB // PROPULSION ENGINEERING WORKSTATION</p>
                    <p class="workstation-subtitle">
                        Active Architecture: <b>{active_cfg.name}</b> ({active_cfg.airframe.frame_type}, {active_cfg.airframe.num_motors} Motors)
                        &nbsp;|&nbsp; Dataset Provenance: <b>{active_ds.provenance.value}</b>
                    </p>
                </div>
                <div>
                    {_severity_badge_html(cp.overall_status)}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Top-level Key Engineering Metrics Bar
    kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)
    with kpi1:
        _render_metric_card(
            "Max Total Thrust",
            f"{tr.max_total_thrust_n:.1f} N",
            f"{tr.max_total_thrust_gf:.0f} gf ({tr.max_total_thrust_kgf:.2f} kgf)",
        )
    with kpi2:
        _render_metric_card(
            "Aircraft Weight (SI)",
            f"{tr.aircraft_weight_n:.1f} N",
            f"Total Mass: {tr.total_mass_kg:.2f} kg ({tr.payload_mass_kg:.2f} kg payload)",
        )
    with kpi3:
        _render_metric_card(
            "Max Thrust-to-Weight",
            f"{tr.twr_max:.2f} : 1",
            f"Margin: {tr.available_thrust_margin_n:+.1f} N ({tr.available_thrust_margin_pct:+.0f}%)",
        )
    with kpi4:
        if tr.hover_feasible and tr.hover_single_motor_state and el.hover_state:
            _render_metric_card(
                "Hover Equilibrium",
                f"{tr.hover_single_motor_state.throttle_pct:.1f}% Th",
                f"{el.hover_state.total_system_current_a:.1f} A | {el.hover_state.total_electrical_power_w:.0f} W",
            )
        else:
            _render_metric_card("Hover Equilibrium", "INFEASIBLE", "Thrust < Weight")
    with kpi5:
        hover_end_str = (
            f"{el.hover_state.estimated_endurance_min:.1f} min"
            if el.hover_state is not None
            else "0.0 min"
        )
        _render_metric_card(
            "Est. Hover Endurance",
            hover_end_str,
            f"Op ({active_cfg.airframe.operating_throttle_pct:.0f}% Th): {el.operating_state.estimated_endurance_min:.1f} min",
        )
    with kpi6:
        _render_metric_card(
            "Usable Battery Energy",
            f"{el.usable_energy_wh:.1f} Wh",
            f"Nominal: {el.nominal_energy_wh:.1f} Wh ({el.usable_capacity_fraction*100:.0f}% DoD)",
        )

    # Structured Workstation Navigation Tabs
    tabs = st.tabs(
        [
            "⚙️ A. Configuration & Datasets",
            "🚀 B & D. Thrust, TWR & Aerodynamics",
            "⚡ C. Electrical & Battery Analysis",
            "🛡️ E. Compatibility & Margins",
            "📊 G. Interactive Visualisations",
            "⚖️ F. Configuration Comparison",
            "📄 H. Engineering Reports",
        ]
    )

    # =========================================================================
    # TAB 1: MODULE A — PROPULSION CONFIGURATION & DATASET MANAGEMENT
    # =========================================================================
    with tabs[0]:
        st.subheader("Module A — Multirotor Propulsion Configuration Editor")
        st.caption(
            "Configure airframe mass, BLDC motors, propellers, ESCs, battery pack, and engineering margins. "
            "All inputs are converted to strict SI units before analysis."
        )

        with st.form("propulsion_config_form"):
            c_meta1, c_meta2 = st.columns([1, 2])
            with c_meta1:
                cfg_name = st.text_input("Configuration Name", value=active_cfg.name)
            with c_meta2:
                cfg_desc = st.text_input("Engineering Description", value=active_cfg.description)

            ds_select_id = st.selectbox(
                "Empirical / Reference Motor-Propeller Performance Dataset",
                options=list(datasets_by_id.keys()),
                format_func=lambda did: datasets_by_id[did].display_label,
                index=list(datasets_by_id.keys()).index(active_cfg.dataset_id)
                if active_cfg.dataset_id in datasets_by_id
                else 0,
                help=(
                    "Accurate motor thrust cannot be calculated from KV and propeller dimensions alone. "
                    "Select a verified manufacturer dataset, user-measured dataset, or labelled synthetic dataset."
                ),
            )

            st.markdown("##### 1. Airframe, Mass Budget & Mission Environment")
            af1, af2, af3, af4, af5 = st.columns(5)
            with af1:
                frame_types = [
                    "Quadcopter (X4)",
                    "Hexacopter (X6)",
                    "Octocopter (X8)",
                    "Coaxial Octocopter (X8 Coax)",
                    "Tricopter (Y3)",
                    "Coaxial Hexacopter (Y6)",
                ]
                frame_idx = (
                    frame_types.index(active_cfg.airframe.frame_type)
                    if active_cfg.airframe.frame_type in frame_types
                    else 0
                )
                frame_type_in = st.selectbox("Airframe Topology", options=frame_types, index=frame_idx)
            with af2:
                num_motors_in = int(
                    st.number_input(
                        "Number of Motors",
                        min_value=1,
                        max_value=32,
                        value=int(active_cfg.airframe.num_motors),
                        step=1,
                    )
                )
            with af3:
                if mass_unit == "kg":
                    dry_default = active_cfg.airframe.aircraft_dry_mass_kg
                elif mass_unit == "g":
                    dry_default = kg_to_grams(active_cfg.airframe.aircraft_dry_mass_kg)
                else:
                    dry_default = kg_to_lbs(active_cfg.airframe.aircraft_dry_mass_kg)
                dry_mass_raw = float(
                    st.number_input(
                        f"Aircraft Dry Mass [{mass_unit}]",
                        min_value=0.01,
                        value=float(round(dry_default, 3)),
                        step=0.05 if mass_unit != "g" else 50.0,
                    )
                )
            with af4:
                if mass_unit == "kg":
                    pl_default = active_cfg.airframe.payload_mass_kg
                elif mass_unit == "g":
                    pl_default = kg_to_grams(active_cfg.airframe.payload_mass_kg)
                else:
                    pl_default = kg_to_lbs(active_cfg.airframe.payload_mass_kg)
                payload_mass_raw = float(
                    st.number_input(
                        f"Payload Mass [{mass_unit}]",
                        min_value=0.0,
                        value=float(round(pl_default, 3)),
                        step=0.05 if mass_unit != "g" else 50.0,
                    )
                )
            with af5:
                op_throttle_in = float(
                    st.number_input(
                        "Operating Throttle [%]",
                        min_value=10.0,
                        max_value=100.0,
                        value=float(active_cfg.airframe.operating_throttle_pct),
                        step=5.0,
                    )
                )

            env1, env2, env3 = st.columns(3)
            with env1:
                avionics_w_in = float(
                    st.number_input(
                        "Avionics & Auxiliary Power [W]",
                        min_value=0.0,
                        max_value=500.0,
                        value=float(active_cfg.airframe.avionics_power_w),
                        step=1.0,
                    )
                )
            with env2:
                alt_m_in = float(
                    st.number_input(
                        "Operating Altitude MSL [m]",
                        min_value=-200.0,
                        max_value=10000.0,
                        value=float(active_cfg.airframe.altitude_m),
                        step=100.0,
                    )
                )
            with env3:
                temp_off_in = float(
                    st.number_input(
                        "ISA Temperature Offset [°C]",
                        min_value=-40.0,
                        max_value=50.0,
                        value=float(active_cfg.airframe.temp_offset_c),
                        step=1.0,
                    )
                )

            st.markdown("##### 2. BLDC Motor & Propeller Specifications")
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            with m1:
                m_mfg = st.text_input("Motor Manufacturer", value=active_cfg.motor.manufacturer)
            with m2:
                m_mod = st.text_input("Motor Model", value=active_cfg.motor.model)
            with m3:
                m_kv = float(
                    st.number_input(
                        "Motor KV [RPM/V]",
                        min_value=50.0,
                        max_value=15000.0,
                        value=float(active_cfg.motor.kv_rating),
                        step=10.0,
                    )
                )
            with m4:
                m_max_i = float(
                    st.number_input(
                        "Motor Max Cont Current [A]",
                        min_value=1.0,
                        max_value=300.0,
                        value=float(active_cfg.motor.max_continuous_current_a),
                        step=1.0,
                    )
                )
            with m5:
                m_max_p = float(
                    st.number_input(
                        "Motor Max Cont Power [W]",
                        min_value=10.0,
                        max_value=10000.0,
                        value=float(active_cfg.motor.max_continuous_power_w),
                        step=10.0,
                    )
                )
            with m6:
                m_rint = float(
                    st.number_input(
                        "Internal Resistance [mΩ]",
                        min_value=1.0,
                        max_value=2000.0,
                        value=float(active_cfg.motor.internal_resistance_mohm),
                        step=5.0,
                    )
                )

            p1, p2, p3, p4, p5, p6 = st.columns(6)
            with p1:
                p_mfg = st.text_input("Propeller Brand", value=active_cfg.propeller.manufacturer)
            with p2:
                p_mod = st.text_input("Propeller Model", value=active_cfg.propeller.model)
            with p3:
                diam_default = (
                    active_cfg.propeller.diameter_in
                    if prop_unit == "inch"
                    else inches_to_mm(active_cfg.propeller.diameter_in)
                )
                p_diam_raw = float(
                    st.number_input(
                        f"Prop Diameter [{prop_unit}]",
                        min_value=1.0,
                        max_value=2000.0,
                        value=float(round(diam_default, 2)),
                        step=0.5 if prop_unit == "inch" else 10.0,
                    )
                )
            with p4:
                pitch_default = (
                    active_cfg.propeller.pitch_in
                    if prop_unit == "inch"
                    else inches_to_mm(active_cfg.propeller.pitch_in)
                )
                p_pitch_raw = float(
                    st.number_input(
                        f"Prop Pitch [{prop_unit}]",
                        min_value=0.5,
                        max_value=1000.0,
                        value=float(round(pitch_default, 2)),
                        step=0.2 if prop_unit == "inch" else 5.0,
                    )
                )
            with p5:
                m_min_s = int(
                    st.number_input(
                        "Motor Min Cells [S]",
                        min_value=1,
                        max_value=24,
                        value=int(active_cfg.motor.min_cells_s),
                    )
                )
            with p6:
                m_max_s = int(
                    st.number_input(
                        "Motor Max Cells [S]",
                        min_value=1,
                        max_value=24,
                        value=int(active_cfg.motor.max_cells_s),
                    )
                )

            st.markdown("##### 3. Electronic Speed Controller (ESC) & Flight Battery")
            e1, e2, e3, e4, e5 = st.columns(5)
            with e1:
                esc_name = st.text_input("ESC Model", value=active_cfg.esc.name)
            with e2:
                esc_cont_a = float(
                    st.number_input(
                        "ESC Continuous Rating [A]",
                        min_value=1.0,
                        max_value=400.0,
                        value=float(active_cfg.esc.continuous_current_a),
                        step=5.0,
                    )
                )
            with e3:
                esc_peak_a = float(
                    st.number_input(
                        "ESC Burst/Peak Rating [A]",
                        min_value=1.0,
                        max_value=600.0,
                        value=float(active_cfg.esc.peak_current_a),
                        step=5.0,
                    )
                )
            with e4:
                esc_min_s = int(
                    st.number_input(
                        "ESC Min Cells [S]",
                        min_value=1,
                        max_value=24,
                        value=int(active_cfg.esc.min_cells_s),
                    )
                )
            with e5:
                esc_max_s = int(
                    st.number_input(
                        "ESC Max Cells [S]",
                        min_value=1,
                        max_value=24,
                        value=int(active_cfg.esc.max_cells_s),
                    )
                )

            b1, b2, b3, b4, b5, b6, b7 = st.columns(7)
            with b1:
                batt_name = st.text_input("Battery Pack Name", value=active_cfg.battery.name)
            with b2:
                batt_s = int(
                    st.number_input(
                        "Series Cells [S]",
                        min_value=1,
                        max_value=24,
                        value=int(active_cfg.battery.cell_count_s),
                    )
                )
            with b3:
                batt_nom_v = float(
                    st.number_input(
                        "Nominal Voltage [V]",
                        min_value=3.0,
                        max_value=120.0,
                        value=float(active_cfg.battery.nominal_voltage_v),
                        step=0.1,
                    )
                )
            with b4:
                batt_op_v = float(
                    st.number_input(
                        "Operating Voltage [V]",
                        min_value=3.0,
                        max_value=120.0,
                        value=float(active_cfg.battery.operating_voltage_v),
                        step=0.1,
                    )
                )
            with b5:
                cap_default = (
                    active_cfg.battery.capacity_mah
                    if cap_unit == "mAh"
                    else mah_to_ah(active_cfg.battery.capacity_mah)
                )
                batt_cap_raw = float(
                    st.number_input(
                        f"Capacity [{cap_unit}]",
                        min_value=0.1,
                        max_value=200000.0,
                        value=float(round(cap_default, 2)),
                        step=500.0 if cap_unit == "mAh" else 0.5,
                    )
                )
            with b6:
                batt_c_cont = float(
                    st.number_input(
                        "Discharge Rating [C]",
                        min_value=1.0,
                        max_value=200.0,
                        value=float(active_cfg.battery.continuous_c_rating),
                        step=5.0,
                    )
                )
            with b7:
                batt_usable_pct = float(
                    st.number_input(
                        "Usable Cap [%]",
                        min_value=20.0,
                        max_value=100.0,
                        value=float(active_cfg.battery.usable_capacity_fraction * 100.0),
                        step=5.0,
                    )
                )

            st.markdown("##### 4. Configurable Engineering Margins")
            mg1, mg2, mg3, mg4 = st.columns(4)
            with mg1:
                esc_sf_in = float(
                    st.number_input(
                        "ESC Safety Factor (x Peak Motor I)",
                        min_value=1.0,
                        max_value=3.0,
                        value=float(active_cfg.margins.esc_current_safety_factor),
                        step=0.05,
                    )
                )
            with mg2:
                min_twr_in = float(
                    st.number_input(
                        "Minimum Hover TWR Threshold",
                        min_value=1.05,
                        max_value=3.0,
                        value=float(active_cfg.margins.min_hover_twr),
                        step=0.1,
                    )
                )
            with mg3:
                rec_twr_in = float(
                    st.number_input(
                        "Target Design TWR (Agile/Margin)",
                        min_value=1.2,
                        max_value=5.0,
                        value=float(active_cfg.margins.recommended_agile_twr),
                        step=0.1,
                    )
                )
            with mg4:
                v_tol_in = float(
                    st.number_input(
                        "Dataset Voltage Mismatch Tol [%]",
                        min_value=1.0,
                        max_value=30.0,
                        value=float(active_cfg.margins.voltage_mismatch_tolerance_pct),
                        step=1.0,
                    )
                )

            btn_save, btn_save_new = st.columns(2)
            with btn_save:
                save_clicked = st.form_submit_button(
                    "💾 Save & Update Active Configuration", width="stretch"
                )
            with btn_save_new:
                save_new_clicked = st.form_submit_button(
                    "➕ Save as New Configuration", width="stretch"
                )

            if save_clicked or save_new_clicked:
                try:
                    # Convert user unit inputs back to internal canonical units
                    if mass_unit == "kg":
                        dry_kg = dry_mass_raw
                        pl_kg = payload_mass_raw
                    elif mass_unit == "g":
                        dry_kg = grams_to_kg(dry_mass_raw)
                        pl_kg = grams_to_kg(payload_mass_raw)
                    else:
                        dry_kg = lbs_to_kg(dry_mass_raw)
                        pl_kg = lbs_to_kg(payload_mass_raw)

                    diam_in = p_diam_raw if prop_unit == "inch" else mm_to_inches(p_diam_raw)
                    pitch_in = p_pitch_raw if prop_unit == "inch" else mm_to_inches(p_pitch_raw)
                    cap_mah = batt_cap_raw if cap_unit == "mAh" else ah_to_mah(batt_cap_raw)

                    target_id = (
                        f"cfg_{uuid.uuid4().hex[:8]}" if save_new_clicked else active_cfg.config_id
                    )
                    target_name = (
                        f"{cfg_name} (New)"
                        if (save_new_clicked and cfg_name == active_cfg.name)
                        else cfg_name
                    )

                    updated_cfg = PropulsionConfiguration(
                        config_id=target_id,
                        name=target_name,
                        description=cfg_desc,
                        motor=MotorSpec(
                            manufacturer=m_mfg,
                            model=m_mod,
                            kv_rating=m_kv,
                            max_continuous_current_a=m_max_i,
                            max_continuous_power_w=m_max_p,
                            internal_resistance_mohm=m_rint,
                            no_load_current_a=active_cfg.motor.no_load_current_a,
                            min_cells_s=m_min_s,
                            max_cells_s=m_max_s,
                            mass_g=active_cfg.motor.mass_g,
                        ),
                        propeller=PropellerSpec(
                            manufacturer=p_mfg,
                            model=p_mod,
                            diameter_in=diam_in,
                            pitch_in=pitch_in,
                            num_blades=active_cfg.propeller.num_blades,
                            material=active_cfg.propeller.material,
                            mass_g=active_cfg.propeller.mass_g,
                        ),
                        esc=ESCSpec(
                            name=esc_name,
                            continuous_current_a=esc_cont_a,
                            peak_current_a=max(esc_cont_a, esc_peak_a),
                            min_cells_s=esc_min_s,
                            max_cells_s=esc_max_s,
                            mass_g=active_cfg.esc.mass_g,
                        ),
                        battery=BatterySpec(
                            name=batt_name,
                            cell_count_s=batt_s,
                            nominal_voltage_v=batt_nom_v,
                            operating_voltage_v=batt_op_v,
                            capacity_mah=cap_mah,
                            continuous_c_rating=batt_c_cont,
                            burst_c_rating=max(batt_c_cont, active_cfg.battery.burst_c_rating),
                            usable_capacity_fraction=batt_usable_pct / 100.0,
                            internal_resistance_per_cell_mohm=active_cfg.battery.internal_resistance_per_cell_mohm,
                            mass_g=active_cfg.battery.mass_g,
                        ),
                        airframe=AirframeSpec(
                            frame_type=frame_type_in,
                            num_motors=num_motors_in,
                            aircraft_dry_mass_kg=dry_kg,
                            payload_mass_kg=pl_kg,
                            avionics_power_w=avionics_w_in,
                            operating_throttle_pct=op_throttle_in,
                            altitude_m=alt_m_in,
                            temp_offset_c=temp_off_in,
                        ),
                        dataset_id=ds_select_id,
                        margins=EngineeringMargins(
                            esc_current_safety_factor=esc_sf_in,
                            min_hover_twr=min_twr_in,
                            recommended_agile_twr=max(min_twr_in, rec_twr_in),
                            voltage_mismatch_tolerance_pct=v_tol_in,
                        ),
                    )
                    repo.save_configuration(updated_cfg)
                    st.session_state["active_config_id"] = updated_cfg.config_id
                    st.success(f"Configuration '{updated_cfg.name}' validated and saved to SQLite.")
                    st.rerun()
                except ValueError as err:
                    st.error(f"Input Validation Error: {err}")

        st.divider()
        st.subheader("Empirical Performance Dataset Inspector & CSV Importer")
        col_ds_view, col_ds_import = st.columns([1.2, 1])

        with col_ds_view:
            st.markdown(f"**Active Dataset:** `{active_ds.display_label}`")
            st.caption(
                f"**Source:** {active_ds.source_reference}  \n"
                f"**Conditions:** {active_ds.measurement_conditions}"
            )
            pts_df = pd.DataFrame(
                [
                    {
                        "Throttle [%]": p.throttle_pct,
                        "Voltage [V]": p.voltage_v,
                        "Current [A]": p.current_a,
                        "Thrust [gf]": p.thrust_gf,
                        "Power [W]": p.power_w,
                        "RPM": p.rpm,
                        "Efficacy [gf/W]": round(p.efficiency_gf_w, 2),
                    }
                    for p in active_ds.points
                ]
            )
            st.dataframe(pts_df, width="stretch", hide_index=True)

        with col_ds_import:
            st.markdown("**Import Custom Motor-Propeller Dataset (CSV)**")
            st.caption(
                "Upload a thrust-stand CSV (`throttle_pct, voltage_v, current_a, thrust_gf, power_w, rpm`) "
                "or paste CSV rows below. Samples are available in `datasets/`."
            )
            uploaded_csv = st.file_uploader("Upload CSV File", type=["csv"])
            ic1, ic2, ic3 = st.columns(3)
            with ic1:
                imp_mfg = st.text_input("Dataset Motor Brand", value=active_cfg.motor.manufacturer)
                imp_prop_d = st.number_input("Dataset Prop Diam [in]", value=float(active_cfg.propeller.diameter_in))
            with ic2:
                imp_mod = st.text_input("Dataset Motor Model", value=active_cfg.motor.model)
                imp_prop_p = st.number_input("Dataset Prop Pitch [in]", value=float(active_cfg.propeller.pitch_in))
            with ic3:
                imp_kv = st.number_input("Dataset Motor KV", value=float(active_cfg.motor.kv_rating))
                imp_v = st.number_input("Dataset Test Voltage [V]", value=float(active_cfg.battery.operating_voltage_v))

            imp_prov = st.selectbox(
                "Data Provenance Classification",
                options=[
                    DataProvenance.USER_MEASURED,
                    DataProvenance.MANUFACTURER_DATASHEET,
                    DataProvenance.ILLUSTRATIVE_SYNTHETIC,
                ],
                format_func=lambda p: p.value,
            )
            imp_src = st.text_input("Source / Test Bench Reference", value="User Dynamometer / Static Thrust Stand")
            default_csv_text = (
                "throttle_pct,voltage_v,current_a,thrust_gf,power_w,rpm\n"
                "40,14.8,1.9,340,28.12,4200\n"
                "50,14.8,3.1,490,45.88,5100\n"
                "65,14.8,5.9,760,87.32,6400\n"
                "75,14.8,8.4,970,124.32,7400\n"
                "85,14.8,11.5,1210,170.20,8100\n"
                "100,14.8,14.2,1430,210.16,8750"
            )
            csv_text_area = st.text_area("Or Paste CSV Data Directly", value=default_csv_text, height=130)

            if st.button("📥 Validate & Register Dataset", width="stretch"):
                raw_csv = (
                    uploaded_csv.getvalue().decode("utf-8")
                    if uploaded_csv is not None
                    else csv_text_area
                )
                try:
                    new_ds_id = f"custom_{uuid.uuid4().hex[:8]}"
                    parsed_ds = parse_csv_performance_dataset(
                        csv_content=raw_csv,
                        dataset_id=new_ds_id,
                        motor_manufacturer=imp_mfg,
                        motor_model=imp_mod,
                        motor_kv=float(imp_kv),
                        propeller_model=f"{imp_prop_d:g}x{imp_prop_p:g}",
                        propeller_diameter_in=float(imp_prop_d),
                        propeller_pitch_in=float(imp_prop_p),
                        test_voltage_v=float(imp_v),
                        provenance=imp_prov,
                        source_reference=imp_src,
                    )
                    repo.save_custom_dataset(parsed_ds)
                    st.success(f"Registered dataset '{parsed_ds.display_label}'!")
                    st.rerun()
                except ValueError as err:
                    st.error(f"CSV Validation Error: {err}")

    # =========================================================================
    # TAB 2: MODULE B & D — THRUST, TWR & AERODYNAMIC ANALYSIS
    # =========================================================================
    with tabs[1]:
        st.subheader("Modules B & D — Thrust, Hover Equilibrium & Thrust-to-Weight Analysis")

        for w_msg in tr.warnings:
            st.warning(f"**Dataset / Interpolation Notice:** {w_msg}")

        col_b1, col_b2, col_b3 = st.columns(3)
        with col_b1:
            st.markdown("##### Peak & Operating Static Thrust")
            st.write(
                f"- **Single Motor Peak Thrust ({tr.max_single_motor_state.throttle_pct:.0f}% Th):** "
                f"`{tr.max_single_motor_state.thrust_gf:.1f} gf` (`{tr.max_single_motor_state.thrust_n:.2f} N`)"
            )
            st.write(
                f"- **Total Peak Thrust ({active_cfg.airframe.num_motors} Motors):** "
                f"`{tr.max_total_thrust_gf:.0f} gf` (`{tr.max_total_thrust_n:.2f} N` / `{tr.max_total_thrust_kgf:.2f} kgf`)"
            )
            st.write(
                f"- **Single Motor Operating Thrust ({active_cfg.airframe.operating_throttle_pct:.0f}% Th):** "
                f"`{tr.operating_single_motor_state.thrust_gf:.1f} gf` (`{tr.operating_single_motor_state.thrust_n:.2f} N`)"
            )
            st.write(
                f"- **Total Operating Thrust:** "
                f"`{tr.operating_total_thrust_gf:.0f} gf` (`{tr.operating_total_thrust_n:.2f} N`)"
            )
            st.write(
                f"- **Peak Propeller RPM & Tip Speed:** "
                f"`{tr.max_single_motor_state.rpm:.0f} RPM` (`{tr.max_single_motor_state.tip_speed_m_s:.1f} m/s`)"
            )

        with col_b2:
            st.markdown("##### Weight, TWR & Payload Margins (SI)")
            st.write(
                f"- **Aircraft Dry Mass:** `{tr.aircraft_dry_mass_kg:.3f} kg` "
                f"| **Payload:** `{tr.payload_mass_kg:.3f} kg`"
            )
            st.write(
                f"- **Total All-Up Mass & Weight:** `{tr.total_mass_kg:.3f} kg` "
                f"(`{tr.aircraft_weight_n:.2f} N` / `{tr.aircraft_weight_gf:.0f} gf`)"
            )
            st.write(f"- **Maximum TWR ($T_{{\\text{{max}}}} / W$):** **`{tr.twr_max:.2f}`**")
            st.write(f"- **Operating TWR ($T_{{\\text{{op}}}} / W$):** `{tr.twr_operating:.2f}`")
            st.write(
                f"- **Available Thrust Margin:** `{tr.available_thrust_margin_n:+.2f} N` "
                f"(`{tr.available_thrust_margin_gf:+.0f} gf` / `{tr.available_thrust_margin_pct:+.1f}%`)"
            )
            st.write(
                f"- **Additional Payload Margin (at Target TWR = {tr.target_twr_used:.2f}):** "
                f"`{tr.max_additional_payload_at_target_twr_kg:+.3f} kg`"
            )
            st.write(
                f"- **Absolute Static Lift Ceiling Payload (TWR = 1.0):** "
                f"`{tr.max_payload_at_twr_1_kg:.3f} kg`"
            )

        with col_b3:
            st.markdown("##### Hover Equilibrium & Actuator Disk Physics")
            if tr.hover_feasible and tr.hover_single_motor_state:
                st.write(
                    f"- **Hover Throttle Command:** **`{tr.hover_single_motor_state.throttle_pct:.1f}%`** "
                    f"(`{tr.hover_single_motor_state.provenance.value}`)"
                )
                st.write(
                    f"- **Hover Thrust per Motor:** `{tr.hover_required_per_motor_gf:.1f} gf` "
                    f"(`{tr.hover_required_per_motor_n:.2f} N`)"
                )
                st.write(
                    f"- **Hover RPM & Efficacy:** `{tr.hover_single_motor_state.rpm:.0f} RPM` | "
                    f"`{tr.hover_single_motor_state.efficiency_gf_w:.2f} gf/W`"
                )
            else:
                st.error("Hover Equilibrium Infeasible: Required thrust exceeds maximum motor thrust.")
            st.write(
                f"- **ISA Air Density ($\\rho$):** `{tr.air_density_kg_m3:.4f} kg/m³` "
                f"Total Disk Area: `{tr.total_disk_area_m2:.4f} m²`"
            )
            st.write(
                f"- **Rotor Disk Loading:** `{tr.disk_loading_kg_m2:.2f} kg/m²` "
                f"(`{tr.disk_loading_n_m2:.1f} N/m²`)"
            )
            st.write(
                f"- **Hover Induced Velocity ($v_i$):** `{tr.hover_induced_velocity_m_s:.2f} m/s` | "
                f"**Figure of Merit ($FM$):** `{tr.figure_of_merit_hover:.3f}`"
            )
            st.write(
                f"- **Motor-Out ($N-1$) Static TWR:** `{tr.motor_out_twr:.2f}` "
                f"(`{tr.motor_out_max_thrust_n:.1f} N`)"
            )

        st.divider()
        st.markdown("##### Interactive Throttle Interpolation Calculator")
        custom_th = st.slider(
            "Probe Any Throttle Percentage [%]",
            min_value=0.0,
            max_value=100.0,
            value=float(active_cfg.airframe.operating_throttle_pct),
            step=1.0,
        )
        from rotorlab.engine.thrust import interpolate_at_throttle

        probed_state = interpolate_at_throttle(active_ds, active_cfg.propeller, custom_th)
        if probed_state.extrapolation_warning:
            st.warning(probed_state.extrapolation_warning)

        pr1, pr2, pr3, pr4, pr5 = st.columns(5)
        pr1.metric("Single Motor Thrust", f"{probed_state.thrust_gf:.1f} gf", f"{probed_state.thrust_n:.2f} N")
        pr2.metric(
            "Total Propulsion Thrust",
            f"{active_cfg.airframe.num_motors * probed_state.thrust_gf:.0f} gf",
            f"TWR: {(active_cfg.airframe.num_motors * probed_state.thrust_n) / tr.aircraft_weight_n:.2f}",
        )
        pr3.metric("Single Motor Current", f"{probed_state.current_a:.2f} A", f"Power: {probed_state.power_w:.1f} W")
        pr4.metric("Rotational Speed", f"{probed_state.rpm:.0f} RPM", f"Tip: {probed_state.tip_speed_m_s:.1f} m/s")
        pr5.metric("Specific Efficacy", f"{probed_state.efficiency_gf_w:.2f} gf/W", probed_state.provenance.value)

    # =========================================================================
    # TAB 3: MODULE C — ELECTRICAL & BATTERY ANALYSIS
    # =========================================================================
    with tabs[2]:
        st.subheader("Module C — Electrical Power, C-Rate Utilisation & Flight Endurance")
        st.caption(
            "Dimensionally consistent electrical analysis: "
            "$E\\,(\\text{Wh}) = V\\,(\\text{V}) \\times C\\,(\\text{Ah})$, "
            "$P\\,(\\text{W}) = V\\,(\\text{V}) \\times I\\,(\\text{A})$, "
            "$\\text{Time}\\,(\\text{min}) = (C_{\\text{usable}}\\,(\\text{Ah}) / I_{\\text{avg}}\\,(\\text{A})) \\times 60$."
        )

        el_c1, el_c2, el_c3, el_c4 = st.columns(4)
        el_c1.metric(
            "Nominal Stored Energy",
            f"{el.nominal_energy_wh:.2f} Wh",
            f"{el.nominal_voltage_v:.1f} V × {el.capacity_ah:.2f} Ah",
        )
        el_c2.metric(
            "Usable Flight Energy",
            f"{el.usable_energy_wh:.2f} Wh",
            f"{el.usable_capacity_ah:.2f} Ah ({el.usable_capacity_fraction*100:.0f}% Usable, {el.reserve_capacity_fraction*100:.0f}% Reserve)",
        )
        el_c3.metric(
            "Max Continuous Discharge",
            f"{el.max_continuous_discharge_a:.1f} A",
            f"{active_cfg.battery.continuous_c_rating:g}C Rating (Burst: {el.max_burst_discharge_a:.1f} A)",
        )
        el_c4.metric(
            "Pack Internal Resistance",
            f"{el.pack_internal_resistance_mohm:.1f} mΩ",
            f"Specific Energy: {el.specific_energy_wh_kg:.1f} Wh/kg",
        )

        regime_rows = []
        if el.hover_state is not None:
            regime_rows.append(el.hover_state)
        regime_rows.append(el.operating_state)
        regime_rows.append(el.peak_state)

        elec_df = pd.DataFrame(
            [
                {
                    "Flight Regime": r.regime_name,
                    "Per-Motor Current [A]": round(r.per_motor_current_a, 2),
                    "Total Motor Current [A]": round(r.total_motor_current_a, 2),
                    "Avionics Current [A]": round(r.avionics_current_a, 2),
                    "Total System Current [A]": round(r.total_system_current_a, 2),
                    "Est. Voltage Sag [V]": round(r.estimated_voltage_sag_v, 2),
                    "Loaded Bus Voltage [V]": round(r.loaded_bus_voltage_v, 2),
                    "Total Electrical Power [W]": round(r.total_electrical_power_w, 1),
                    "Copper Loss / Motor [W]": round(r.motor_copper_loss_per_motor_w, 2),
                    "Effective C-Rate [C]": round(r.effective_c_rate, 2),
                    "Cont. Limit Utilisation [%]": round(r.battery_continuous_utilization_pct, 1),
                    "Est. Endurance [min]": round(r.estimated_endurance_min, 1),
                }
                for r in regime_rows
            ]
        )
        st.markdown("##### Multi-Regime Electrical & Endurance Breakdown")
        st.dataframe(elec_df, width="stretch", hide_index=True)

        st.markdown("##### Operating Assumptions & Real-World Battery Physics")
        for assumption in el.assumptions:
            st.info(assumption)

    # =========================================================================
    # TAB 4: MODULE E — PROPULSION COMPATIBILITY
    # =========================================================================
    with tabs[3]:
        st.subheader("Module E — Component Compatibility & Engineering Margin Evaluation")
        st.caption(
            "Evaluates subsystem electrical, thermal, voltage, dataset, and thrust margins against "
            "your configurable engineering safety factors."
        )

        for item in cp.items:
            with st.container():
                st.markdown(
                    f"""
                    <div style="background-color:#111827; border:1px solid #1E293B; border-radius:6px; padding:12px 16px; margin-bottom:10px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <span style="font-size:0.75rem; color:#38BDF8; text-transform:uppercase;">{item.category}</span>
                                <h5 style="margin:2px 0 6px 0; color:#F8FAFC;">{item.title}</h5>
                            </div>
                            <div>{_severity_badge_html(item.severity)}</div>
                        </div>
                        <div style="font-size:0.85rem; color:#CBD5E1; margin-bottom:6px;">
                            <b>Measured:</b> <code>{item.measured_value_str}</code> &nbsp;|&nbsp;
                            <b>Limit / Target:</b> <code>{item.limit_value_str}</code> &nbsp;|&nbsp;
                            <b>Margin:</b> <code>{item.margin_str}</code>
                        </div>
                        <div style="font-size:0.86rem; color:#94A3B8;">{item.explanation}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.warning(f"**Flight-Safety Engineering Disclaimer:** {cp.engineering_disclaimer}")

    # =========================================================================
    # TAB 5: MODULE G — ENGINEERING VISUALISATION
    # =========================================================================
    with tabs[4]:
        st.subheader("Module G — Interactive Engineering Visualisations")
        st.caption(
            "Every chart embeds SI/engineering measurement units, data-source provenance, "
            "and operating assumptions."
        )

        ch_r1_c1, ch_r1_c2 = st.columns(2)
        with ch_r1_c1:
            st.plotly_chart(build_thrust_vs_throttle_chart(analysis), width="stretch")
        with ch_r1_c2:
            st.plotly_chart(build_current_vs_throttle_chart(analysis), width="stretch")

        ch_r2_c1, ch_r2_c2 = st.columns(2)
        with ch_r2_c1:
            st.plotly_chart(build_power_vs_throttle_chart(analysis), width="stretch")
        with ch_r2_c2:
            st.plotly_chart(build_battery_utilisation_chart(analysis), width="stretch")

        st.plotly_chart(build_payload_tradeoff_chart(analysis), width="stretch")

    # =========================================================================
    # TAB 6: MODULE F — CONFIGURATION COMPARISON
    # =========================================================================
    with tabs[5]:
        st.subheader("Module F — Multi-Configuration Architecture Comparison")
        st.caption(
            "Select two or more saved propulsion configurations to compare total thrust, TWR, "
            "current draw, electrical power, battery energy, endurance, ESC compatibility, and payload margin."
        )

        selected_cmp_ids: List[str] = st.multiselect(
            "Configurations Included in Trade Study",
            options=[c.config_id for c in all_configs],
            default=[c.config_id for c in all_configs],
            format_func=lambda cid: config_options[cid],
        )

        if not selected_cmp_ids:
            st.info("Select at least one configuration above to display comparison tables and charts.")
        else:
            cmp_analyses: List[CompleteConfigurationAnalysis] = []
            for cid in selected_cmp_ids:
                cfg_obj = repo.get_configuration(cid)
                if cfg_obj is not None:
                    ds_obj = datasets_by_id.get(cfg_obj.dataset_id, all_datasets[0])
                    cmp_analyses.append(evaluate_configuration(cfg_obj, ds_obj))

            cmp_rows = compare_configurations(cmp_analyses)
            st.plotly_chart(build_configuration_comparison_chart(cmp_rows), width="stretch")

            cmp_df = pd.DataFrame(
                [
                    {
                        "Configuration": r.config_name,
                        "Topology": f"{r.frame_type} ({r.num_motors}M)",
                        "Motor": r.motor_label,
                        "Propeller": r.propeller_label,
                        "Battery": r.battery_label,
                        "Data Provenance": r.provenance_label,
                        "Total Mass [kg]": round(r.total_mass_kg, 2),
                        "Max Thrust [N]": round(r.max_total_thrust_n, 1),
                        "Max Thrust [gf]": round(r.max_total_thrust_gf, 0),
                        "Max TWR": round(r.twr_max, 2),
                        "Hover Th [%]": round(r.hover_throttle_pct, 1),
                        "Hover Current [A]": round(r.hover_current_a, 2),
                        "Op Current [A]": round(r.operating_current_a, 2),
                        "Op Power [W]": round(r.operating_power_w, 1),
                        "Battery Energy [Wh]": round(r.battery_nominal_energy_wh, 1),
                        "Hover Endurance [min]": round(r.hover_endurance_min, 1),
                        "Op Endurance [min]": round(r.operating_endurance_min, 1),
                        "Payload Margin (TWR Target) [kg]": round(r.max_additional_payload_target_twr_kg, 2),
                        "ESC Status": f"{r.esc_compatibility_status.value} ({r.esc_margin_str})",
                        "Overall Status": r.overall_compatibility_status.value,
                    }
                    for r in cmp_rows
                ]
            )
            st.dataframe(cmp_df, width="stretch", hide_index=True)

            cmp_csv_bytes = generate_comparison_csv(cmp_rows).encode("utf-8")
            st.download_button(
                label="📥 Download Comparison Matrix (CSV)",
                data=cmp_csv_bytes,
                file_name="rotorlab_configuration_comparison.csv",
                mime="text/csv",
            )

    # =========================================================================
    # TAB 7: MODULE H — ENGINEERING REPORTS
    # =========================================================================
    with tabs[6]:
        st.subheader("Module H — Downloadable Engineering Reports & Data Exports")
        st.caption(
            "Generate complete engineering documentation packages containing component specifications, "
            "validated calculations, compatibility warnings, data provenance, and limitations."
        )

        pdf_bytes = generate_pdf_report(analysis)
        md_text = generate_markdown_report(analysis)
        csv_curve_text = generate_single_analysis_csv(analysis)

        dl1, dl2, dl3 = st.columns(3)
        with dl1:
            st.download_button(
                label="📄 Download Engineering Dossier (PDF)",
                data=pdf_bytes,
                file_name=f"RotorLab_Report_{active_cfg.config_id}.pdf",
                mime="application/pdf",
                width="stretch",
            )
        with dl2:
            st.download_button(
                label="📊 Download Throttle Curve Data (CSV)",
                data=csv_curve_text.encode("utf-8"),
                file_name=f"RotorLab_Curve_{active_cfg.config_id}.csv",
                mime="text/csv",
                width="stretch",
            )
        with dl3:
            st.download_button(
                label="📝 Download Technical Report (Markdown)",
                data=md_text.encode("utf-8"),
                file_name=f"RotorLab_Report_{active_cfg.config_id}.md",
                mime="text/markdown",
                width="stretch",
            )

        with st.expander("Preview Full Engineering Report", expanded=True):
            st.markdown(md_text)


if __name__ == "__main__":
    main()
