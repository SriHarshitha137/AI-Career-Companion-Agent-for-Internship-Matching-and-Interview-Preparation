"""Gemini-powered extraction of contextual resume information."""

from __future__ import annotations

import json
import os
import re

from google import genai
from pydantic import ValidationError

import config  # noqa: F401  # Load .env before Gemini configuration is read.
from schemas import LLMResumeData

DEFAULT_MODEL = "gemini-3.5-flash-lite"
FALLBACK_MODELS = ["gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-flash-latest"]


class LLMExtractionError(Exception):
    """Raised for a missing API key, API failure, or repeatedly invalid Gemini JSON."""


def _safe_gemini_error(exc: Exception, api_key: str) -> str:
    detail = str(exc).replace(api_key, "[redacted]")
    return re.sub(r"AIza[\w-]+", "[redacted]", detail)[:700] or type(exc).__name__


def _schema_prompt() -> str:
    """Provide an explicit JSON shape, making the model output easy to validate."""
    return """Return exactly one JSON object, with no Markdown fences or other text.
Use this exact schema. Every key is required. Use null for unknown strings and [] for
unknown lists. Do not invent information.
{
  "full_name": null, "professional_summary": null,
  "technical_skills": [], "soft_skills": [],
  "education": [{"institution": null, "degree": null, "field_of_study": null, "start_date": null, "end_date": null, "grade": null}],
  "work_experience": [{"company": null, "title": null, "location": null, "start_date": null, "end_date": null, "responsibilities": []}],
  "projects": [{"name": null, "description": null, "technologies": [], "url": null}],
  "certifications": [{"name": null, "issuer": null, "date": null, "credential_url": null}],
  "internships": [{"company": null, "title": null, "location": null, "start_date": null, "end_date": null, "responsibilities": []}],
  "achievements": [], "languages": [],
  "publications": [{"title": null, "publisher": null, "date": null, "url": null}]
}"""


def _clean_json_text(text: str) -> str:
    """Strip markdown code fences and isolate the JSON object."""
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    match = re.search(r"\{[\s\S]*\}", cleaned)
    return match.group(0) if match else cleaned


def _response_text(response: object) -> str:
    """Read Gemini's generated text, checking that it is not empty."""
    text = (getattr(response, "text", None) or "").strip()
    if not text:
        raise LLMExtractionError("Gemini returned an empty response.")
    return text


def _validate_json(raw_json: str) -> LLMResumeData:
    """Decode JSON first, then validate its types and required keys with Pydantic."""
    cleaned = _clean_json_text(raw_json)
    data = json.loads(cleaned)
    # Ensure nested list items have dictionaries if needed
    for key in ("education", "work_experience", "projects", "certifications", "internships", "publications"):
        if isinstance(data.get(key), list):
            data[key] = [item if isinstance(item, dict) else {"name": str(item)} for item in data[key]]
    for key in ("technical_skills", "soft_skills", "achievements", "languages"):
        if isinstance(data.get(key), list):
            data[key] = [str(item) for item in data[key] if item]
    return LLMResumeData.model_validate(data)


def extract_with_gemini(resume_text: str) -> LLMResumeData:
    """Ask Gemini with automatic model fallback and resilient JSON extraction."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key.startswith("paste_your_"):
        raise LLMExtractionError(
            "GEMINI_API_KEY is not configured. Set it in the project-root .env file and restart the server."
        )

    client = genai.Client(api_key=api_key)
    configured_model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    models = [configured_model] + [m for m in FALLBACK_MODELS if m != configured_model]

    initial_instruction = (
        "You are a precise resume parser. Extract only facts present in the resume.\n\n"
        + _schema_prompt()
        + "\n\nRESUME TEXT:\n"
        + resume_text[:15000]
    )

    last_error: Exception | None = None
    for model in models:
        try:
            response = client.models.generate_content(
                model=model,
                contents=initial_instruction,
            )
            raw_text = _response_text(response)
            try:
                return _validate_json(raw_text)
            except (json.JSONDecodeError, ValidationError) as validation_error:
                retry_instruction = (
                    "Your previous response failed JSON parsing. Return ONLY valid JSON adhering to this schema:\n"
                    f"{_schema_prompt()}\n\nResume text:\n{resume_text[:10000]}"
                )
                retry_resp = client.models.generate_content(model=model, contents=retry_instruction)
                return _validate_json(_response_text(retry_resp))
        except Exception as exc:
            last_error = exc
            continue

    raise LLMExtractionError("Resume parsing failed. Please try again.") from last_error
