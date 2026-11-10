"""RotorLab AI Copilot, engineering function calling, and datasheet intelligence."""

from rotorlab.ai.client import get_gemini_client, get_gemini_model_name, has_gemini_api_key
from rotorlab.ai.copilot import RotorLabCopilot
from rotorlab.ai.tools import get_rotorlab_tools

__all__ = [
    "get_gemini_client",
    "get_gemini_model_name",
    "has_gemini_api_key",
    "RotorLabCopilot",
    "get_rotorlab_tools",
]
