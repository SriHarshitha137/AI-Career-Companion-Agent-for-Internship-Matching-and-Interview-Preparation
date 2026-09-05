"""Comprehensive test suite for 10 distinct candidate profiles and matching behavior."""

from __future__ import annotations

import unittest
from services.internship_index import search
from services.internship_matcher import candidate_query, match


def recommend(skills: list[str], education: list[str] | None = None, experience: list[str] | None = None, projects: list[dict] | None = None, summary: str = ""):
    candidate = {
        "skills": skills,
        "education": education or [],
        "experience": experience or [],
        "projects": projects or [],
        "summary": summary,
    }
    query = candidate_query(candidate)
    retrieved = search(query, 10)
    return match(candidate, retrieved)


class CandidateMatchingTests(unittest.TestCase):
    # 1. Skill-based matching
    def test_01_skill_based_matching_python_sql_git(self):
        results = recommend(["Python", "SQL", "Git"])
        top = results[0]
        self.assertIn("Python", top["matching_skills"])
        self.assertIn("SQL", top["matching_skills"])
        self.assertGreaterEqual(top["overall_match_percentage"], 65)

    # 2. Education-based matching
    def test_02_education_based_matching_computer_science(self):
        results = recommend(
            skills=["Python", "C++", "DSA"],
            education=["B.Tech in Computer Science and Engineering, 9.2 CGPA"],
            summary="Undergraduate CS student focusing on systems programming.",
        )
        self.assertTrue(len(results) > 0)
        self.assertGreater(results[0]["semantic_similarity"], 0)

    # 3. Experience-based matching
    def test_03_experience_based_matching_backend_intern(self):
        results = recommend(
            skills=["Python", "FastAPI", "PostgreSQL", "Docker", "REST APIs"],
            experience=["Backend Developer Intern building microservice REST APIs and database migrations."],
            summary="Experienced building scalable cloud APIs.",
        )
        titles = [r["title"] for r in results[:3]]
        self.assertTrue(any("Backend" in t or "Software Engineering" in t for t in titles))

    # 4. Project-based matching
    def test_04_project_based_matching_distributed_fintech(self):
        results = recommend(
            skills=["Node.js", "Express.js", "MongoDB", "WebSockets"],
            projects=[{"name": "PayFlow", "technologies": ["Node.js", "Express.js", "MongoDB", "JWT"]}],
            summary="Built real-time collaborative applications and secure payment APIs.",
        )
        top_roles = [r["title"] for r in results[:4]]
        self.assertTrue(any("Full Stack" in t or "Backend" in t or "Software Engineering" in t for t in top_roles))

    # 5. Multiple-skill matching
    def test_05_multiple_skill_matching_fullstack_overlap(self):
        results = recommend(["JavaScript", "React", "Python", "SQL", "HTML", "CSS", "Git"])
        fs = next((r for r in results if r["internship_id"] == "fs-002"), None)
        self.assertIsNotNone(fs)
        self.assertGreaterEqual(fs["skill_match_percentage"], 85)
        self.assertIn("React", fs["matching_skills"])

    # 6. AI/ML internship
    def test_06_aiml_internship_matching(self):
        results = recommend(["Python", "Machine Learning", "Pandas", "NumPy", "scikit-learn"])
        ml = next((r for r in results if r["internship_id"] == "ml-003"), None)
        self.assertIsNotNone(ml)
        self.assertIn("Machine Learning", ml["matching_skills"])
        self.assertGreaterEqual(ml["skill_match_percentage"], 80)

    # 7. Backend internship
    def test_07_backend_internship_matching(self):
        results = recommend(
            skills=["Python", "REST APIs", "SQL", "Git", "Docker", "FastAPI"],
            summary="Passionate backend engineer building scalable cloud REST APIs with FastAPI and Docker.",
            experience=["Backend Engineering Intern at CloudHarbor partner building APIs."],
        )
        be = next((r for r in results if r["internship_id"] == "be-005"), None)
        self.assertIsNotNone(be)
        self.assertIn("REST APIs", be["matching_skills"])
        self.assertGreaterEqual(be["overall_match_percentage"], 70)

    # 8. Data Science internship
    def test_08_data_science_internship_matching(self):
        results = recommend(["Python", "Statistics", "Pandas", "SQL", "Data Visualization"])
        ds = next((r for r in results if r["internship_id"] == "ds-010"), None)
        self.assertIsNotNone(ds)
        self.assertIn("Statistics", ds["matching_skills"])
        self.assertGreaterEqual(ds["skill_match_percentage"], 80)

    # 9. Generative AI internship
    def test_09_generative_ai_internship_matching(self):
        results = recommend(
            skills=["Python", "Generative AI", "Prompt Engineering", "RAG"],
            summary="AI student prototyping retrieval-augmented generation features and prompt engineering workflows.",
            projects=[{"name": "AI Agent", "technologies": ["Python", "Generative AI", "RAG"]}],
        )
        genai = next((r for r in results if r["internship_id"] == "genai-007"), None)
        self.assertIsNotNone(genai)
        self.assertIn("Prompt Engineering", genai["matching_skills"])
        self.assertGreaterEqual(genai["overall_match_percentage"], 75)

    # 10. Full-stack internship
    def test_10_fullstack_developer_internship_matching(self):
        results = recommend(["JavaScript", "HTML", "CSS", "React", "TypeScript", "Figma"])
        frontend = next((r for r in results if r["internship_id"] == "ui-006"), None)
        self.assertIsNotNone(frontend)
        self.assertIn("React", frontend["matching_skills"])
        self.assertIn("JavaScript", frontend["matching_skills"])
        self.assertGreaterEqual(frontend["skill_match_percentage"], 85)


if __name__ == "__main__":
    unittest.main()
