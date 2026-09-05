"""Unified resume processing pipeline — avoids circular imports with main.py."""

from __future__ import annotations

from pathlib import Path

from extract_text import TextExtractionError, extract_text
from llm_extractor import LLMExtractionError, extract_with_gemini
from merge import merge_resume_data
from regex_extractor import extract_contact_data


class ResumeProcessingError(Exception):
    """Application-level error returned in a stable, readable JSON format."""

    def __init__(self, message: str, status_code: int = 422) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def parse_resume(file_bytes: bytes, filename: str) -> dict:
    """Run extraction, regex parsing, Gemini parsing, and merge in one reusable pipeline."""
    extension = Path(filename).suffix.lower()
    if extension not in {".pdf", ".docx"}:
        raise ResumeProcessingError("Unsupported file type. Upload a .pdf or .docx file.", 415)
    try:
        text = extract_text(file_bytes, extension)
        contact = extract_contact_data(text)
        llm_data = extract_with_gemini(text)
        return merge_resume_data(contact, llm_data).model_dump(mode="json")
    except TextExtractionError as exc:
        raise ResumeProcessingError(str(exc), 422) from exc
    except LLMExtractionError as exc:
        raise ResumeProcessingError(str(exc), 502) from exc
