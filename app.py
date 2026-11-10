"""ROTORLAB 1.0 — Professional UAV Propulsion Analysis and Configuration Platform.

Premium Aerospace Engineering Workstation Interface.
All mathematical calculations are strictly delegated to `rotorlab.engine` and `rotorlab.services`.
"""

from __future__ import annotations

import uuid
from typing import List

import pandas as pd
import streamlit as st

from rotorlab.data.datasets import parse_csv_performance_dataset
from rotorlab.data.repository import RotorLabRepository
from rotorlab.engine.thrust import interpolate_at_throttle
from rotorlab.models.domain import (
    AirframeSpec,
    BatterySpec,
    DataProvenance,
    EngineeringMargins,
    ESCSpec,
    MotorSpec,
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

# Premium Aerospace Workstation Design System & Accessible Micro-Interactions
st.markdown(
    """
    <style>
    :root {
        --bg-canvas: #080C14;
        --bg-surface: #0D1322;
        --bg-elevated: #131C31;
        --border-subtle: #1E293B;
        --border-focus: #38BDF8;
        --text-primary: #F8FAFC;
        --text-secondary: #CBD5E1;
        --text-muted: #94A3B8;
        --accent-cyan: #38BDF8;
        --accent-emerald: #10B981;
        --accent-amber: #F59E0B;
        --accent-rose: #F43F5E;
        --ease-out: cubic-bezier(0.22, 1, 0.36, 1);
    }

    .stApp {
        background-color: var(--bg-canvas);
        color: var(--text-primary);
        font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
    }

    .block-container {
        padding-top: 1.6rem !important;
        padding-bottom: 3rem !important;
        max-width: 1440px !important;
    }

    @keyframes rlFadeSlideIn {
        from {
            opacity: 0;
            transform: translateY(6px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* Workstation Top Banner */
    .rl-banner {
        background: linear-gradient(135deg, #0D1322 0%, #131C31 100%);
        border: 1px solid var(--border-subtle);
        border-left: 4px solid var(--accent-cyan);
        border-radius: 10px;
        padding: 18px 24px;
        margin-bottom: 18px;
        animation: rlFadeSlideIn 260ms var(--ease-out) both;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.28);
    }
    .rl-banner-top {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 16px;
        flex-wrap: wrap;
    }
    .rl-eyebrow {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--accent-cyan);
        margin-bottom: 4px;
    }
    .rl-title {
        font-size: 1.45rem;
        font-weight: 700;
        color: var(--text-primary);
        margin: 0;
        letter-spacing: -0.01em;
    }
    .rl-subtitle {
        font-size: 0.88rem;
        color: var(--text-muted);
        margin: 4px 0 0 0;
        line-height: 1.45;
    }
    .rl-chip-row {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 12px;
        padding-top: 12px;
        border-top: 1px solid rgba(148, 163, 184, 0.12);
    }
    .rl-chip {
        background-color: rgba(15, 23, 42, 0.75);
        border: 1px solid var(--border-subtle);
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 0.78rem;
        color: var(--text-secondary);
    }
    .rl-chip b {
        color: var(--text-primary);
    }

    /* 4 Primary Dashboard KPI Cards */
    .rl-kpi-card {
        background-color: var(--bg-surface);
        border: 1px solid var(--border-subtle);
        border-radius: 10px;
        padding: 16px 18px;
        height: 100%;
        min-height: 132px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        transition: transform 180ms var(--ease-out), border-color 180ms var(--ease-out), box-shadow 180ms var(--ease-out);
        animation: rlFadeSlideIn 280ms var(--ease-out) both;
    }
    .rl-kpi-card:hover {
        transform: translateY(-2px);
        border-color: rgba(56, 189, 248, 0.45);
        box-shadow: 0 10px 24px rgba(0, 0, 0, 0.32);
    }
    .rl-kpi-label {
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--text-muted);
        margin-bottom: 6px;
    }
    .rl-kpi-value {
        font-size: 1.55rem;
        font-weight: 700;
        color: var(--text-primary);
        font-variant-numeric: tabular-nums;
        line-height: 1.2;
    }
    .rl-kpi-sub {
        font-size: 0.81rem;
        font-weight: 600;
        color: var(--accent-cyan);
        margin-top: 6px;
        font-variant-numeric: tabular-nums;
    }
    .rl-kpi-explain {
        font-size: 0.77rem;
        color: var(--text-muted);
        margin-top: 6px;
        line-height: 1.38;
    }

    /* Section Panels & Cards */
    .rl-panel {
        background-color: var(--bg-surface);
        border: 1px solid var(--border-subtle);
        border-radius: 10px;
        padding: 18px 20px;
        margin-bottom: 14px;
        animation: rlFadeSlideIn 240ms var(--ease-out) both;
    }
    .rl-panel-title {
        font-size: 1.02rem;
        font-weight: 600;
        color: var(--text-primary);
        margin: 0 0 4px 0;
    }
    .rl-panel-desc {
        font-size: 0.84rem;
        color: var(--text-muted);
        margin: 0 0 12px 0;
        line-height: 1.45;
    }

    /* Compatibility Check Cards */
    .rl-compat-card {
        background-color: var(--bg-surface);
        border: 1px solid var(--border-subtle);
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 10px;
        transition: border-color 180ms var(--ease-out), background-color 180ms var(--ease-out);
        animation: rlFadeSlideIn 220ms var(--ease-out) both;
    }
    .rl-compat-card:hover {
        border-color: #334155;
        background-color: var(--bg-elevated);
    }

    /* Status Badges */
    .badge-pass {
        background-color: rgba(16, 185, 129, 0.14);
        color: #34D399;
        border: 1px solid rgba(16, 185, 129, 0.45);
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        display: inline-block;
    }
    .badge-warn {
        background-color: rgba(245, 158, 11, 0.14);
        color: #FBBF24;
        border: 1px solid rgba(245, 158, 11, 0.45);
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        display: inline-block;
    }
    .badge-crit {
        background-color: rgba(244, 63, 94, 0.14);
        color: #FB7185;
        border: 1px solid rgba(244, 63, 94, 0.45);
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        display: inline-block;
    }
    .badge-info {
        background-color: rgba(56, 189, 248, 0.14);
        color: #38BDF8;
        border: 1px solid rgba(56, 189, 248, 0.45);
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        display: inline-block;
    }

    /* Streamlit Tabs Refinement */
    div[data-testid="stTabs"] button[role="tab"] {
        font-size: 0.88rem !important;
        font-weight: 600 !important;
        padding: 10px 16px !important;
        transition: color 160ms var(--ease-out), background-color 160ms var(--ease-out) !important;
    }
    div[data-testid="stTabs"] div[role="tabpanel"] {
        animation: rlFadeSlideIn 220ms var(--ease-out) both;
        padding-top: 12px;
    }

    /* Buttons & Expanders Polish */
    .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        border: 1px solid #26354D !important;
        transition: transform 150ms var(--ease-out), border-color 150ms var(--ease-out), background-color 150ms var(--ease-out) !important;
    }
    .stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {
        border-color: var(--accent-cyan) !important;
        transform: translateY(-1px);
    }
    .stButton > button:active, .stDownloadButton > button:active, .stFormSubmitButton > button:active {
        transform: translateY(0);
    }
    div[data-testid="stExpander"] {
        background-color: var(--bg-surface);
        border: 1px solid var(--border-subtle) !important;
        border-radius: 8px !important;
    }

    /* Reduced Motion Accessibility Support */
    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
            scroll-behavior: auto !important;
        }
        .rl-kpi-card:hover, .stButton > button:hover {
            transform: none !important;
        }
    }

    /* Responsive adjustments */
    @media (max-width: 900px) {
        .rl-title {
            font-size: 1.2rem;
        }
        .rl-kpi-value {
            font-size: 1.3rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_repo() -> RotorLabRepository:
    return RotorLabRepository("rotorlab_workspace.db")


def _severity_badge_html(sev: SeverityLevel, prefix: str = "") -> str:
    label = f"{prefix}{sev.value}" if prefix else sev.value
    if sev == SeverityLevel.PASS:
        return f"<span class='badge-pass'>✓ {label}</span>"
    if sev == SeverityLevel.WARNING:
        return f"<span class='badge-warn'>⚠ {label}</span>"
    if sev == SeverityLevel.CRITICAL:
        return f"<span class='badge-crit'>✕ {label}</span>"
    return f"<span class='badge-info'>ℹ {label}</span>"


def _render_kpi_card(label: str, value: str, sub: str, explanation: str) -> None:
    st.markdown(
        f"""
        <div class="rl-kpi-card">
            <div>
                <div class="rl-kpi-label">{label}</div>
                <div class="rl-kpi-value">{value}</div>
                <div class="rl-kpi-sub">{sub}</div>
            </div>
            <div class="rl-kpi-explain">{explanation}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    repo = get_repo()
    repo.ensure_builtin_presets()
    all_configs = repo.list_configurations()
    all_datasets = repo.list_all_datasets()
    datasets_by_id = {d.dataset_id: d for d in all_datasets}
    builtin_ids = repo.builtin_preset_ids()

    # Initialize session state
    if "active_config_id" not in st.session_state or st.session_state["active_config_id"] not in {
        c.config_id for c in all_configs
    }:
        st.session_state["active_config_id"] = all_configs[0].config_id

    # =========================================================================
    # SIDEBAR — WORKSTATION CONTROL, SAVED CONFIGURATIONS & UNITS
    # =========================================================================
    with st.sidebar:
        st.markdown("### 🛸 ROTORLAB 1.0")
        st.caption("Aerospace UAV Propulsion Analysis & Configuration Workstation")
        st.divider()

        st.markdown("#### Saved Configurations")
        config_options = {c.config_id: f"{c.name}" for c in all_configs}
        selected_cfg_id = st.selectbox(
            "Active Aircraft Architecture",
            options=list(config_options.keys()),
            format_func=lambda cid: config_options[cid],
            index=list(config_options.keys()).index(st.session_state["active_config_id"]),
            help="Switch between saved multirotor propulsion configurations stored in SQLite.",
        )
        if selected_cfg_id != st.session_state["active_config_id"]:
            st.session_state["active_config_id"] = selected_cfg_id
            st.rerun()

        active_cfg = repo.get_configuration(st.session_state["active_config_id"])
        if active_cfg is None:
            active_cfg = all_configs[0]

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if st.button("Duplicate", width="stretch", help="Create an editable copy of this configuration for what-if trade studies"):
                dup = repo.duplicate_configuration(active_cfg.config_id)
                st.session_state["active_config_id"] = dup.config_id
                st.toast(f"Cloned as '{dup.name}'")
                st.rerun()
        with col_s2:
            is_builtin = active_cfg.config_id in builtin_ids
            can_delete = (not is_builtin) and (len(all_configs) > 1)
            if st.button(
                "Delete",
                width="stretch",
                disabled=not can_delete,
                help="Built-in reference presets are protected and cannot be deleted. Only custom or duplicated configurations can be deleted."
                if is_builtin
                else "Remove this custom configuration from workspace storage.",
            ):
                repo.delete_configuration(active_cfg.config_id)
                remaining = repo.list_configurations()
                st.session_state["active_config_id"] = remaining[0].config_id
                st.toast("Custom configuration removed.")
                st.rerun()

        if st.button("🔄 Restore Factory Presets", width="stretch", help="Restore all 4 built-in reference UAV configurations to their original specifications"):
            repo.reset_builtin_presets()
            st.toast("All 4 factory reference presets restored!")
            st.rerun()

        with st.expander("⚙️ Measurement Units", expanded=False):
            st.caption("Choose your preferred display and input units. Internal equations always execute in SI.")
            mass_unit = st.selectbox("Mass Unit", ["kg", "g", "lb"], index=0)
            prop_unit = st.selectbox("Propeller Dimension Unit", ["inch", "mm"], index=0)
            cap_unit = st.selectbox("Battery Capacity Unit", ["mAh", "Ah"], index=0)

        active_ds = datasets_by_id.get(active_cfg.dataset_id, all_datasets[0])
        with st.expander("📡 Data Provenance & Guide", expanded=False):
            st.markdown(
                f"**Provenance:** `{active_ds.provenance.value}`\n\n"
                f"- **Motor:** `{active_ds.motor_manufacturer} {active_ds.motor_model} (KV{active_ds.motor_kv:.0f})`\n"
                f"- **Propeller:** `{active_ds.propeller_diameter_in:g}×{active_ds.propeller_pitch_in:g}\"` @ `{active_ds.test_voltage_v:g} V`\n\n"
                "**Workflow Guide:**\n"
                "1. Review summary & warnings on **Overview**.\n"
                "2. Edit airframe & components in **1 & 2. Configure**.\n"
                "3. Inspect curves & hover margins in **3. Analyse**.\n"
                "4. Run trade studies in **4. Compare**.\n"
                "5. Export PDF/CSV in **5. Report**."
            )

    # Evaluate active configuration through deterministic engine
    analysis: CompleteConfigurationAnalysis = evaluate_configuration(active_cfg, active_ds)
    tr = analysis.thrust
    el = analysis.electrical
    cp = analysis.compatibility

    # =========================================================================
    # WORKSTATION HEADER & ESSENTIAL 4-KPI EXECUTIVE BAR
    # =========================================================================
    st.markdown(
        f"""
        <div class="rl-banner">
            <div class="rl-banner-top">
                <div>
                    <div class="rl-eyebrow">ROTORLAB 1.0 // DETERMINISTIC PROPULSION WORKSTATION</div>
                    <h1 class="rl-title">{active_cfg.name}</h1>
                    <p class="rl-subtitle">{active_cfg.description}</p>
                </div>
                <div>
                    {_severity_badge_html(cp.overall_status, prefix="SYSTEM STATUS: ")}
                </div>
            </div>
            <div class="rl-chip-row">
                <span class="rl-chip">Topology: <b>{active_cfg.airframe.frame_type} ({active_cfg.airframe.num_motors} Motors)</b></span>
                <span class="rl-chip">Motor: <b>{active_cfg.motor.full_name}</b></span>
                <span class="rl-chip">Propeller: <b>{active_cfg.propeller.code}" {active_cfg.propeller.material}</b></span>
                <span class="rl-chip">Battery: <b>{active_cfg.battery.cell_count_s}S {active_cfg.battery.capacity_mah:.0f} mAh ({active_cfg.battery.operating_voltage_v:.1f} V)</b></span>
                <span class="rl-chip">Data Source: <b>{active_ds.provenance.value}</b></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Essential 4 KPI Cards (Avoiding Simultaneous Metric Overload)
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        _render_kpi_card(
            "Total Estimated Thrust",
            f"{tr.max_total_thrust_n:.1f} N",
            f"{tr.max_total_thrust_gf:.0f} gf ({tr.max_total_thrust_kgf:.2f} kgf) Peak",
            f"Combined static lift of all {active_cfg.airframe.num_motors} rotors vs. {tr.aircraft_weight_n:.1f} N ({tr.total_mass_kg:.2f} kg) total aircraft weight.",
        )
    with kpi2:
        hover_th_text = (
            f"Hover at {tr.hover_single_motor_state.throttle_pct:.1f}% throttle"
            if tr.hover_feasible and tr.hover_single_motor_state
            else "Hover Infeasible (>100% throttle)"
        )
        _render_kpi_card(
            "Thrust-to-Weight Ratio (TWR)",
            f"{tr.twr_max:.2f} : 1",
            hover_th_text,
            "Ratio of peak thrust to aircraft weight. Multirotors typically target TWR ≥ 2.0 for safe climb and wind control.",
        )
    with kpi3:
        _render_kpi_card(
            "Usable Battery Energy",
            f"{el.usable_energy_wh:.1f} Wh",
            f"Nominal: {el.nominal_energy_wh:.1f} Wh ({el.usable_capacity_fraction * 100:.0f}% Usable)",
            f"Retains a {el.reserve_capacity_fraction * 100:.0f}% safety buffer to prevent LiPo deep-discharge damage.",
        )
    with kpi4:
        hover_end_str = (
            f"{el.hover_state.estimated_endurance_min:.1f} min"
            if el.hover_state is not None
            else "0.0 min"
        )
        _render_kpi_card(
            "Estimated Flight Endurance",
            hover_end_str,
            f"Cruise ({active_cfg.airframe.operating_throttle_pct:.0f}% Th): {el.operating_state.estimated_endurance_min:.1f} min",
            "Continuous hover duration based on usable battery capacity and total motor + avionics current draw.",
        )

    st.write("")

    # =========================================================================
    # LOGICAL 5-STEP ENGINEERING WORKFLOW NAVIGATION
    # =========================================================================
    tabs = st.tabs(
        [
            "🏠 Overview Dashboard",
            "🛠️ 1 & 2. Configure Aircraft & Propulsion",
            "📈 3. Analyse Performance",
            "⚖️ 4. Compare Configurations",
            "📄 5. Generate Engineering Report",
        ]
    )

    # =========================================================================
    # TAB 0: OVERVIEW DASHBOARD (IMMEDIATELY UNDERSTANDABLE SUMMARY)
    # =========================================================================
    with tabs[0]:
        ov_left, ov_right = st.columns([1.35, 1])

        with ov_left:
            st.plotly_chart(build_thrust_vs_throttle_chart(analysis), width="stretch", key="ov_thrust_chart")

        with ov_right:
            st.markdown(
                """
                <div class="rl-panel">
                    <p class="rl-panel-title">Engineering Health & Compatibility Summary</p>
                    <p class="rl-panel-desc">
                        Automated verification of ESC current headroom, motor thermal limits, battery C-rate capability,
                        voltage matching, and hover authority.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            non_pass_items = [item for item in cp.items if item.severity != SeverityLevel.PASS]
            if not non_pass_items:
                st.success(
                    f"**All {cp.pass_count} Subsystem Checks Passed.** "
                    "Motor, ESC, battery, dataset voltage, and TWR margins satisfy configured engineering thresholds."
                )
            else:
                for item in non_pass_items:
                    st.markdown(
                        f"""
                        <div class="rl-compat-card">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                                <b style="color:#F8FAFC; font-size:0.88rem;">{item.title}</b>
                                {_severity_badge_html(item.severity)}
                            </div>
                            <div style="font-size:0.8rem; color:#CBD5E1; margin-bottom:4px;">
                                Measured: <code>{item.measured_value_str}</code> &nbsp;|&nbsp; Limit: <code>{item.limit_value_str}</code>
                            </div>
                            <div style="font-size:0.81rem; color:#94A3B8;">{item.explanation}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            with st.expander(f"View All {len(cp.items)} Compatibility & Margin Checks", expanded=False):
                for item in cp.items:
                    st.markdown(
                        f"- **[{item.severity.value}] {item.title}**: `{item.measured_value_str}` vs `{item.limit_value_str}` — {item.explanation}"
                    )

        # Quick Switcher for Saved / Recent Configurations
        st.markdown("##### Saved & Reference Aircraft Configurations")
        st.caption("Click any configuration preset below to load and evaluate it immediately.")
        preset_cols = st.columns(min(4, max(1, len(all_configs))))
        for idx, cfg_item in enumerate(all_configs[:4]):
            with preset_cols[idx % len(preset_cols)]:
                is_current = cfg_item.config_id == active_cfg.config_id
                card_border = "#38BDF8" if is_current else "#1E293B"
                st.markdown(
                    f"""
                    <div style="background-color:#0D1322; border:1px solid {card_border}; border-radius:8px; padding:12px 14px; margin-bottom:8px;">
                        <div style="font-size:0.72rem; color:#38BDF8; text-transform:uppercase; font-weight:600;">
                            {cfg_item.airframe.frame_type} • {cfg_item.airframe.num_motors} Motors
                        </div>
                        <div style="font-size:0.92rem; font-weight:700; color:#F8FAFC; margin:2px 0 4px 0;">
                            {cfg_item.name}
                        </div>
                        <div style="font-size:0.78rem; color:#94A3B8;">
                            {cfg_item.motor.manufacturer} {cfg_item.motor.model} • {cfg_item.propeller.code}" • {cfg_item.battery.cell_count_s}S {cfg_item.battery.capacity_mah:.0f}mAh
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(
                    "✓ Active Configuration" if is_current else "Load Configuration",
                    key=f"quick_load_{cfg_item.config_id}",
                    disabled=is_current,
                    width="stretch",
                ):
                    st.session_state["active_config_id"] = cfg_item.config_id
                    st.rerun()

    # =========================================================================
    # TAB 1: STEPS 1 & 2 — CONFIGURE AIRCRAFT & SELECT PROPULSION COMPONENTS
    # =========================================================================
    with tabs[1]:
        st.subheader("Steps 1 & 2 — Configure Aircraft & Select Propulsion Components")
        st.caption(
            "Essential parameters are shown upfront. Advanced internal resistances, atmospheric offsets, "
            "and safety factor thresholds are organised in expandable panels below."
        )

        with st.form("propulsion_config_form"):
            st.markdown("##### Step 1: Aircraft Topology & Mass Budget")
            c_meta1, c_meta2 = st.columns([1, 1.8])
            with c_meta1:
                cfg_name = st.text_input(
                    "Configuration Name",
                    value=active_cfg.name,
                    help="Unique name for identifying this aircraft setup in comparisons and reports.",
                )
            with c_meta2:
                cfg_desc = st.text_input(
                    "Mission & Engineering Description",
                    value=active_cfg.description,
                    help="Brief summary of the aircraft's intended mission profile.",
                )

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
                frame_type_in = st.selectbox(
                    "Airframe Topology",
                    options=frame_types,
                    index=frame_idx,
                    help="Geometric arrangement of the multirotor arms and propulsion units.",
                )
            with af2:
                num_motors_in = int(
                    st.number_input(
                        "Number of Motors",
                        min_value=1,
                        max_value=32,
                        value=int(active_cfg.airframe.num_motors),
                        step=1,
                        help="Total count of active lift-generating motors on the airframe.",
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
                        help="Mass of the airframe, motors, ESCs, avionics, and battery WITHOUT mission payload.",
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
                        help="Mass of cameras, gimbals, LiDAR sensors, or cargo carried by the aircraft.",
                    )
                )
            with af5:
                op_throttle_in = float(
                    st.number_input(
                        "Nominal Cruise Throttle [%]",
                        min_value=10.0,
                        max_value=100.0,
                        value=float(active_cfg.airframe.operating_throttle_pct),
                        step=5.0,
                        help="Representative throttle command used to evaluate cruise operating power and endurance.",
                    )
                )

            st.divider()
            st.markdown("##### Step 2: Propulsion Components & Empirical Dataset")
            ds_select_id = st.selectbox(
                "Empirical Motor-Propeller Performance Dataset",
                options=list(datasets_by_id.keys()),
                format_func=lambda did: datasets_by_id[did].display_label,
                index=list(datasets_by_id.keys()).index(active_cfg.dataset_id)
                if active_cfg.dataset_id in datasets_by_id
                else 0,
                help=(
                    "Accurate static thrust cannot be computed from KV and propeller diameter alone. "
                    "Select a measured test-bench dataset that matches your motor, propeller, and voltage."
                ),
            )

            comp_col1, comp_col2 = st.columns(2)
            with comp_col1:
                st.caption("**BLDC Motor & Propeller**")
                mc1, mc2, mc3 = st.columns(3)
                with mc1:
                    m_mfg = st.text_input("Motor Brand", value=active_cfg.motor.manufacturer)
                with mc2:
                    m_mod = st.text_input("Motor Model", value=active_cfg.motor.model)
                with mc3:
                    m_kv = float(
                        st.number_input(
                            "Motor KV [RPM/V]",
                            min_value=50.0,
                            max_value=15000.0,
                            value=float(active_cfg.motor.kv_rating),
                            step=10.0,
                            help="Unloaded motor rotational speed per Volt applied.",
                        )
                    )

                mc4, mc5, mc6, mc7 = st.columns(4)
                with mc4:
                    m_max_i = float(
                        st.number_input(
                            "Motor Max Current [A]",
                            min_value=1.0,
                            max_value=300.0,
                            value=float(active_cfg.motor.max_continuous_current_a),
                            step=1.0,
                            help="Maximum continuous current rating from the motor datasheet.",
                        )
                    )
                with mc5:
                    m_max_p = float(
                        st.number_input(
                            "Motor Max Power [W]",
                            min_value=10.0,
                            max_value=10000.0,
                            value=float(active_cfg.motor.max_continuous_power_w),
                            step=10.0,
                            help="Maximum continuous electrical power rating of the motor.",
                        )
                    )
                with mc6:
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
                            help="Outer tip-to-tip diameter of the propeller.",
                        )
                    )
                with mc7:
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
                            help="Theoretical axial distance travelled per single propeller revolution.",
                        )
                    )

            with comp_col2:
                st.caption("**ESC & Flight Battery Pack**")
                bc1, bc2, bc3 = st.columns(3)
                with bc1:
                    esc_name = st.text_input("ESC Model", value=active_cfg.esc.name)
                with bc2:
                    esc_cont_a = float(
                        st.number_input(
                            "ESC Cont. Rating [A]",
                            min_value=1.0,
                            max_value=400.0,
                            value=float(active_cfg.esc.continuous_current_a),
                            step=5.0,
                            help="Continuous current capability of each Electronic Speed Controller.",
                        )
                    )
                with bc3:
                    batt_name = st.text_input("Battery Pack Name", value=active_cfg.battery.name)

                bc4, bc5, bc6, bc7 = st.columns(4)
                with bc4:
                    batt_s = int(
                        st.number_input(
                            "Cells [S]",
                            min_value=1,
                            max_value=24,
                            value=int(active_cfg.battery.cell_count_s),
                            help="Number of series-connected LiPo/Li-Ion cells (e.g., 4S = 14.8V nominal, 6S = 22.2V nominal).",
                        )
                    )
                with bc5:
                    batt_op_v = float(
                        st.number_input(
                            "Operating Voltage [V]",
                            min_value=3.0,
                            max_value=120.0,
                            value=float(active_cfg.battery.operating_voltage_v),
                            step=0.1,
                            help="Bus voltage used for power and compatibility evaluation.",
                        )
                    )
                with bc6:
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
                            help="Total nominal charge capacity of the battery pack.",
                        )
                    )
                with bc7:
                    batt_c_cont = float(
                        st.number_input(
                            "Discharge [C]",
                            min_value=1.0,
                            max_value=200.0,
                            value=float(active_cfg.battery.continuous_c_rating),
                            step=5.0,
                            help="Continuous discharge C-rating. Max continuous current = Capacity (Ah) × C-rating.",
                        )
                    )

            # Progressive Disclosure: Advanced Electrical, Atmospheric & Margin Parameters
            with st.expander("🔬 Advanced Parameters (Atmosphere, Internal Resistance, Cell Bounds & Safety Margins)", expanded=False):
                adv1, adv2, adv3, adv4 = st.columns(4)
                with adv1:
                    avionics_w_in = float(
                        st.number_input(
                            "Avionics Power Load [W]",
                            min_value=0.0,
                            max_value=500.0,
                            value=float(active_cfg.airframe.avionics_power_w),
                            step=1.0,
                            help="Continuous electrical power drawn by flight controller, GPS, companion computer, and telemetry.",
                        )
                    )
                    alt_m_in = float(
                        st.number_input(
                            "Operating Altitude MSL [m]",
                            min_value=-200.0,
                            max_value=10000.0,
                            value=float(active_cfg.airframe.altitude_m),
                            step=100.0,
                            help="Geopotential altitude above Mean Sea Level for ISA air density calculation.",
                        )
                    )
                    temp_off_in = float(
                        st.number_input(
                            "ISA Temp Offset [°C]",
                            min_value=-40.0,
                            max_value=50.0,
                            value=float(active_cfg.airframe.temp_offset_c),
                            step=1.0,
                            help="Temperature deviation from standard ISA atmosphere (+15°C at sea level).",
                        )
                    )
                with adv2:
                    p_mfg = st.text_input("Propeller Brand", value=active_cfg.propeller.manufacturer)
                    p_mod = st.text_input("Propeller Model Name", value=active_cfg.propeller.model)
                    m_rint = float(
                        st.number_input(
                            "Motor Winding Resistance [mΩ]",
                            min_value=1.0,
                            max_value=2000.0,
                            value=float(active_cfg.motor.internal_resistance_mohm),
                            step=5.0,
                            help="Phase-to-phase DC resistance used to calculate motor copper heating losses (I²R).",
                        )
                    )
                with adv3:
                    batt_nom_v = float(
                        st.number_input(
                            "Battery Nominal Voltage [V]",
                            min_value=3.0,
                            max_value=120.0,
                            value=float(active_cfg.battery.nominal_voltage_v),
                            step=0.1,
                            help="Nominal pack voltage used for stored Watt-hour (Wh) calculation.",
                        )
                    )
                    batt_usable_pct = float(
                        st.number_input(
                            "Usable Battery Capacity [%]",
                            min_value=20.0,
                            max_value=100.0,
                            value=float(active_cfg.battery.usable_capacity_fraction * 100.0),
                            step=5.0,
                            help="Percentage of nominal capacity consumed before landing (80% leaves a 20% safety reserve).",
                        )
                    )
                    esc_peak_a = float(
                        st.number_input(
                            "ESC Peak/Burst Current [A]",
                            min_value=1.0,
                            max_value=600.0,
                            value=float(active_cfg.esc.peak_current_a),
                            step=5.0,
                        )
                    )
                with adv4:
                    esc_sf_in = float(
                        st.number_input(
                            "ESC Safety Factor (× Peak I)",
                            min_value=1.0,
                            max_value=3.0,
                            value=float(active_cfg.margins.esc_current_safety_factor),
                            step=0.05,
                            help="Recommended ratio of ESC continuous rating to peak per-motor current.",
                        )
                    )
                    min_twr_in = float(
                        st.number_input(
                            "Min Hover TWR Threshold",
                            min_value=1.05,
                            max_value=3.0,
                            value=float(active_cfg.margins.min_hover_twr),
                            step=0.1,
                        )
                    )
                    rec_twr_in = float(
                        st.number_input(
                            "Target Design TWR",
                            min_value=1.2,
                            max_value=5.0,
                            value=float(active_cfg.margins.recommended_agile_twr),
                            step=0.1,
                        )
                    )
                    v_tol_in = float(
                        st.number_input(
                            "Dataset Voltage Tolerance [%]",
                            min_value=1.0,
                            max_value=30.0,
                            value=float(active_cfg.margins.voltage_mismatch_tolerance_pct),
                            step=1.0,
                        )
                    )

                cell_c1, cell_c2, cell_c3, cell_c4 = st.columns(4)
                with cell_c1:
                    m_min_s = int(
                        st.number_input("Motor Min Cells [S]", min_value=1, max_value=24, value=int(active_cfg.motor.min_cells_s))
                    )
                with cell_c2:
                    m_max_s = int(
                        st.number_input("Motor Max Cells [S]", min_value=1, max_value=24, value=int(active_cfg.motor.max_cells_s))
                    )
                with cell_c3:
                    esc_min_s = int(
                        st.number_input("ESC Min Cells [S]", min_value=1, max_value=24, value=int(active_cfg.esc.min_cells_s))
                    )
                with cell_c4:
                    esc_max_s = int(
                        st.number_input("ESC Max Cells [S]", min_value=1, max_value=24, value=int(active_cfg.esc.max_cells_s))
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
                    st.toast(f"Saved '{updated_cfg.name}'")
                    st.rerun()
                except ValueError as err:
                    st.error(f"Input Validation Error: {err}")

        # Progressive Disclosure for Raw Dataset Table & Custom CSV Importer
        with st.expander("📂 Inspect Active Performance Dataset & Import Custom Thrust-Stand CSV", expanded=False):
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
                    "or paste CSV rows below."
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
                csv_text_area = st.text_area("Or Paste CSV Data Directly", value=default_csv_text, height=120)

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
    # TAB 2: STEP 3 — ANALYSE PERFORMANCE (CHARTS, THRUST, ELECTRICAL, COMPAT)
    # =========================================================================
    with tabs[2]:
        st.subheader("Step 3 — Propulsion Performance, Electrical & Compatibility Analysis")
        st.caption(
            "Explore interactive performance curves, probe any throttle setting, and inspect detailed aerodynamic and electrical breakdowns."
        )

        for w_msg in tr.warnings:
            st.warning(f"**Dataset / Interpolation Notice:** {w_msg}")

        # Primary Interactive Charts Grid
        ch_r1_c1, ch_r1_c2 = st.columns(2)
        with ch_r1_c1:
            st.plotly_chart(build_thrust_vs_throttle_chart(analysis), width="stretch", key="an_thrust_chart")
        with ch_r1_c2:
            st.plotly_chart(build_current_vs_throttle_chart(analysis), width="stretch", key="an_current_chart")

        ch_r2_c1, ch_r2_c2 = st.columns(2)
        with ch_r2_c1:
            st.plotly_chart(build_power_vs_throttle_chart(analysis), width="stretch", key="an_power_chart")
        with ch_r2_c2:
            st.plotly_chart(build_battery_utilisation_chart(analysis), width="stretch", key="an_batt_chart")

        st.plotly_chart(build_payload_tradeoff_chart(analysis), width="stretch", key="an_payload_chart")

        st.divider()
        # Interactive Throttle Probe
        st.markdown("##### Interactive Throttle Operating Point Probe")
        st.caption("Slide to inspect interpolated single-motor and full-aircraft metrics at any throttle command.")
        custom_th = st.slider(
            "Throttle Command [%]",
            min_value=0.0,
            max_value=100.0,
            value=float(active_cfg.airframe.operating_throttle_pct),
            step=1.0,
        )
        probed_state = interpolate_at_throttle(active_ds, active_cfg.propeller, custom_th)
        if probed_state.extrapolation_warning:
            st.warning(probed_state.extrapolation_warning)

        pr1, pr2, pr3, pr4, pr5 = st.columns(5)
        pr1.metric("Single Motor Thrust", f"{probed_state.thrust_gf:.1f} gf", f"{probed_state.thrust_n:.2f} N")
        pr2.metric(
            "Total Aircraft Thrust",
            f"{active_cfg.airframe.num_motors * probed_state.thrust_gf:.0f} gf",
            f"TWR: {(active_cfg.airframe.num_motors * probed_state.thrust_n) / tr.aircraft_weight_n:.2f}",
        )
        pr3.metric("Single Motor Current", f"{probed_state.current_a:.2f} A", f"Power: {probed_state.power_w:.1f} W")
        pr4.metric("Propeller Speed", f"{probed_state.rpm:.0f} RPM", f"Tip: {probed_state.tip_speed_m_s:.1f} m/s")
        pr5.metric("Specific Efficacy", f"{probed_state.efficiency_gf_w:.2f} gf/W", probed_state.provenance.value)

        # Progressive Disclosure for Detailed Engineering Tables & Physics Explanations
        with st.expander("🚀 Detailed Thrust, Payload Margin & Actuator-Disk Aerodynamics (Modules B & D)", expanded=False):
            col_b1, col_b2, col_b3 = st.columns(3)
            with col_b1:
                st.markdown("**Peak & Operating Static Thrust**")
                st.write(
                    f"- **Single Motor Peak ({tr.max_single_motor_state.throttle_pct:.0f}% Th):** "
                    f"`{tr.max_single_motor_state.thrust_gf:.1f} gf` (`{tr.max_single_motor_state.thrust_n:.2f} N`)"
                )
                st.write(
                    f"- **Total Peak Thrust ({active_cfg.airframe.num_motors} Motors):** "
                    f"`{tr.max_total_thrust_gf:.0f} gf` (`{tr.max_total_thrust_n:.2f} N` / `{tr.max_total_thrust_kgf:.2f} kgf`)"
                )
                st.write(
                    f"- **Operating Thrust ({active_cfg.airframe.operating_throttle_pct:.0f}% Th):** "
                    f"`{tr.operating_total_thrust_gf:.0f} gf` (`{tr.operating_total_thrust_n:.2f} N`)"
                )
                st.write(
                    f"- **Peak RPM & Blade Tip Speed:** "
                    f"`{tr.max_single_motor_state.rpm:.0f} RPM` (`{tr.max_single_motor_state.tip_speed_m_s:.1f} m/s`)"
                )
            with col_b2:
                st.markdown("**Weight, TWR & Payload Limits**")
                st.write(
                    f"- **Mass Breakdown:** `{tr.aircraft_dry_mass_kg:.3f} kg` dry + `{tr.payload_mass_kg:.3f} kg` payload = **`{tr.total_mass_kg:.3f} kg`**"
                )
                st.write(f"- **Max TWR:** **`{tr.twr_max:.2f}`** | **Operating TWR:** `{tr.twr_operating:.2f}`")
                st.write(
                    f"- **Available Thrust Margin:** `{tr.available_thrust_margin_n:+.2f} N` (`{tr.available_thrust_margin_pct:+.1f}%`)"
                )
                st.write(
                    f"- **Additional Payload at Target TWR ({tr.target_twr_used:.1f}):** `{tr.max_additional_payload_at_target_twr_kg:+.3f} kg`"
                )
                st.write(f"- **Max Payload at Static Ceiling (TWR = 1.0):** `{tr.max_payload_at_twr_1_kg:.3f} kg`")
            with col_b3:
                st.markdown("**Actuator Disk Momentum Physics**")
                st.write(f"- **ISA Air Density ($\\rho$):** `{tr.air_density_kg_m3:.4f} kg/m³`")
                st.write(
                    f"- **Rotor Disk Loading:** `{tr.disk_loading_kg_m2:.2f} kg/m²` (`{tr.disk_loading_n_m2:.1f} N/m²`) — *lower disk loading improves hover efficiency*"
                )
                st.write(
                    f"- **Hover Induced Velocity ($v_i$):** `{tr.hover_induced_velocity_m_s:.2f} m/s` — *downwash air velocity through the rotor disk*"
                )
                st.write(
                    f"- **Electro-Propulsive Figure of Merit ($FM$):** `{tr.figure_of_merit_hover:.3f}` — *ratio of ideal actuator-disk power to electrical input power*"
                )
                st.write(
                    f"- **Single-Motor Failure ($N-1$) TWR:** `{tr.motor_out_twr:.2f}` (`{tr.motor_out_max_thrust_n:.1f} N`)"
                )

        with st.expander("⚡ Multi-Regime Electrical Power, Voltage Sag & Battery Breakdown (Module C)", expanded=False):
            st.caption(
                "Equations: $E\\,(\\text{Wh}) = V\\,(\\text{V}) \\times C\\,(\\text{Ah})$, "
                "$P\\,(\\text{W}) = V\\,(\\text{V}) \\times I\\,(\\text{A})$, "
                "$\\text{Time}\\,(\\text{min}) = (C_{\\text{usable}}\\,(\\text{Ah}) / I_{\\text{avg}}\\,(\\text{A})) \\times 60$."
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
            st.dataframe(elec_df, width="stretch", hide_index=True)
            for assumption in el.assumptions:
                st.info(assumption)

        with st.expander("🛡️ Full Component Compatibility & Safety Margin Audit (Module E)", expanded=False):
            for item in cp.items:
                st.markdown(
                    f"""
                    <div class="rl-compat-card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <span style="font-size:0.72rem; color:#38BDF8; text-transform:uppercase; font-weight:600;">{item.category}</span>
                                <div style="font-size:0.95rem; font-weight:700; color:#F8FAFC; margin:2px 0 4px 0;">{item.title}</div>
                            </div>
                            <div>{_severity_badge_html(item.severity)}</div>
                        </div>
                        <div style="font-size:0.83rem; color:#CBD5E1; margin-bottom:4px;">
                            <b>Measured:</b> <code>{item.measured_value_str}</code> &nbsp;|&nbsp;
                            <b>Limit / Target:</b> <code>{item.limit_value_str}</code> &nbsp;|&nbsp;
                            <b>Margin:</b> <code>{item.margin_str}</code>
                        </div>
                        <div style="font-size:0.84rem; color:#94A3B8;">{item.explanation}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            st.warning(f"**Flight-Safety Engineering Disclaimer:** {cp.engineering_disclaimer}")

    # =========================================================================
    # TAB 3: STEP 4 — COMPARE CONFIGURATIONS (MODULE F)
    # =========================================================================
    with tabs[3]:
        st.subheader("Step 4 — Multi-Configuration Trade Study Comparison")
        st.caption(
            "Compare total thrust, TWR, hover throttle, electrical power, battery energy, flight endurance, "
            "and payload margins across saved multirotor architectures."
        )

        selected_cmp_ids: List[str] = st.multiselect(
            "Select Configurations to Compare",
            options=[c.config_id for c in all_configs],
            default=[c.config_id for c in all_configs],
            format_func=lambda cid: config_options[cid],
        )

        if not selected_cmp_ids:
            st.info("Select at least one configuration above to display comparison charts and tables.")
        else:
            cmp_analyses: List[CompleteConfigurationAnalysis] = []
            for cid in selected_cmp_ids:
                cfg_obj = repo.get_configuration(cid)
                if cfg_obj is not None:
                    ds_obj = datasets_by_id.get(cfg_obj.dataset_id, all_datasets[0])
                    cmp_analyses.append(evaluate_configuration(cfg_obj, ds_obj))

            cmp_rows = compare_configurations(cmp_analyses)
            st.plotly_chart(build_configuration_comparison_chart(cmp_rows), width="stretch", key="cmp_bar_chart")

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
    # TAB 4: STEP 5 — GENERATE ENGINEERING REPORT (MODULE H)
    # =========================================================================
    with tabs[4]:
        st.subheader("Step 5 — Generate & Export Engineering Reports")
        st.caption(
            "Download a formal engineering dossier containing component specifications, governing equations, "
            "analysis results, compatibility audits, data provenance, and operational limitations."
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

        with st.expander("Preview Full Engineering Dossier", expanded=True):
            st.markdown(md_text)


if __name__ == "__main__":
    main()
