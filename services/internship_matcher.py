"""Build a candidate query and grounded recommendation explanations."""

from __future__ import annotations

import re
from typing import Any


SYNONYMS = {
    "js": "javascript",
    "javascript": "javascript",
    "ts": "typescript",
    "typescript": "typescript",
    "py": "python",
    "python": "python",
    "reactjs": "react",
    "react.js": "react",
    "react": "react",
    "nodejs": "nodejs",
    "node.js": "nodejs",
    "node": "nodejs",
    "express": "expressjs",
    "expressjs": "expressjs",
    "express.js": "expressjs",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "mongo": "mongodb",
    "mongodb": "mongodb",
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",
    "rest": "restapis",
    "restapi": "restapis",
    "restapis": "restapis",
    "ml": "machinelearning",
    "machinelearning": "machinelearning",
    "ai": "artificialintelligence",
    "genai": "generativeai",
    "generativeai": "generativeai",
    "promptengineering": "promptengineering",
    "rag": "rag",
    "scikitlearn": "scikitlearn",
    "sklearn": "scikitlearn",
}


def _canonical(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]", "", value.lower())
    return SYNONYMS.get(cleaned, cleaned)


def _items(value: Any) -> list[str]:
    if isinstance(value, list):
        items = []
        for item in value:
            if isinstance(item, dict):
                items.extend(_items(item.get("technologies") or item.get("name") or item.get("title") or []))
            elif item:
                items.append(str(item))
        return items
    return [str(value)] if value else []


def candidate_data(profile: Any, resume: Any) -> dict[str, Any]:
    parsed = resume.parsed_json if resume else {}
    skills = (
        _items(getattr(profile, "skills", []))
        + _items(getattr(profile, "technical_skills", []))
        + _items(getattr(profile, "soft_skills", []))
        + _items(parsed.get("technical_skills"))
        + _items(parsed.get("soft_skills"))
    )
    # Also add technologies mentioned in projects
    for proj in (getattr(profile, "projects", []) or []) + (parsed.get("projects") or []):
        if isinstance(proj, dict):
            skills.extend(_items(proj.get("technologies")))

    education = _items(getattr(profile, "education", [])) + _items(parsed.get("education"))
    experience = _items(getattr(profile, "experience", [])) + _items(parsed.get("work_experience")) + _items(parsed.get("internships"))
    projects = _items(getattr(profile, "projects", [])) + _items(parsed.get("projects"))
    return {
        "skills": _unique(skills),
        "education": education,
        "experience": experience,
        "projects": projects,
        "summary": parsed.get("professional_summary") or getattr(profile, "bio", None),
    }


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    return [value for value in values if value and not (_canonical(value) in seen or seen.add(_canonical(value)))]


def candidate_query(candidate: dict[str, Any]) -> str:
    sections = []
    for label, values in (("Skills", candidate["skills"]), ("Education", candidate["education"]), ("Experience", candidate["experience"]), ("Projects", candidate["projects"])):
        if values:
            sections.append(f"{label}: " + "; ".join(str(value) for value in values))
    if candidate.get("summary"):
        sections.append("Summary: " + str(candidate["summary"]))
    return "\n".join(sections)


def _normalize(value: str) -> str:
    return _canonical(value)


def match(candidate: dict[str, Any], retrieved: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidate_skills = {_canonical(skill): skill for skill in candidate["skills"] if _canonical(skill)}
    recommendations = []
    for result in retrieved:
        record = result["record"]
        required = _items(record.get("required_skills"))
        preferred = _items(record.get("preferred_skills"))

        matching = [skill for skill in required + preferred if _canonical(skill) in candidate_skills]
        # De-duplicate matching while preserving order
        seen_m: set[str] = set()
        unique_matching = [s for s in matching if not (_canonical(s) in seen_m or seen_m.add(_canonical(s)))]

        missing = [skill for skill in required if _canonical(skill) not in candidate_skills]
        missing_preferred = [skill for skill in preferred if _canonical(skill) not in candidate_skills]

        required_ratio = len([skill for skill in required if _canonical(skill) in candidate_skills]) / max(1, len(required))
        preferred_ratio = len([skill for skill in preferred if _canonical(skill) in candidate_skills]) / max(1, len(preferred)) if preferred else 0.0

        semantic_similarity = round(min(100, max(0, result["semantic_score"] * 100)))
        if preferred:
            skill_match_percentage = round(100 * ((0.80 * required_ratio) + (0.20 * preferred_ratio)))
        else:
            skill_match_percentage = round(100 * required_ratio)

        score = round(min(100, 0.35 * semantic_similarity + 0.65 * skill_match_percentage))
        reason = _reason(record, unique_matching, missing)

        recommendations.append({
            **record,
            "match_score": score,
            "overall_match_percentage": score,
            "semantic_similarity": semantic_similarity,
            "skill_match_percentage": skill_match_percentage,
            "matching_skills": unique_matching,
            "missing_skills": missing,
            "missing_preferred_skills": missing_preferred,
            "reason": reason,
        })
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
