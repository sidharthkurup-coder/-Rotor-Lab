"""RotorLab AI Copilot interface: Conversational engineering assistant and PDF Datasheet Intelligence."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
import streamlit as st

from rotorlab.ai.client import get_gemini_model_name, has_gemini_api_key
from rotorlab.ai.copilot import RotorLabCopilot
from rotorlab.ai.datasheet import extract_datasheet_specifications
from rotorlab.data.repository import RotorLabRepository
from rotorlab.models.domain import (
    BatterySpec,
    DataProvenance,
    ESCSpec,
    MotorSpec,
    PerformanceDataset,
    PropellerSpec,
    PropulsionConfiguration,
)
from rotorlab.services.analyzer import CompleteConfigurationAnalysis


def render_copilot_view(
    repo: RotorLabRepository,
    active_cfg: PropulsionConfiguration,
    active_ds: PerformanceDataset,
    analysis: CompleteConfigurationAnalysis,
) -> None:
    """Render the AI Copilot conversational engineering interface and datasheet intelligence."""
    # Check for active API key (from environment, .env, or session state)
    session_api_key = st.session_state.get("gemini_api_key", "").strip() or None
    api_key_available = has_gemini_api_key(session_api_key)

    # Header and Context Banner
    st.markdown(
        f"""
        <div class="rl-banner">
            <div class="rl-banner-top">
                <div>
                    <div class="rl-eyebrow">AI COPILOT // GOOGLE GEMINI AEROSPACE REASONING & FUNCTION CALLING</div>
                    <h1 class="rl-title">RotorLab Engineering Copilot</h1>
                    <p class="rl-subtitle">
                        Co-engineer multirotor UAVs using natural language grounded directly in RotorLab's verified equations.
                    </p>
                </div>
                <div>
                    <span class="rl-badge {'rl-badge-pass' if api_key_available else 'rl-badge-info'}">
                        {'🟢 GEMINI ONLINE' if api_key_available else '⚪ API KEY REQUIRED'}
                    </span>
                </div>
            </div>
            <div class="rl-chip-row">
                <span class="rl-chip">Active Aircraft: <b>{active_cfg.name}</b></span>
                <span class="rl-chip">Frame: <b>{active_cfg.airframe.frame_type}</b></span>
                <span class="rl-chip">TWR: <b>{analysis.thrust.twr_max:.2f}</b></span>
                <span class="rl-chip">Hover Throttle: <b>{analysis.thrust.hover_single_motor_state.throttle_pct if analysis.thrust.hover_single_motor_state else 100:.1f}%</b></span>
                <span class="rl-chip">Model: <b>{get_gemini_model_name()}</b></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")

    if not api_key_available:
        # Graceful degradation notice and in-app API key configuration
        st.markdown(
            """
            <div class="rl-panel">
                <p class="rl-panel-title">🔑 Connect Google Gemini API Key</p>
                <p class="rl-panel-desc">
                    To activate the AI Copilot, natural-language UAV trade studies, and PDF Datasheet Intelligence,
                    please supply a Google Gemini API Key. All calculations are executed via deterministic function calling.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_k1, col_k2 = st.columns([2, 1])
        with col_k1:
            entered_key = st.text_input(
                "Gemini API Key",
                type="password",
                help="Your key is held in session memory only and never saved to disk or repository files.",
                placeholder="AIzaSy...",
            )
            if st.button("🚀 Connect AI Copilot", type="primary", width="stretch"):
                if entered_key.strip():
                    st.session_state["gemini_api_key"] = entered_key.strip()
                    os.environ["GEMINI_API_KEY"] = entered_key.strip()
                    st.toast("Gemini API key connected for this session!")
                    st.rerun()
                else:
                    st.warning("Please enter a non-empty API key.")

        with col_k2:
            st.info(
                "**Get an API Key:**\n"
                "1. Visit [Google AI Studio](https://aistudio.google.com/app/apikey).\n"
                "2. Create a free Gemini API key.\n"
                "3. Alternatively, create a `.env` file with `GEMINI_API_KEY=your_key`.\n\n"
                "*Note: The 5-step Engineering Workspace remains 100% functional offline without an API key.*"
            )
        return

    # Tabs inside AI Copilot: Chat Copilot vs Datasheet Intelligence
    copilot_tabs = st.tabs(
        [
            "💬 Natural Language Engineering Copilot",
            "📑 PDF Datasheet Intelligence",
        ]
    )

    # Initialize Copilot instance
    copilot = RotorLabCopilot(
        api_key=session_api_key,
        active_config_id=active_cfg.config_id,
    )

    # =========================================================================
    # TAB 1: CONVERSATIONAL COPILOT
    # =========================================================================
    with copilot_tabs[0]:
        st.caption("Ask questions, explore trade studies, or describe custom multirotor missions. The AI Copilot invokes RotorLab's engineering engine automatically.")

        # Quick Starter Prompts
        st.markdown("**Quick Engineering Starters:**")
        q_cols1 = st.columns(3)
        q_cols2 = st.columns(3)

        send_prompt: Optional[str] = None
        with q_cols1[0]:
            if st.button("🚀 Design 2kg Payload Quad", width="stretch"):
                send_prompt = "Design a quadcopter capable of carrying a 2 kg payload with at least 25 minutes of endurance. Suggest a suitable motor, propeller, ESC and battery combination, and assemble the configuration."
        with q_cols1[1]:
            if st.button("⚖️ Calculate Thrust-to-Weight", width="stretch"):
                send_prompt = f"Calculate the thrust-to-weight ratio and hover throttle of the active configuration ({active_cfg.name}). Explain if it meets recommended aerospace agility standards."
        with q_cols1[2]:
            if st.button("⏱️ Improve Flight Endurance", width="stretch"):
                send_prompt = f"How can I improve the flight endurance of {active_cfg.name}? Analyze its current power consumption, motor efficiency, and battery capacity, and suggest specific hardware modifications."

        with q_cols2[0]:
            if st.button("💥 Single Motor Failure (N-1)", width="stretch"):
                send_prompt = f"What happens if one motor fails in flight on {active_cfg.name}? Analyze the degraded thrust-to-weight ratio and explain if attitude control can be maintained."
        with q_cols2[1]:
            if st.button("📊 Quad vs Hexa Comparison", width="stretch"):
                send_prompt = "Compare quadcopter (X4) and hexacopter (X6) architectures. When should an engineer choose an X6 hexacopter over an X4 quadcopter for heavy-lift and safety-critical missions?"
        with q_cols2[2]:
            if st.button("📐 Explain Calculations", width="stretch"):
                send_prompt = f"Explain the engineering calculations behind the performance results for {active_cfg.name}, including momentum theory, Figure of Merit, and internal resistance voltage sag."

        st.divider()

        # Chat history state
        if "chat_messages" not in st.session_state:
            st.session_state["chat_messages"] = [
                {
                    "role": "assistant",
                    "content": (
                        f"Hello! I am your RotorLab Aerospace Copilot. I'm connected to the deterministic propulsion engine "
                        f"and currently inspecting **{active_cfg.name}** ({active_cfg.airframe.frame_type}, AUW {analysis.thrust.total_mass_kg:.2f} kg, TWR {analysis.thrust.twr_max:.2f}).\n\n"
                        "How can I assist your multirotor propulsion engineering today?"
                    ),
                    "tool_calls": [],
                }
            ]

        # Render conversation history
        for msg in st.session_state["chat_messages"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg.get("tool_calls"):
                    with st.expander(f"⚙️ Engine Function Calls ({len(msg['tool_calls'])})", expanded=False):
                        for tc in msg["tool_calls"]:
                            st.markdown(f"**Tool Invoked:** `{tc['tool_name']}`")
                            st.json(tc["args"])
                            st.caption("Engine Return:")
                            st.json(tc["result"])

        # Handle user prompt from input bar or quick starter
        chat_input = st.chat_input("Ask an aerospace engineering question or describe a drone configuration...")
        active_user_prompt = send_prompt or chat_input

        if active_user_prompt:
            # Append user message
            st.session_state["chat_messages"].append({"role": "user", "content": active_user_prompt, "tool_calls": []})

            with st.spinner("RotorLab Copilot is evaluating engineering equations..."):
                response_dict = copilot.send_message(active_user_prompt)

            if response_dict["status"] == "success":
                st.session_state["chat_messages"].append(
                    {
                        "role": "assistant",
                        "content": response_dict["response_text"],
                        "tool_calls": response_dict["tool_calls"],
                    }
                )
            else:
                st.session_state["chat_messages"].append(
                    {
                        "role": "assistant",
                        "content": f"⚠️ **Error:** {response_dict['message']}",
                        "tool_calls": response_dict["tool_calls"],
                    }
                )

            st.rerun()

        col_clr, _ = st.columns([1, 4])
        with col_clr:
            if st.button("🗑️ Clear Chat History"):
                st.session_state["chat_messages"] = []
                copilot.reset_conversation()
                st.rerun()

    # =========================================================================
    # TAB 2: PDF DATASHEET INTELLIGENCE
    # =========================================================================
    with copilot_tabs[1]:
        st.markdown("#### 📄 Document Intelligence for Manufacturer Datasheets")
        st.caption(
            "Upload motor, propeller, ESC, or battery manufacturer PDF datasheets. Gemini multimodal document understanding "
            "extracts key electrical/aerodynamic parameters and thrust stand measurement curves for your review."
        )

        uploaded_pdf = st.file_uploader(
            "Choose a Datasheet File (PDF, PNG, JPG)",
            type=["pdf", "png", "jpg", "jpeg"],
            help="Upload an official component datasheet, bench test report, or manufacturer specification sheet.",
        )

        if uploaded_pdf is not None:
            col_u1, col_u2 = st.columns([1, 2])
            with col_u1:
                st.markdown(f"**File:** `{uploaded_pdf.name}` ({len(uploaded_pdf.getvalue()) / 1024:.1f} KB)")
                if st.button("🔍 Extract Specifications with Gemini", type="primary", width="stretch"):
                    with st.spinner("Analyzing document structure, specification tables, and test curves..."):
                        mime = uploaded_pdf.type or "application/pdf"
                        res = extract_datasheet_specifications(
                            pdf_bytes=uploaded_pdf.getvalue(),
                            filename=uploaded_pdf.name,
                            api_key=session_api_key,
                            mime_type=mime,
                        )
                        st.session_state["datasheet_result"] = res

            with col_u2:
                st.caption(
                    "Datasheet Intelligence extracts:\n"
                    "- Motor: KV, continuous current, power, internal resistance, mass.\n"
                    "- Propeller: Diameter, pitch, blade count, material.\n"
                    "- ESC: Continuous and peak current limits, voltage range.\n"
                    "- Battery: Cell count, nominal voltage, capacity, C-rating.\n"
                    "- Static thrust curves (throttle, current, thrust gf, RPM)."
                )

        # Display extracted datasheet review card if available
        if "datasheet_result" in st.session_state and st.session_state["datasheet_result"]:
            res = st.session_state["datasheet_result"]
            if res.get("status") == "error":
                st.error(res.get("message", "Error extracting datasheet."))
            else:
                data = res.get("data", {})
                st.divider()
                st.markdown("### 📋 Extracted Specifications Review Card")
                st.caption("⚠️ Please review and verify all extracted specifications before committing to the database.")

                conf = data.get("confidence", "MEDIUM").upper()
                conf_badge = "rl-badge-pass" if conf == "HIGH" else ("rl-badge-warning" if conf == "MEDIUM" else "rl-badge-critical")

                st.markdown(
                    f"""
                    <div class="rl-panel">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <b>Document: {res.get('filename')}</b>
                            <span class="rl-badge {conf_badge}">EXTRACTION CONFIDENCE: {conf}</span>
                        </div>
                        <p style="margin-top:8px; font-size:13px; color:#cbd5e1;">
                            {data.get('confidence_explanation', 'No specific ambiguities reported.')}
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                ctype = st.selectbox(
                    "Component Type",
                    options=["motor", "propeller", "esc", "battery", "thrust_table"],
                    index=["motor", "propeller", "esc", "battery", "thrust_table"].index(data.get("component_type", "motor"))
                    if data.get("component_type") in ["motor", "propeller", "esc", "battery", "thrust_table"]
                    else 0,
                )
                mfg = st.text_input("Manufacturer", value=data.get("manufacturer") or "T-Motor")
                mdl = st.text_input("Model", value=data.get("model") or "Extracted Model")

                prov_choice = st.selectbox(
                    "Data Provenance Label",
                    options=[
                        DataProvenance.MANUFACTURER_DATASHEET.value,
                        DataProvenance.USER_MEASURED.value,
                        DataProvenance.CALCULATED_ESTIMATE.value,
                    ],
                    index=0,
                    help="Manufacturer measurements are verified from official factory test benches.",
                )

                if ctype == "motor":
                    m_data = data.get("motor", {})
                    col_m1, col_m2, col_m3 = st.columns(3)
                    with col_m1:
                        kv = st.number_input("KV Rating (RPM/V)", value=float(m_data.get("kv_rating") or 400.0))
                        imax = st.number_input("Max Current (A)", value=float(m_data.get("max_continuous_current_a") or 25.0))
                    with col_m2:
                        pmax = st.number_input("Max Power (W)", value=float(m_data.get("max_continuous_power_w") or 450.0))
                        rm = st.number_input("Internal Resistance (mOhm)", value=float(m_data.get("internal_resistance_mohm") or 100.0))
                    with col_m3:
                        i0 = st.number_input("No Load Current (A)", value=float(m_data.get("no_load_current_a") or 0.6))
                        mass = st.number_input("Mass (g)", value=float(m_data.get("mass_g") or 90.0))

                    if st.button("✅ Confirm & Save Motor to Catalog", type="primary"):
                        ms = MotorSpec(
                            manufacturer=mfg,
                            model=mdl,
                            kv_rating=kv,
                            max_continuous_current_a=imax,
                            max_continuous_power_w=pmax,
                            internal_resistance_mohm=rm,
                            no_load_current_a=i0,
                            mass_g=mass,
                        )
                        cid = repo.save_component("motor", ms, provenance=prov_choice, source_reference=f"Datasheet: {res.get('filename')}")
                        st.toast(f"Motor '{ms.full_name}' saved to catalog (ID: {cid})!")
                        st.session_state["datasheet_result"] = None
                        st.rerun()

                elif ctype == "propeller":
                    p_data = data.get("propeller", {})
                    col_p1, col_p2 = st.columns(2)
                    with col_p1:
                        dia = st.number_input("Diameter (in)", value=float(p_data.get("diameter_in") or 13.0))
                        pitch = st.number_input("Pitch (in)", value=float(p_data.get("pitch_in") or 4.5))
                    with col_p2:
                        mat = st.text_input("Material", value=p_data.get("material") or "Carbon Fiber")
                        mass = st.number_input("Mass (g)", value=float(p_data.get("mass_g") or 18.0))

                    if st.button("✅ Confirm & Save Propeller to Catalog", type="primary"):
                        ps = PropellerSpec(
                            manufacturer=mfg,
                            model=mdl,
                            diameter_in=dia,
                            pitch_in=pitch,
                            material=mat,
                            mass_g=mass,
                        )
                        cid = repo.save_component("propeller", ps, provenance=prov_choice, source_reference=f"Datasheet: {res.get('filename')}")
                        st.toast(f"Propeller saved to catalog (ID: {cid})!")
                        st.session_state["datasheet_result"] = None
                        st.rerun()

                elif ctype == "esc":
                    e_data = data.get("esc", {})
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        icont = st.number_input("Continuous Current (A)", value=float(e_data.get("continuous_current_a") or 40.0))
                    with col_e2:
                        ipeak = st.number_input("Peak Current (A)", value=float(e_data.get("peak_current_a") or 50.0))

                    if st.button("✅ Confirm & Save ESC to Catalog", type="primary"):
                        es = ESCSpec(
                            name=f"{mfg} {mdl}",
                            continuous_current_a=icont,
                            peak_current_a=ipeak,
                        )
                        cid = repo.save_component("esc", es, provenance=prov_choice, source_reference=f"Datasheet: {res.get('filename')}")
                        st.toast(f"ESC saved to catalog (ID: {cid})!")
                        st.session_state["datasheet_result"] = None
                        st.rerun()

                elif ctype == "battery":
                    b_data = data.get("battery", {})
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        cells = st.number_input("Cell Count (S)", value=int(b_data.get("cell_count_s") or 4))
                        cap = st.number_input("Capacity (mAh)", value=float(b_data.get("capacity_mah") or 5000.0))
                    with col_b2:
                        crate = st.number_input("Continuous C-Rating", value=float(b_data.get("continuous_c_rating") or 25.0))
                        mass = st.number_input("Mass (g)", value=float(b_data.get("mass_g") or 450.0))

                    if st.button("✅ Confirm & Save Battery to Catalog", type="primary"):
                        nom_v = round(cells * 3.7, 1)
                        bs = BatterySpec(
                            name=f"{mfg} {mdl}",
                            cell_count_s=cells,
                            nominal_voltage_v=nom_v,
                            operating_voltage_v=nom_v,
                            capacity_mah=cap,
                            continuous_c_rating=crate,
                            burst_c_rating=crate * 1.5,
                            mass_g=mass,
                        )
                        cid = repo.save_component("battery", bs, provenance=prov_choice, source_reference=f"Datasheet: {res.get('filename')}")
                        st.toast(f"Battery saved to catalog (ID: {cid})!")
                        st.session_state["datasheet_result"] = None
                        st.rerun()
