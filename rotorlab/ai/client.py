"""Google Gemini API client initialization and configuration using the official Google Gen AI Python SDK."""

from __future__ import annotations

import os
from typing import Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

try:
    from google import genai

    HAS_GENAI_SDK = True
except ImportError:
    genai = None  # type: ignore[assignment]
    HAS_GENAI_SDK = False


DEFAULT_MODEL = "gemini-2.5-flash"


def get_gemini_model_name() -> str:
    """Return the configured Gemini model name from environment or default."""
    return os.environ.get("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def resolve_api_key(api_key: Optional[str] = None) -> Optional[str]:
    """Resolve Gemini API key from explicit argument or environment variable."""
    if api_key and api_key.strip():
        return api_key.strip()
    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    return env_key if env_key else None


def has_gemini_api_key(api_key: Optional[str] = None) -> bool:
    """Check whether a non-empty Gemini API key is available."""
    return resolve_api_key(api_key) is not None


def get_gemini_client(api_key: Optional[str] = None) -> Optional[genai.Client]:
    """Initialize and return a google-genai Client instance if API key is configured.

    Returns None if no API key is provided or if google-genai SDK is not installed.
    Never crashes the application when API key is missing.
    """
    if not HAS_GENAI_SDK or genai is None:
        return None

    key = resolve_api_key(api_key)
    if not key:
        return None

    try:
        return genai.Client(api_key=key)
    except Exception:
        return None
