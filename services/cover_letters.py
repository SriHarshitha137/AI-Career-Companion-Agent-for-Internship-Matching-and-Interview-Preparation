"""Grounded Gemini cover-letter generation."""

from __future__ import annotations

import os
from typing import Any


class CoverLetterError(Exception):
    pass


def generate(candidate: dict[str, Any], internship: dict[str, Any]) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise CoverLetterError("GEMINI_API_KEY is not set in the environment.")
    facts = {key: internship.get(key) for key in ("title", "company", "description", "required_skills", "preferred_skills", "eligibility")}
    prompt = (
        "Write a concise, professional internship cover letter. Use only the candidate and internship facts below. "
        "Never invent skills, experience, education, companies, achievements, dates, or requirements. "
        "If a detail is missing, omit it. Return only the letter.\n\n"
        f"CANDIDATE FACTS: {candidate}\n\nINTERNSHIP FACTS: {facts}"
    )
    try:
        from google import genai
        model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        text = (genai.Client(api_key=api_key).models.generate_content(model=model, contents=prompt).text or "").strip()
        if not text:
            raise CoverLetterError("Gemini returned an empty cover letter.")
        return text
    except CoverLetterError:
        raise
    except Exception as exc:
        raise CoverLetterError("Could not generate the cover letter. Check Gemini configuration.") from exc
