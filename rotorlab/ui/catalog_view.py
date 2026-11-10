"""Component and Dataset Catalog view for RotorLab.

Provides dynamic browsing, manual creation, CSV imports/exports, and explicit
data provenance tracking for motors, propellers, ESCs, batteries, and thrust stand curves.
"""

from __future__ import annotations

import io
from typing import Optional
import pandas as pd
import streamlit as st

from rotorlab.data.repository import RotorLabRepository
from rotorlab.models.domain import (
    BatterySpec,
    DataProvenance,
    ESCSpec,
    MotorSpec,
    PropellerSpec,
)


SAMPLE_MOTOR_CSV = """manufacturer,model,kv_rating,max_continuous_current_a,max_continuous_power_w,internal_resistance_mohm,no_load_current_a,min_cells_s,max_cells_s,mass_g
T-Motor,MN501-S,360,32.0,750.0,75.0,0.8,4,6,165.0
KDE Direct,KDE4215XF,465,42.0,1100.0,42.0,1.2,4,8,215.0
"""

SAMPLE_PROP_CSV = """manufacturer,model,diameter_in,pitch_in,num_blades,material,mass_g
T-Motor,CF-Prop,15.0,5.0,2,Carbon Fiber,22.0
APC,Multi-Rotor,12.0,4.5,2,Composite,14.5
"""

SAMPLE_ESC_CSV = """name,continuous_current_a,peak_current_a,min_cells_s,max_cells_s,mass_g
T-Motor Flame 60A,60.0,80.0,4,8,45.0
KDE KDEXF-UAS55,55.0,75.0,4,8,62.0
"""

SAMPLE_BATTERY_CSV = """name,cell_count_s,nominal_voltage_v,operating_voltage_v,capacity_mah,continuous_c_rating,burst_c_rating,usable_capacity_fraction,internal_resistance_per_cell_mohm,mass_g
Tattu R-Line 4S,4,14.8,14.8,5000.0,30.0,60.0,0.80,3.5,490.0
Gens Ace High-End 6S,6,22.2,22.2,10000.0,25.0,50.0,0.80,2.8,1250.0
"""


def render_catalog_view(repo: RotorLabRepository, active_cfg: Optional[Any] = None) -> None:
    """Render the dynamic Component & Dataset Catalog."""
    st.markdown(
        """
        <div class="rl-banner">
            <div class="rl-banner-top">
                <div>
                    <div class="rl-eyebrow">PROPULSION HARDWARE INVENTORY // DATA PROVENANCE ASSURANCE</div>
                    <h1 class="rl-title">Component & Dataset Catalog</h1>
                    <p class="rl-subtitle">
                        Browse, add, and import motors, propellers, ESCs, batteries, and thrust stand test datasets.
                        Every entry strictly tracks its data provenance and source reference.
                    </p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")

    catalog_tabs = st.tabs(
        [
            "📦 Component Inventory",
            "➕ Add Component Manually",
            "📥 CSV Bulk Import & Export",
            "📊 Thrust Stand Datasets",
        ]
    )

    # =========================================================================
    # TAB 1: BROWSE INVENTORY
    # =========================================================================
    with catalog_tabs[0]:
        col_f1, col_f2 = st.columns([1, 2])
        with col_f1:
            ctype_filter = st.selectbox(
                "Filter by Category",
                options=["All Categories", "motor", "propeller", "esc", "battery"],
                index=0,
            )
        with col_f2:
            search_query = st.text_input("Search Components", placeholder="Search by name, model, manufacturer...")

        filter_arg = None if ctype_filter == "All Categories" else ctype_filter
        components = repo.list_components(component_type=filter_arg)
        if search_query.strip():
            sq = search_query.lower().strip()
            components = [
                c for c in components
                if sq in c["name"].lower() or sq in c["manufacturer"].lower() or sq in c["component_type"].lower()
            ]

        st.caption(f"Showing **{len(components)}** verified propulsion components in workspace database.")

        for c in components:
            prov = c["provenance"]
            badge_class = (
                "rl-badge-pass"
                if prov == DataProvenance.MANUFACTURER_DATASHEET.value
                else ("rl-badge-warning" if prov == DataProvenance.USER_MEASURED.value else "rl-badge-critical")
            )

            with st.container():
                st.markdown(
                    f"""
                    <div class="rl-panel" style="margin-bottom: 10px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <span style="font-size:11px; text-transform:uppercase; letter-spacing:0.05em; color:#94a3b8;">
                                    {c['component_type'].upper()}
                                </span>
                                <h3 style="margin:2px 0 0 0; font-size:16px; color:#f8fafc;">{c['name']}</h3>
                            </div>
                            <span class="rl-badge {badge_class}">{prov.upper()}</span>
                        </div>
                        <div style="margin-top:6px; font-size:12px; color:#cbd5e1;">
                            Source / Reference: <code>{c['source_reference'] or 'Local workspace catalog'}</code>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                with st.expander(f"Inspect Specifications: {c['name']}", expanded=False):
                    st.json(c["spec"])
                    col_del, _ = st.columns([1, 4])
                    with col_del:
                        if st.button(f"🗑️ Delete", key=f"del_{c['component_id']}"):
                            repo.delete_component(c["component_id"])
                            st.toast(f"Deleted {c['name']}")
                            st.rerun()

    # =========================================================================
    # TAB 2: MANUAL COMPONENT ENTRY
    # =========================================================================
    with catalog_tabs[1]:
        st.markdown("#### Enter Custom Component Specifications")
        st.caption("All entries are validated against strict SI physics constraints before being stored.")

        ctype_new = st.selectbox("Component Category", ["motor", "propeller", "esc", "battery"], index=0)
        prov_new = st.selectbox(
            "Provenance Classification",
            options=[
                DataProvenance.USER_MEASURED.value,
                DataProvenance.MANUFACTURER_DATASHEET.value,
                DataProvenance.CALCULATED_ESTIMATE.value,
            ],
            index=0,
            help="Clearly distinguish user bench test measurements from manufacturer factory claims.",
        )
        src_ref = st.text_input("Source Reference / Test Bench Notes", value="Custom Thrust Stand Measurement")

        if ctype_new == "motor":
            col1, col2 = st.columns(2)
            with col1:
                m_mfg = st.text_input("Motor Brand / OEM", value="T-Motor")
                m_mdl = st.text_input("Motor Model", value="U11 KV120")
                m_kv = st.number_input("KV (RPM/V)", min_value=10.0, max_value=4000.0, value=120.0)
                m_imax = st.number_input("Max Continuous Current (A)", min_value=1.0, max_value=250.0, value=40.0)
            with col2:
                m_pmax = st.number_input("Max Continuous Power (W)", min_value=10.0, max_value=15000.0, value=1200.0)
                m_rm = st.number_input("Internal Resistance (mOhm)", min_value=1.0, max_value=1000.0, value=65.0)
                m_i0 = st.number_input("No-Load Idle Current (A)", min_value=0.0, max_value=10.0, value=1.1)
                m_mass = st.number_input("Mass (grams)", min_value=5.0, max_value=3000.0, value=280.0)

            if st.button("💾 Save Motor to Database", type="primary"):
                try:
                    ms = MotorSpec(
                        manufacturer=m_mfg.strip(),
                        model=m_mdl.strip(),
                        kv_rating=m_kv,
                        max_continuous_current_a=m_imax,
                        max_continuous_power_w=m_pmax,
                        internal_resistance_mohm=m_rm,
                        no_load_current_a=m_i0,
                        mass_g=m_mass,
                    )
                    repo.save_component("motor", ms, provenance=prov_new, source_reference=src_ref)
                    st.toast(f"Motor '{ms.full_name}' saved!")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Validation Error: {str(exc)}")

        elif ctype_new == "propeller":
            col1, col2 = st.columns(2)
            with col1:
                p_mfg = st.text_input("Propeller Brand / OEM", value="Mejzlik")
                p_mdl = st.text_input("Propeller Model", value="Heavy-Lift CF")
                p_dia = st.number_input("Diameter (in)", min_value=3.0, max_value=50.0, value=22.0)
            with col2:
                p_pit = st.number_input("Pitch (in)", min_value=1.0, max_value=30.0, value=7.0)
                p_bld = st.number_input("Number of Blades", min_value=1, max_value=6, value=2)
                p_mat = st.text_input("Material", value="Carbon Fiber")
                p_mass = st.number_input("Mass (grams)", min_value=1.0, max_value=500.0, value=48.0)

            if st.button("💾 Save Propeller to Database", type="primary"):
                try:
                    ps = PropellerSpec(
                        manufacturer=p_mfg.strip(),
                        model=p_mdl.strip(),
                        diameter_in=p_dia,
                        pitch_in=p_pit,
                        num_blades=int(p_bld),
                        material=p_mat.strip(),
                        mass_g=p_mass,
                    )
                    repo.save_component("propeller", ps, provenance=prov_new, source_reference=src_ref)
                    st.toast(f"Propeller saved!")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Validation Error: {str(exc)}")

        elif ctype_new == "esc":
            col1, col2 = st.columns(2)
            with col1:
                e_name = st.text_input("ESC Name", value="Flame 100A HV")
                e_icont = st.number_input("Continuous Current Rating (A)", min_value=5.0, max_value=400.0, value=100.0)
            with col2:
                e_ipeak = st.number_input("Peak / Burst Current Rating (A)", min_value=5.0, max_value=500.0, value=120.0)
                e_mass = st.number_input("Mass (grams)", min_value=1.0, max_value=500.0, value=75.0)

            if st.button("💾 Save ESC to Database", type="primary"):
                try:
                    es = ESCSpec(
                        name=e_name.strip(),
                        continuous_current_a=e_icont,
                        peak_current_a=e_ipeak,
                        mass_g=e_mass,
                    )
                    repo.save_component("esc", es, provenance=prov_new, source_reference=src_ref)
                    st.toast(f"ESC saved!")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Validation Error: {str(exc)}")

        elif ctype_new == "battery":
            col1, col2 = st.columns(2)
            with col1:
                b_name = st.text_input("Battery Model Name", value="Tattu 12S 22000mAh")
                b_s = st.number_input("Cell Count (S)", min_value=2, max_value=24, value=12)
                b_cap = st.number_input("Nominal Capacity (mAh)", min_value=500.0, max_value=150000.0, value=22000.0, step=500.0)
            with col2:
                b_crate = st.number_input("Continuous C-Rating", min_value=1.0, max_value=150.0, value=25.0)
                b_rm = st.number_input("Internal Resistance per Cell (mOhm)", min_value=0.5, max_value=30.0, value=2.0)
                b_mass = st.number_input("Battery Mass (grams)", min_value=50.0, max_value=20000.0, value=2600.0, step=50.0)

            if st.button("💾 Save Battery to Database", type="primary"):
                try:
                    nom_v = round(b_s * 3.7, 1)
                    bs = BatterySpec(
                        name=b_name.strip(),
                        cell_count_s=int(b_s),
                        nominal_voltage_v=nom_v,
                        operating_voltage_v=nom_v,
                        capacity_mah=b_cap,
                        continuous_c_rating=b_crate,
                        burst_c_rating=b_crate * 1.5,
                        internal_resistance_per_cell_mohm=b_rm,
                        mass_g=b_mass,
                    )
                    repo.save_component("battery", bs, provenance=prov_new, source_reference=src_ref)
                    st.toast(f"Battery saved!")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Validation Error: {str(exc)}")

    # =========================================================================
    # TAB 3: CSV IMPORT & EXPORT
    # =========================================================================
    with catalog_tabs[2]:
        st.markdown("#### Bulk CSV Operations")
        st.caption("Import multiple propulsion components at once or export your workspace database.")

        col_csv1, col_csv2 = st.columns(2)
        with col_csv1:
            st.markdown("**📥 Import Components from CSV**")
            imp_type = st.selectbox("Target Component Category", ["motor", "propeller", "esc", "battery"], key="csv_imp_type")
            imp_prov = st.selectbox(
                "Assign Data Provenance",
                options=[
                    DataProvenance.USER_MEASURED.value,
                    DataProvenance.MANUFACTURER_DATASHEET.value,
                    DataProvenance.CALCULATED_ESTIMATE.value,
                ],
                key="csv_imp_prov",
            )
            csv_file = st.file_uploader("Upload CSV File", type=["csv"], key="comp_csv_upload")

            # Sample template downloads
            sample_data = {
                "motor": SAMPLE_MOTOR_CSV,
                "propeller": SAMPLE_PROP_CSV,
                "esc": SAMPLE_ESC_CSV,
                "battery": SAMPLE_BATTERY_CSV,
            }[imp_type]

            st.download_button(
                label=f"📄 Download Sample {imp_type.upper()} CSV Template",
                data=sample_data,
                file_name=f"sample_{imp_type}_template.csv",
                mime="text/csv",
            )

            if csv_file is not None:
                if st.button("🚀 Process & Import CSV", type="primary"):
                    try:
                        content = csv_file.getvalue().decode("utf-8")
                        count = repo.import_components_csv(content, component_type=imp_type, provenance=imp_prov)
                        st.success(f"Successfully imported {count} {imp_type} records into catalog!")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"CSV Import Failed: {str(exc)}")

        with col_csv2:
            st.markdown("**📤 Export Components to CSV**")
            exp_type = st.selectbox("Select Category to Export", ["motor", "propeller", "esc", "battery"], key="csv_exp_type")
            exported_csv = repo.export_components_csv(exp_type)

            if exported_csv:
                st.download_button(
                    label=f"💾 Download All {exp_type.upper()}s (CSV)",
                    data=exported_csv,
                    file_name=f"rotorlab_{exp_type}_catalog.csv",
                    mime="text/csv",
                    width="stretch",
                )
            else:
                st.info(f"No custom or seeded {exp_type} entries found to export.")

    # =========================================================================
    # TAB 4: THRUST STAND PERFORMANCE DATASETS
    # =========================================================================
    with catalog_tabs[3]:
        st.markdown("#### Static Thrust Stand Performance Datasets")
        st.caption("Inspect and link verified dynamometer / thrust stand measurement curves.")

        all_datasets = repo.list_all_datasets()
        for ds in all_datasets:
            with st.expander(f"{ds.display_label} ({len(ds.points)} points)", expanded=False):
                st.markdown(
                    f"- **Motor:** `{ds.motor_manufacturer} {ds.motor_model} (KV{ds.motor_kv:.0f})`\n"
                    f"- **Propeller:** `{ds.propeller_model} ({ds.propeller_diameter_in}x{ds.propeller_pitch_in}\")`\n"
                    f"- **Test Voltage:** `{ds.test_voltage_v} V`\n"
                    f"- **Provenance:** `{ds.provenance.value}`\n"
                    f"- **Source Reference:** `{ds.source_reference}`\n"
                    f"- **Conditions:** `{ds.measurement_conditions}`"
                )
                df_pts = pd.DataFrame([
                    {
                        "Throttle (%)": p.throttle_pct,
                        "Voltage (V)": p.voltage_v,
                        "Current (A)": p.current_a,
                        "Thrust (gf)": p.thrust_gf,
                        "Power (W)": p.power_w,
                        "RPM": p.rpm,
                        "Efficacy (gf/W)": round(p.efficiency_gf_w, 2),
                    }
                    for p in ds.points
                ])
                st.dataframe(df_pts, width="stretch", hide_index=True)
