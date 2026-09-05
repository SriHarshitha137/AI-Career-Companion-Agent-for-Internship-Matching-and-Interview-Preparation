"""Grounded Gemini cover-letter generation."""

from __future__ import annotations

import os
import re
from typing import Any

import config  # noqa: F401  # Load .env before Gemini configuration is read.

class CoverLetterError(Exception):
    pass


def _safe_gemini_error(exc: Exception, api_key: str) -> str:
    """Expose Gemini's useful diagnostic without ever returning a credential."""
    detail = str(exc).replace(api_key, "[redacted]")
    detail = re.sub(r"AIza[\w-]+", "[redacted]", detail)
    return detail[:700] or type(exc).__name__


def generate(candidate: dict[str, Any], internship: dict[str, Any]) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key.startswith("paste_your_"):
        raise CoverLetterError(
            "GEMINI_API_KEY is not configured. Open the .env file in the project root, "
            "replace the placeholder with your real Google AI Studio key, then restart the server."
        )
    facts = {key: internship.get(key) for key in ("title", "company", "description", "required_skills", "preferred_skills", "eligibility")}
    prompt = (
        "Write a concise, professional internship cover letter. Use only the candidate and internship facts below. "
        "Never invent skills, experience, education, companies, achievements, dates, or requirements. "
        "If a detail is missing, omit it. Return only the letter.\n\n"
        f"CANDIDATE FACTS: {candidate}\n\nINTERNSHIP FACTS: {facts}"
    )
    from google import genai
    configured_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    models = [configured_model] + [m for m in ["gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-flash-latest"] if m != configured_model]
    client = genai.Client(api_key=api_key)

    last_error: Exception | None = None
    for model in models:
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            text = (response.text or "").strip()
            if text:
                return text
        except Exception as exc:
            last_error = exc
            continue

    raise CoverLetterError(
        f"Gemini request failed: {_safe_gemini_error(last_error, api_key) if last_error else 'Generation returned empty'}"
    )
