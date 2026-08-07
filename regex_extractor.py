"""Readable, deterministic contact-detail extraction using regular expressions."""

from __future__ import annotations

import re

from schemas import ContactData

# Standard email local-part and domain pattern. It intentionally stops at punctuation.
EMAIL_PATTERN = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")

# Indian (+91, 91, or 0 prefixes) and usual 10-digit mobile numbers beginning 6-9.
PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:(?:\+91|91|0)[\s.-]?)?[6-9]\d{4}[\s.-]?\d{5}(?!\d)"
)

# LinkedIn profile URLs, with an optional www. prefix and optional trailing slash.
LINKEDIN_PATTERN = re.compile(r"(?i)\b(?:https?://)?(?:www\.)?linkedin\.com/in/[A-Z0-9_-]+/?")

# GitHub profile URLs. The negative lookahead avoids GitHub asset/path URLs where possible.
GITHUB_PATTERN = re.compile(r"(?i)\b(?:https?://)?(?:www\.)?github\.com/(?!topics|features|settings)[A-Z0-9-]+/?")

SECTION_WORDS = {
    "resume", "curriculum vitae", "professional summary", "summary", "education",
    "experience", "work experience", "skills", "projects", "certifications",
}


def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(0).rstrip(".,;:)\]") if match else None


def _best_effort_name(text: str) -> str | None:
    """Use the first plausible short, alphabetic line as a conservative name heuristic."""
    for raw_line in text.splitlines()[:12]:
        line = re.sub(r"\s+", " ", raw_line).strip(" -|:")
        lower = line.lower()
        words = line.split()
        if (
            2 <= len(words) <= 5
            and 3 <= len(line) <= 60
            and lower not in SECTION_WORDS
            and not EMAIL_PATTERN.search(line)
            and not PHONE_PATTERN.search(line)
            and not re.search(r"\d|https?://|linkedin|github|\|", line, re.I)
            and all(re.fullmatch(r"[A-Za-z.'-]+", word) for word in words)
        ):
            return line.title() if line.isupper() else line
    return None


def extract_contact_data(text: str) -> ContactData:
    """Extract the fields for which regex is more reliable than an LLM."""
    return ContactData(
        name=_best_effort_name(text),
        email=_first_match(EMAIL_PATTERN, text),
        phone=_first_match(PHONE_PATTERN, text),
        linkedin=_first_match(LINKEDIN_PATTERN, text),
        github=_first_match(GITHUB_PATTERN, text),
    )
