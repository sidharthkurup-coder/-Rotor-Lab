"""Dynamic Custom Aircraft Configuration Builder for RotorLab.

Allows engineers to create, configure, and persist custom UAV architectures from scratch
with arbitrary rotor counts, custom motor/prop/ESC/battery specifications, and linked datasets.
"""

from __future__ import annotations

import re
import uuid
import streamlit as st

from rotorlab.data.repository import RotorLabRepository
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


@st.dialog("➕ Create Custom UAV Configuration")
def render_new_aircraft_dialog(repo: RotorLabRepository) -> None:
    """Modal dialog allowing the creation of arbitrary custom UAV configurations."""
    st.markdown("#### Aircraft Architecture & Mission Specifications")
    st.caption("Specify your multirotor airframe, rotor count, mass budget, and propulsion subsystem.")

    col1, col2 = st.columns(2)
    with col1:
        cfg_name = st.text_input("Aircraft Name", value="Valkyrie-Custom Quad", help="Human-readable configuration identifier")
        frame_type = st.selectbox(
            "Airframe Topology",
            options=[
                "Quadcopter (X4)",
                "Hexacopter (X6)",
                "Octocopter (X8)",
                "Coaxial Octocopter (X8)",
                "Tricopter (Y3)",
                "Custom Multirotor",
            ],
            index=0,
        )
        default_rotors = 4
        if "Hexacopter" in frame_type:
            default_rotors = 6
        elif "Octocopter" in frame_type:
            default_rotors = 8
        elif "Tricopter" in frame_type:
            default_rotors = 3

        num_motors = st.number_input("Rotor Count", min_value=1, max_value=32, value=default_rotors)
        dry_mass_kg = st.number_input("Airframe Empty Mass (kg)", min_value=0.1, max_value=500.0, value=1.5, step=0.1, help="Total mass including frame, wiring, battery, and motors without mission payload")
        payload_mass_kg = st.number_input("Mission Payload Mass (kg)", min_value=0.0, max_value=500.0, value=0.5, step=0.1, help="Gimbal, camera, sensor, lidar, or cargo payload mass")

    with col2:
        cfg_desc = st.text_input("Mission Description", value="Custom engineered multirotor configuration")
        op_throttle = st.slider("Target Operating Throttle (%)", min_value=20.0, max_value=90.0, value=65.0, step=1.0)
        aux_power_w = st.number_input("Avionics Auxiliary Power (W)", min_value=0.0, max_value=200.0, value=8.0, step=1.0, help="Power drawn by flight controller, companion computer, GNSS, and telemetry")
        altitude_m = st.number_input("Operating Altitude MSL (m)", min_value=0.0, max_value=6000.0, value=0.0, step=50.0)

    st.divider()
    st.markdown("#### Propulsion Subsystem")

    # Catalog motors, props, ESCs, batteries for quick auto-fill
    stored_motors = repo.list_components("motor")
    stored_props = repo.list_components("propeller")
    stored_escs = repo.list_components("esc")
    stored_bats = repo.list_components("battery")

    col_m, col_p = st.columns(2)
    with col_m:
        st.markdown("**BLDC Motor**")
        motor_choice = st.selectbox(
            "Select Motor Preset or Custom",
            options=["Custom Motor Entry"] + [f"{m['name']} [{m['provenance']}]" for m in stored_motors],
            index=0,
        )
        if motor_choice != "Custom Motor Entry":
            idx = [f"{m['name']} [{m['provenance']}]" for m in stored_motors].index(motor_choice)
            mspec = stored_motors[idx]["spec"]
            m_mfg = st.text_input("Motor Manufacturer", value=mspec.get("manufacturer", "T-Motor"))
            m_model = st.text_input("Motor Model", value=mspec.get("model", "MN4006"))
            m_kv = st.number_input("Motor KV (RPM/V)", min_value=10.0, max_value=5000.0, value=float(mspec.get("kv_rating", 380.0)))
            m_imax = st.number_input("Max Continuous Current (A)", min_value=1.0, max_value=200.0, value=float(mspec.get("max_continuous_current_a", 20.0)))
            m_pmax = st.number_input("Max Continuous Power (W)", min_value=10.0, max_value=10000.0, value=float(mspec.get("max_continuous_power_w", 350.0)))
            m_mass = st.number_input("Motor Mass (g)", min_value=5.0, max_value=2000.0, value=float(mspec.get("mass_g", 80.0)))
        else:
            m_mfg = st.text_input("Motor Manufacturer", value="T-Motor")
            m_model = st.text_input("Motor Model", value="Custom-KV400")
            m_kv = st.number_input("Motor KV (RPM/V)", min_value=10.0, max_value=5000.0, value=400.0)
            m_imax = st.number_input("Max Continuous Current (A)", min_value=1.0, max_value=200.0, value=25.0)
            m_pmax = st.number_input("Max Continuous Power (W)", min_value=10.0, max_value=10000.0, value=450.0)
            m_mass = st.number_input("Motor Mass (g)", min_value=5.0, max_value=2000.0, value=95.0)

    with col_p:
        st.markdown("**Propeller Geometry**")
        prop_choice = st.selectbox(
            "Select Propeller Preset or Custom",
            options=["Custom Propeller Entry"] + [f"{p['name']} [{p['provenance']}]" for p in stored_props],
            index=0,
        )
        if prop_choice != "Custom Propeller Entry":
            idx = [f"{p['name']} [{p['provenance']}]" for p in stored_props].index(prop_choice)
            pspec = stored_props[idx]["spec"]
            p_mfg = st.text_input("Propeller Manufacturer", value=pspec.get("manufacturer", "APC"))
            p_model = st.text_input("Propeller Model", value=pspec.get("model", "MR"))
            p_dia = st.number_input("Diameter (inches)", min_value=3.0, max_value=40.0, value=float(pspec.get("diameter_in", 14.0)))
            p_pitch = st.number_input("Pitch (inches)", min_value=1.0, max_value=25.0, value=float(pspec.get("pitch_in", 4.7)))
        else:
            p_mfg = st.text_input("Propeller Manufacturer", value="APC")
            p_model = st.text_input("Propeller Model", value="Multi-Rotor")
            p_dia = st.number_input("Diameter (inches)", min_value=3.0, max_value=40.0, value=13.0)
            p_pitch = st.number_input("Pitch (inches)", min_value=1.0, max_value=25.0, value=4.5)

    col_e, col_b = st.columns(2)
    with col_e:
        st.markdown("**Electronic Speed Controller (ESC)**")
        esc_choice = st.selectbox(
            "Select ESC Preset or Custom",
            options=["Custom ESC Entry"] + [f"{e['name']} [{e['provenance']}]" for e in stored_escs],
            index=0,
        )
        if esc_choice != "Custom ESC Entry":
            idx = [f"{e['name']} [{e['provenance']}]" for e in stored_escs].index(esc_choice)
            espec = stored_escs[idx]["spec"]
            esc_name = st.text_input("ESC Name", value=espec.get("name", "40A Multi-Rotor ESC"))
            esc_cont = st.number_input("Continuous Rating (A)", min_value=5.0, max_value=300.0, value=float(espec.get("continuous_current_a", 40.0)))
            esc_peak = st.number_input("Burst / Peak Rating (A)", min_value=5.0, max_value=400.0, value=float(espec.get("peak_current_a", 50.0)))
        else:
            esc_name = st.text_input("ESC Name", value="Multi-Rotor 40A OPTO")
            esc_cont = st.number_input("Continuous Rating (A)", min_value=5.0, max_value=300.0, value=40.0)
            esc_peak = st.number_input("Burst / Peak Rating (A)", min_value=5.0, max_value=400.0, value=50.0)

    with col_b:
        st.markdown("**Flight Battery Subsystem**")
        bat_choice = st.selectbox(
            "Select Battery Preset or Custom",
            options=["Custom Battery Entry"] + [f"{b['name']} [{b['provenance']}]" for b in stored_bats],
            index=0,
        )
        if bat_choice != "Custom Battery Entry":
            idx = [f"{b['name']} [{b['provenance']}]" for b in stored_bats].index(bat_choice)
            bspec = stored_bats[idx]["spec"]
            bat_name = st.text_input("Battery Name", value=bspec.get("name", "LiPo Battery"))
            bat_cells = st.number_input("Cell Count (S)", min_value=2, max_value=16, value=int(bspec.get("cell_count_s", 4)))
            bat_cap = st.number_input("Capacity (mAh)", min_value=500.0, max_value=100000.0, value=float(bspec.get("capacity_mah", 5200.0)), step=100.0)
            bat_c = st.number_input("Continuous C-Rating", min_value=1.0, max_value=150.0, value=float(bspec.get("continuous_c_rating", 25.0)))
        else:
            bat_name = st.text_input("Battery Name", value="High-Discharge 4S LiPo")
            bat_cells = st.number_input("Cell Count (S)", min_value=2, max_value=16, value=4)
            bat_cap = st.number_input("Capacity (mAh)", min_value=500.0, max_value=100000.0, value=5000.0, step=100.0)
            bat_c = st.number_input("Continuous C-Rating", min_value=1.0, max_value=150.0, value=25.0)

    # Dataset selection
    all_datasets = repo.list_all_datasets()
    ds_options = {d.dataset_id: f"{d.display_label}" for d in all_datasets}
    st.divider()
    selected_ds_id = st.selectbox(
        "Link Performance Dataset",
        options=list(ds_options.keys()),
        format_func=lambda did: ds_options[did],
        help="Thrust stand measurements curve used to evaluate motor-propeller performance.",
    )

    if st.button("🚀 Assemble & Save Configuration", width="stretch", type="primary"):
        try:
            m_obj = MotorSpec(
                manufacturer=m_mfg.strip() or "Custom",
                model=m_model.strip() or "BLDC",
                kv_rating=float(m_kv),
                max_continuous_current_a=float(m_imax),
                max_continuous_power_w=float(m_pmax),
                mass_g=float(m_mass),
                min_cells_s=max(1, bat_cells - 1),
                max_cells_s=bat_cells + 2,
            )
            p_obj = PropellerSpec(
                manufacturer=p_mfg.strip() or "Custom",
                model=p_model.strip() or "Prop",
                diameter_in=float(p_dia),
                pitch_in=float(p_pitch),
            )
            e_obj = ESCSpec(
                name=esc_name.strip() or "ESC",
                continuous_current_a=float(esc_cont),
                peak_current_a=float(esc_peak),
                min_cells_s=max(1, bat_cells - 1),
                max_cells_s=bat_cells + 2,
            )
            nom_v = round(bat_cells * 3.7, 1)
            b_obj = BatterySpec(
                name=bat_name.strip() or "Battery",
                cell_count_s=int(bat_cells),
                nominal_voltage_v=nom_v,
                operating_voltage_v=nom_v,
                capacity_mah=float(bat_cap),
                continuous_c_rating=float(bat_c),
                burst_c_rating=float(bat_c * 1.5),
            )
            af_obj = AirframeSpec(
                frame_type=frame_type,
                num_motors=int(num_motors),
                aircraft_dry_mass_kg=float(dry_mass_kg),
                payload_mass_kg=float(payload_mass_kg),
                operating_throttle_pct=float(op_throttle),
                avionics_power_w=float(aux_power_w),
                altitude_m=float(altitude_m),
            )

            new_id = f"cfg_{re.sub(r'[^a-zA-Z0-9_]', '_', cfg_name.lower())[:16]}_{uuid.uuid4().hex[:6]}"
            new_config = PropulsionConfiguration(
                config_id=new_id,
                name=cfg_name.strip() or "Custom UAV Configuration",
                description=cfg_desc.strip(),
                motor=m_obj,
                propeller=p_obj,
                esc=e_obj,
                battery=b_obj,
                airframe=af_obj,
                dataset_id=selected_ds_id,
                margins=EngineeringMargins(),
            )

            repo.save_configuration(new_config)
            st.session_state["active_config_id"] = new_id
            st.toast(f"Configuration '{new_config.name}' saved and activated!")
            st.rerun()

        except Exception as exc:
            st.error(f"Configuration validation error: {str(exc)}")
