"""Build a candidate query and grounded recommendation explanations."""

from __future__ import annotations

import re
from typing import Any


def _items(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return [str(value)] if value else []


def candidate_data(profile: Any, resume: Any) -> dict[str, Any]:
    parsed = resume.parsed_json if resume else {}
    skills = (_items(getattr(profile, "skills", [])) + _items(getattr(profile, "technical_skills", []))
              + _items(parsed.get("technical_skills")) + _items(parsed.get("soft_skills")))
    education = _items(getattr(profile, "education", [])) + _items(parsed.get("education"))
    experience = _items(getattr(profile, "experience", [])) + _items(parsed.get("work_experience")) + _items(parsed.get("internships"))
    projects = _items(parsed.get("projects"))
    return {"skills": _unique(skills), "education": education, "experience": experience, "projects": projects, "summary": parsed.get("professional_summary") or getattr(profile, "bio", None)}


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    return [value for value in values if value and not (value.lower() in seen or seen.add(value.lower()))]


def candidate_query(candidate: dict[str, Any]) -> str:
    sections = []
    for label, values in (("Skills", candidate["skills"]), ("Education", candidate["education"]), ("Experience", candidate["experience"]), ("Projects", candidate["projects"])):
        if values:
            sections.append(f"{label}: " + "; ".join(str(value) for value in values))
    if candidate.get("summary"):
        sections.append("Summary: " + str(candidate["summary"]))
    return "\n".join(sections)


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9+#.]", "", value.lower())


def match(candidate: dict[str, Any], retrieved: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidate_skills = {_normalize(skill): skill for skill in candidate["skills"] if _normalize(skill)}
    recommendations = []
    for result in retrieved:
        record = result["record"]
        required = _items(record.get("required_skills"))
        preferred = _items(record.get("preferred_skills"))
        matching = [skill for skill in required + preferred if _normalize(skill) in candidate_skills]
        missing = [skill for skill in required if _normalize(skill) not in candidate_skills]
        required_ratio = len([skill for skill in required if _normalize(skill) in candidate_skills]) / max(1, len(required))
        preferred_ratio = len([skill for skill in preferred if _normalize(skill) in candidate_skills]) / max(1, len(preferred))
        semantic_similarity = round(min(100, max(0, result["semantic_score"] * 100)))
        skill_match_percentage = round(100 * ((0.8 * required_ratio) + (0.2 * preferred_ratio)))
        score = round(min(100, 0.45 * semantic_similarity + 0.45 * skill_match_percentage + 10 * preferred_ratio))
        reason = _reason(record, matching, missing)
        recommendations.append({**record, "match_score": score, "overall_match_percentage": score,
                                "semantic_similarity": semantic_similarity, "skill_match_percentage": skill_match_percentage,
                                "matching_skills": matching, "missing_skills": missing,
                                "missing_preferred_skills": [skill for skill in preferred if _normalize(skill) not in candidate_skills],
                                "reason": reason})
    return sorted(recommendations, key=lambda item: item["match_score"], reverse=True)


def _reason(record: dict[str, Any], matching: list[str], missing: list[str]) -> str:
    pieces = []
    if matching:
        pieces.append("Your matching skills are " + ", ".join(matching) + ".")
    else:
        pieces.append("The result was retrieved from your overall resume/profile context, but no listed skill matched exactly.")
    if missing:
        pieces.append("Listed required skills still to develop: " + ", ".join(missing) + ".")
    eligibility = record.get("eligibility")
    if eligibility:
        pieces.append("Eligibility: " + str(eligibility))
    return " ".join(pieces)
