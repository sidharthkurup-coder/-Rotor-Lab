"""Datasheet Intelligence service using Google Gemini multimodal document understanding.

Extracts structured motor, propeller, ESC, and battery specifications and static thrust
tables from PDF datasheets. Ensures data provenance is tracked and prompts the user
to review extracted specifications before saving into RotorLab's catalog.
"""

from __future__ import annotations

import io
import json
import re
from typing import Any, Dict, List, Optional

try:
    from google import genai
    from google.genai import types

    HAS_GENAI = True
except ImportError:
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]
    HAS_GENAI = False

try:
    import pypdf

    HAS_PYPDF = True
except ImportError:
    pypdf = None  # type: ignore[assignment]
    HAS_PYPDF = False

from rotorlab.ai.client import get_gemini_client, get_gemini_model_name
from rotorlab.models.domain import DataProvenance


DATASHEET_EXTRACTION_PROMPT = """
You are an expert aerospace and multirotor propulsion engineer analyzing a component datasheet or test report.
Extract all UAV propulsion engineering specifications from the document.

You MUST return a strictly valid JSON object conforming to the following structure:
{
  "component_type": "motor" | "propeller" | "esc" | "battery" | "thrust_table" | "aircraft",
  "manufacturer": "string (brand or OEM name)",
  "model": "string (exact model number or part name)",
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "confidence_explanation": "string explaining if any values were assumed, unclear, or extrapolated",
  "verification_required": true | false,
  "data_provenance": "Manufacturer Measurements" | "User-Supplied Measurements" | "Calculated Estimate",
  "motor": {
    "kv_rating": float or null,
    "max_continuous_current_a": float or null,
    "max_continuous_power_w": float or null,
    "internal_resistance_mohm": float or null,
    "no_load_current_a": float or null,
    "min_cells_s": int or null,
    "max_cells_s": int or null,
    "mass_g": float or null
  },
  "propeller": {
    "diameter_in": float or null,
    "pitch_in": float or null,
    "num_blades": int or null,
    "material": "string" or null,
    "mass_g": float or null
  },
  "esc": {
    "continuous_current_a": float or null,
    "peak_current_a": float or null,
    "min_cells_s": int or null,
    "max_cells_s": int or null,
    "mass_g": float or null
  },
  "battery": {
    "cell_count_s": int or null,
    "nominal_voltage_v": float or null,
    "capacity_mah": float or null,
    "continuous_c_rating": float or null,
    "burst_c_rating": float or null,
    "mass_g": float or null
  },
  "thrust_points": [
    {
      "throttle_pct": float (0-100),
      "voltage_v": float,
      "current_a": float,
      "thrust_gf": float,
      "power_w": float,
      "rpm": float
    }
  ],
  "test_voltage_v": float or null,
  "notes": "string with any additional test conditions, ambient temp, or notes"
}

Important Instructions:
1. If numerical values are clearly printed in tables or specs, set confidence to "HIGH" and verification_required to false.
2. If values are blurry, ambiguous, or missing key parameters, set confidence to "MEDIUM" or "LOW", set verification_required to true, and explain clearly in confidence_explanation.
3. If thrust stand measurement points are present (throttle, current, thrust, etc.), extract them in order under "thrust_points".
4. Output strictly valid JSON with no markdown backticks or commentary outside the JSON object.
"""


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Fallback text extractor using pypdf if multimodal upload needs text accompaniment."""
    if not HAS_PYPDF or pypdf is None:
        return ""
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        pages_text = []
        for i, page in enumerate(reader.pages[:10]):  # Limit to first 10 pages
            text = page.extract_text()
            if text:
                pages_text.append(f"--- Page {i+1} ---\n{text}")
        return "\n\n".join(pages_text)
    except Exception:
        return ""


def extract_datasheet_specifications(
    pdf_bytes: bytes,
    filename: str,
    api_key: Optional[str] = None,
    mime_type: str = "application/pdf",
) -> Dict[str, Any]:
    """Process an uploaded PDF datasheet using Gemini multimodal document understanding.

    Extracts component parameters and thrust curves into structured data for user verification.
    """
    client = get_gemini_client(api_key)
    if not client or not HAS_GENAI or types is None:
        return {
            "status": "error",
            "message": "Gemini API key is required to analyze datasheets with AI. Please set GEMINI_API_KEY.",
        }

    model_name = get_gemini_model_name()

    try:
        # Construct multimodal contents: PDF file part + instruction prompt
        part = types.Part.from_bytes(data=pdf_bytes, mime_type=mime_type)
        contents = [
            part,
            f"Datasheet filename: {filename}\n\n{DATASHEET_EXTRACTION_PROMPT}",
        ]

        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,  # Low temperature for strict factual extraction
            ),
        )

        response_text = response.text or ""
        # Clean potential markdown fences
        clean_json_str = re.sub(r"^```(?:json)?\s*", "", response_text.strip(), flags=re.MULTILINE)
        clean_json_str = re.sub(r"\s*```$", "", clean_json_str.strip(), flags=re.MULTILINE)

        parsed_data = json.loads(clean_json_str)
        return {
            "status": "success",
            "filename": filename,
            "data": parsed_data,
        }

    except Exception as exc:
        # Try fallback using extracted text if direct PDF upload failed
        fallback_text = extract_text_from_pdf(pdf_bytes)
        if fallback_text:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        f"Datasheet text extracted from {filename}:\n\n{fallback_text}\n\n{DATASHEET_EXTRACTION_PROMPT}"
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1,
                    ),
                )
                response_text = response.text or ""
                clean_json_str = re.sub(r"^```(?:json)?\s*", "", response_text.strip(), flags=re.MULTILINE)
                clean_json_str = re.sub(r"\s*```$", "", clean_json_str.strip(), flags=re.MULTILINE)
                parsed_data = json.loads(clean_json_str)
                return {
                    "status": "success",
                    "filename": filename,
                    "data": parsed_data,
                    "mode": "text_fallback",
                }
            except Exception as inner_exc:
                return {
                    "status": "error",
                    "message": f"Failed to extract datasheet data: {str(inner_exc)}",
                }

        return {
            "status": "error",
            "message": f"Failed to extract datasheet data: {str(exc)}",
        }
