"""RotorLab AI Copilot agent with Google Gemini official SDK integration and engineering engine function calling."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

try:
    from google import genai
    from google.genai import types

    HAS_GENAI = True
except ImportError:
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]
    HAS_GENAI = False

from rotorlab.ai.client import get_gemini_client, get_gemini_model_name, has_gemini_api_key
from rotorlab.ai.tools import get_rotorlab_tools, get_tool_logger


COPILOT_SYSTEM_INSTRUCTION = """
You are RotorLab AI Copilot, a principal UAV propulsion systems engineer and multirotor flight performance expert.
You pair-program and co-engineer multirotor drones, quadcopters, hexacopters, octocopters, and heavy-lift UAVs.

CRITICAL ENGINEERING RULE:
You MUST NEVER fabricate, hallucinate, or guess numerical engineering figures (thrust, power, endurance, current, voltage sag, hover throttle percentage, or safety margins).
All numerical statistics and engineering evaluations MUST originate from calling RotorLab's deterministic engineering tools:
- run_propulsion_analysis(config_id, custom_payload_kg)
- calculate_thrust_to_weight(config_id, custom_payload_kg)
- calculate_hover_throttle(config_id, custom_payload_kg)
- calculate_battery_endurance(config_id, custom_payload_kg, reserve_percentage)
- check_component_compatibility(config_id)
- compare_aircraft_configurations(config_ids)
- analyse_motor_failure(config_id)
- retrieve_component_specifications(component_type, query)
- create_or_modify_aircraft_configuration(...)

HOW TO RESPOND TO COMMON USER REQUESTS:
1. "Design a drone / quadcopter for 2 kg payload":
   - Call retrieve_component_specifications to see existing components or aircraft.
   - Call create_or_modify_aircraft_configuration to generate and persist a concrete configuration.
   - Call run_propulsion_analysis to evaluate its real TWR, hover throttle %, and endurance.
   - Present the bill of materials (motor, prop, ESC, battery), AUW, and verified flight statistics.

2. "Calculate thrust-to-weight ratio" or "Can it carry more payload?":
   - Call calculate_thrust_to_weight(config_id, custom_payload_kg).
   - Explain the result against standard aerospace design rules (Hover margin >= 1.5, Recommended agile flight >= 2.0).

3. "What happens if one motor fails?":
   - Call analyse_motor_failure(config_id).
   - Report the degraded TWR(N-1) and static hover capability.
   - Detail the aerodynamic stability impact: Quadcopters cannot maintain attitude balance (yaw spin and tumble); Hexacopters and Octocopters have redundant control axes and can execute emergency controlled landing if TWR(N-1) > 1.1-1.2.

4. "How can I improve flight endurance?":
   - Call run_propulsion_analysis or calculate_battery_endurance.
   - Analyze specific trade-offs: larger low-pitch propellers for higher propulsive efficiency (gf/W), lower motor KV, high-energy-density LiPo/Li-Ion packs (higher Wh/kg), or payload mass reduction.

5. "Explain the calculations behind these results":
   - Detail the momentum theory equations: T = 2 * rho * A * v_i^2, Ideal Power P_ideal = T * v_i, Figure of Merit (FM), Peukert battery discharge, and internal resistance voltage sag V_terminal = V_ocv - I * R_internal.

CONVERSATION GUIDELINES:
- Maintain conversation context across turns. Allow the user to iteratively refine their aircraft.
- When referring to an aircraft or component, state its exact name, model, and data provenance (e.g. Manufacturer Measurements vs Illustrative Synthetic).
- Always include clear engineering units (N, gf, kg, W, A, V, %, min).
- If required parameters are missing to perform a specific calculation, politely ask the user for them rather than guessing.
"""


class RotorLabCopilot:
    """Conversational AI Copilot connected to Google Gemini and RotorLab's engineering engine."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        active_config_id: Optional[str] = None,
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name or get_gemini_model_name()
        self.active_config_id = active_config_id
        self._client: Optional[genai.Client] = None
        self._chat: Optional[Any] = None
        self._tool_logger = get_tool_logger()

    @property
    def is_available(self) -> bool:
        """Check whether Gemini is ready to process requests."""
        return has_gemini_api_key(self.api_key) and HAS_GENAI

    def _ensure_chat(self) -> Any:
        """Initialize or return the underlying Gemini chat session."""
        if self._chat is not None:
            return self._chat

        self._client = get_gemini_client(self.api_key)
        if not self._client or not HAS_GENAI or types is None:
            raise RuntimeError(
                "Gemini API is not configured. Please supply a valid GEMINI_API_KEY."
            )

        tools = get_rotorlab_tools()
        system_prompt = COPILOT_SYSTEM_INSTRUCTION
        if self.active_config_id:
            system_prompt += f"\n\nCURRENT ACTIVE AIRCRAFT CONTEXT: The user is currently inspecting aircraft with config_id='{self.active_config_id}'. Unless specified otherwise, default your analysis and calculations to this configuration."

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=tools,
            temperature=0.3,  # Controlled, focused engineering responses
        )

        self._chat = self._client.chats.create(
            model=self.model_name,
            config=config,
        )
        return self._chat

    def set_active_config_id(self, config_id: str) -> None:
        """Update active configuration context."""
        if self.active_config_id != config_id:
            self.active_config_id = config_id
            # Reset chat session so new active aircraft is part of system context
            self._chat = None

    def send_message(self, user_message: str) -> Dict[str, Any]:
        """Send a message to the AI Copilot and execute any necessary engineering function calls.

        Returns a dictionary containing:
            - response_text: The grounded engineering response from Gemini.
            - tool_calls: List of engineering tool calls executed during this turn.
            - status: 'success' or 'error'.
        """
        if not self.is_available:
            return {
                "status": "error",
                "message": (
                    "Gemini API key is not configured. Please provide a GEMINI_API_KEY "
                    "in your environment, in a local .env file, or in the sidebar settings."
                ),
                "tool_calls": [],
                "response_text": "",
            }

        # Clear tool logger before running this turn
        self._tool_logger.clear()

        try:
            chat = self._ensure_chat()
            response = chat.send_message(user_message)

            tool_calls = list(self._tool_logger.calls)

            return {
                "status": "success",
                "response_text": response.text or "",
                "tool_calls": tool_calls,
            }

        except Exception as exc:
            err_str = str(exc)
            # User friendly translation of common API exceptions
            if "API_KEY_INVALID" in err_str or "401" in err_str:
                msg = "The provided Gemini API key appears to be invalid. Please verify your key at Google AI Studio."
            elif "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                msg = "Gemini API rate limit or quota exceeded. Please wait a moment before trying again."
            else:
                msg = f"Gemini API communication error: {err_str}"

            return {
                "status": "error",
                "message": msg,
                "tool_calls": list(self._tool_logger.calls),
                "response_text": "",
            }

    def reset_conversation(self) -> None:
        """Clear conversation history."""
        self._chat = None
        self._tool_logger.clear()
