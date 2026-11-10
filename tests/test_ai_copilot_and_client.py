"""Automated tests for Gemini API client, graceful degradation, and Copilot session state."""

import os
from unittest.mock import MagicMock, patch

from rotorlab.ai.client import get_gemini_client, get_gemini_model_name, has_gemini_api_key
from rotorlab.ai.copilot import RotorLabCopilot


def test_client_missing_api_key_returns_none():
    with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=True):
        client = get_gemini_client()
        assert client is None
        assert has_gemini_api_key() is False


def test_copilot_missing_key_graceful_degradation():
    with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=True):
        copilot = RotorLabCopilot(api_key=None)
        assert copilot.is_available is False

        response = copilot.send_message("What is the TWR of my drone?")
        assert response["status"] == "error"
        assert "Gemini API key is not configured" in response["message"]
        assert response["tool_calls"] == []


def test_model_name_configurable_via_env():
    with patch.dict(os.environ, {"GEMINI_MODEL": "gemini-2.5-pro"}):
        assert get_gemini_model_name() == "gemini-2.5-pro"

    with patch.dict(os.environ, {}, clear=True):
        # Fallback default
        assert get_gemini_model_name() == "gemini-3.5-flash"


def test_copilot_switch_active_config_resets_chat():
    copilot = RotorLabCopilot(active_config_id="cfg_endurance_quad_4s")
    assert copilot.active_config_id == "cfg_endurance_quad_4s"

    copilot.set_active_config_id("cfg_heavylift_hexa_6s")
    assert copilot.active_config_id == "cfg_heavylift_hexa_6s"
    assert copilot._chat is None
