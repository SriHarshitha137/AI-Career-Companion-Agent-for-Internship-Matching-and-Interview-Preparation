"""Behavior-focused synthetic candidate checks for the internship matching pipeline."""

from __future__ import annotations

import unittest

from services.internship_index import search
from services.internship_matcher import candidate_query, match


def recommend(skills: list[str]):
    candidate = {"skills": skills, "education": [], "experience": [], "projects": [], "summary": ""}
    return match(candidate, search(candidate_query(candidate), 10))


class MatchingBehaviorTests(unittest.TestCase):
    def test_backend_candidate_matches_python_roles(self):
        results = recommend(["Python", "FastAPI", "SQL", "Git"])
        titles = {item["title"] for item in results[:3]}
        self.assertTrue({"Software Engineering Intern", "Backend Engineering Intern"} & titles)

    def test_machine_learning_candidate_has_ml_skill_overlap(self):
        results = recommend(["Python", "Machine Learning", "Pandas", "NumPy"])
        ml = next(item for item in results if item["internship_id"] == "ml-003")
        self.assertIn("Machine Learning", ml["matching_skills"])

    def test_generative_ai_candidate_has_rag_skill_gap_visibility(self):
        results = recommend(["Python", "Generative AI", "Prompt Engineering"])
        role = next(item for item in results if item["internship_id"] == "genai-007")
        self.assertGreater(role["skill_match_percentage"], 50)
        self.assertIn("RAG", role["missing_preferred_skills"])

    def test_cloud_candidate_surfaces_required_skills(self):
        results = recommend(["Linux", "Git", "Docker"])
        role = next(item for item in results if item["internship_id"] == "cloud-008")
        self.assertEqual(role["missing_skills"], [])

    def test_java_candidate_matches_java_listing(self):
        results = recommend(["Java", "SQL", "Git"])
        role = next(item for item in results if item["internship_id"] == "java-009")
        self.assertIn("Java", role["matching_skills"])

    def test_data_candidate_has_data_science_overlap(self):
        results = recommend(["Python", "Statistics", "Pandas", "SQL"])
        role = next(item for item in results if item["internship_id"] == "ds-010")
        self.assertGreaterEqual(role["skill_match_percentage"], 80)


if __name__ == "__main__":
    unittest.main()
