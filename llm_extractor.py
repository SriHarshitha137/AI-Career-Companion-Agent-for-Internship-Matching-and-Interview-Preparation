"""Gemini-powered extraction of contextual resume information."""

from __future__ import annotations

import json
import os

from google import genai
from pydantic import ValidationError

from schemas import LLMResumeData

DEFAULT_MODEL = "gemini-3.6-flash"


class LLMExtractionError(Exception):
    """Raised for a missing API key, API failure, or repeatedly invalid Gemini JSON."""


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


def _response_text(response: object) -> str:
    """Read Gemini's generated text, checking that it is not empty."""
    text = (getattr(response, "text", None) or "").strip()
    if not text:
        raise LLMExtractionError("Gemini returned an empty response.")
    return text


def _validate_json(raw_json: str) -> LLMResumeData:
    """Decode JSON first, then validate its types and required keys with Pydantic."""
    return LLMResumeData.model_validate(json.loads(raw_json))


def extract_with_gemini(resume_text: str) -> LLMResumeData:
    """Ask Gemini once, then retry exactly once if the returned JSON is invalid."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise LLMExtractionError("GEMINI_API_KEY is not set in the environment.")

    client = genai.Client(api_key=api_key)
    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    initial_instruction = (
        "You are a precise resume parser. Extract only facts present in the resume.\n\n"
        + _schema_prompt()
        + "\n\nRESUME TEXT:\n"
        + resume_text
    )
    try:
        first_response = client.models.generate_content(
            model=model,
            contents=initial_instruction,
        )
        first_text = _response_text(first_response)
        try:
            return _validate_json(first_text)
        except (json.JSONDecodeError, ValidationError) as validation_error:
            # A single, stricter repair request fulfils the controlled retry requirement.
            retry_instruction = (
                "Your previous response failed strict JSON/Pydantic validation. Return a corrected "
                "answer now. Output ONLY one JSON object, no prose or fences. Include every key "
                "from the required schema and no extra keys.\nValidation error: "
                f"{validation_error}\n\nRequired schema:\n{_schema_prompt()}\n\n"
                f"Resume text:\n{resume_text}\n\nPrevious invalid output:\n{first_text}"
            )
            retry_response = client.models.generate_content(
                model=model,
                contents=retry_instruction,
            )
            try:
                return _validate_json(_response_text(retry_response))
            except (json.JSONDecodeError, ValidationError) as retry_error:
                raise LLMExtractionError(
                    "Gemini returned JSON that did not match the required schema after one retry."
                ) from retry_error
    except LLMExtractionError:
        raise
    except Exception as exc:
        raise LLMExtractionError("Gemini API request failed. Check your API key, model, and network.") from exc
