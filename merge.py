"""Merge deterministic contact values with validated contextual LLM data."""

from __future__ import annotations

from regex_extractor import ContactData
from schemas import FinalResumeData, LLMResumeData


def merge_resume_data(contact: ContactData, llm_data: LLMResumeData) -> FinalResumeData:
    """Regex wins for contact fields; Gemini supplies all remaining structured fields."""
    combined = llm_data.model_dump()
    # Name is contextual: use Gemini first, with the regex line heuristic as fallback.
    combined["full_name"] = llm_data.full_name or contact.name
    # These four fields deliberately prefer deterministic regex matches.
    combined["email"] = contact.email
    combined["phone"] = contact.phone
    combined["linkedin"] = contact.linkedin
    combined["github"] = contact.github
    return FinalResumeData.model_validate(combined)
