"""Unit and integration tests for AI-Powered Interview Preparation Agent."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models import InterviewDocument, InterviewMessage, InterviewSession, Resume, User
from services.interview_prep_service import (
    InterviewPrepError,
    chat_with_agent,
    check_out_of_scope_intent,
    check_product_intent,
    extract_resume_profile,
    find_previous_user_question,
    generate_interview_questions,
    generate_roadmap,
    generate_skill_gap_and_path,
    get_strongest_skills,
    process_interview_document,
    recommend_roles,
    search_document_chunks,
)


class TestInterviewPrepService(unittest.TestCase):
    def setUp(self):
        self.patcher = patch(
            "services.interview_prep_service.call_gemini",
            side_effect=lambda prompt, fallback_text="": fallback_text,
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

        self.sample_resume_data = {
            "full_name": "Sri Harsha",
            "professional_summary": "Aspiring Backend & AI engineer with strong skills in Python and FastAPI.",
            "technical_skills": ["Python", "FastAPI", "PostgreSQL", "RAG", "SQL", "Git"],
            "soft_skills": ["Problem Solving", "Communication"],
            "education": [
                {
                    "institution": "Tech University",
                    "degree": "B.Tech",
                    "field_of_study": "Computer Science",
                    "grade": "8.8 CGPA",
                }
            ],
            "projects": [
                {
                    "name": "InternSphere",
                    "description": "AI-powered internship matching platform with RAG.",
                    "technologies": ["Python", "FastAPI", "PostgreSQL", "Gemini"],
                },
                {
                    "name": "TaskFlow",
                    "description": "Distributed task queue with real-time tracking.",
                    "technologies": ["Python", "Redis", "Docker"],
                },
            ],
            "work_experience": [],
            "internships": [
                {
                    "company": "NextGen Labs",
                    "title": "Backend Intern",
                    "responsibilities": ["Built REST APIs with FastAPI", "Optimized SQL queries"],
                }
            ],
            "certifications": [{"name": "AWS Certified Cloud Practitioner"}],
            "achievements": ["Finalist in National Hackathon"],
        }
        self.profile = extract_resume_profile(
            Resume(
                user_id=1,
                original_filename="resume.pdf",
                stored_filename="uuid.pdf",
                file_path="/tmp/test.pdf",
                parsed_json=self.sample_resume_data,
            )
        )

    # 1. Missing resume error handling
    def test_01_missing_resume_raises_error(self):
        with self.assertRaises(InterviewPrepError) as ctx:
            recommend_roles({})
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Please upload and parse your resume first", ctx.exception.message)

        with self.assertRaises(InterviewPrepError):
            get_strongest_skills({})

        with self.assertRaises(InterviewPrepError):
            generate_interview_questions({})

        with self.assertRaises(InterviewPrepError):
            generate_skill_gap_and_path({}, "Backend Developer Intern")

    # 2. Role recommendation based on resume skills
    def test_02_role_recommendation(self):
        result = recommend_roles(self.profile)
        roles = result["roles"]
        self.assertTrue(len(roles) >= 2)
        self.assertTrue(
            any("Backend" in r or "Software Engineer" in r or "AI" in r for r in roles)
        )
        self.assertTrue(len(result["candidate_skills"]) > 0)

    # 3. Strongest skills extraction with evidence
    def test_03_strongest_skills(self):
        result = get_strongest_skills(self.profile)
        skills = result["skills"]
        self.assertTrue(len(skills) >= 3)
        self.assertIn("Python", skills)
        evidence = result["evidence"]
        self.assertTrue(len(evidence) > 0)
        # Check evidence references projects
        self.assertTrue(any("InternSphere" in str(e) or "resume" in str(e).lower() for e in evidence))

    # 4. Technical questions generation
    def test_04_technical_questions(self):
        result = generate_interview_questions(
            self.profile, category="technical", role="Backend Developer Intern"
        )
        self.assertEqual(result["category"], "technical")
        self.assertEqual(result["role"], "Backend Developer Intern")
        self.assertTrue(len(result["questions"]) >= 4)
        # Verify questions consider skills or architecture
        questions_text = " ".join(result["questions"]).lower()
        self.assertTrue(
            any(kw in questions_text for kw in ["python", "api", "database", "sql", "fastapi", "rag"])
        )

    # 5. HR and Behavioral questions generation
    def test_05_hr_questions(self):
        result = generate_interview_questions(
            self.profile, category="hr", role="Software Engineer Intern"
        )
        self.assertEqual(result["category"], "hr")
        self.assertTrue(len(result["questions"]) >= 4)
        q_text = " ".join(result["questions"]).lower()
        self.assertTrue(
            any(kw in q_text for kw in ["yourself", "project", "problem", "challenge", "interest"])
        )

    # 6. Project-based questions generation
    def test_06_project_questions(self):
        result = generate_interview_questions(
            self.profile, category="project", role="Backend Developer Intern", project_name="InternSphere"
        )
        self.assertEqual(result["category"], "project")
        self.assertTrue(len(result["questions"]) >= 4)
        q_text = " ".join(result["questions"])
        self.assertIn("InternSphere", q_text)

    # 7. Preparation roadmap generation
    def test_07_roadmap_generation(self):
        result = generate_roadmap(self.profile, "Backend Developer Intern")
        self.assertEqual(result["role"], "Backend Developer Intern")
        roadmap = result["roadmap"]
        self.assertTrue(len(roadmap) >= 5)
        step_titles = [s["title"] for s in roadmap]
        self.assertTrue(any("Resume" in t or "Fundamentals" in t for t in step_titles))

    # 8. Skill gap and learning path
    def test_08_skill_gap_analysis(self):
        result = generate_skill_gap_and_path(self.profile, "Backend Developer Intern")
        self.assertEqual(result["role"], "Backend Developer Intern")
        # Python and SQL exist in profile, so they should be in current_skills
        self.assertTrue(any("Python" in s for s in result["current_skills"]))
        self.assertTrue(isinstance(result["missing_skills"], list))
        self.assertTrue(len(result["learning_path"]) >= 3)

    # 9. Product intent detection
    def test_09_product_intent_detection(self):
        self.assertTrue(check_product_intent("How do I apply for an internship?"))
        self.assertTrue(check_product_intent("How to withdraw an application?"))
        self.assertTrue(check_product_intent("How do I generate a cover letter?"))
        self.assertTrue(check_product_intent("Where can I see my applications?"))
        self.assertTrue(check_product_intent("How does the matching page work?"))
        self.assertFalse(check_product_intent("What are my strongest skills?"))
        self.assertFalse(check_product_intent("What technical questions can they ask?"))

    # 10. Out-of-scope intent detection
    def test_10_out_of_scope_intent(self):
        self.assertTrue(check_out_of_scope_intent("What is the capital of France?"))
        self.assertTrue(check_out_of_scope_intent("Give me a recipe for chocolate cake"))
        self.assertTrue(check_out_of_scope_intent("What is the weather today in Paris?"))
        self.assertFalse(check_out_of_scope_intent("What roles suit me?"))
        self.assertFalse(check_out_of_scope_intent("Explain REST APIs."))

    # 11. Conversational session memory
    def test_11_conversational_memory(self):
        history = [
            {"role": "user", "content": "What is my strongest skill?"},
            {"role": "assistant", "content": "Your strongest skill is Python."},
            {"role": "user", "content": "Why is that?"},
            {"role": "assistant", "content": "Because you have demonstrated it in your projects."},
        ]
        prev = find_previous_user_question(history)
        self.assertEqual(prev, "What is my strongest skill?")

        ans, sources, is_prod, is_out = chat_with_agent(
            "What was my previous question?",
            profile=self.profile,
            history=history + [{"role": "user", "content": "What was my previous question?"}],
        )
        self.assertIn("What is my strongest skill?", ans)
        self.assertIn("Session History", sources)

    # 12. Chat routing for product questions
    def test_12_chat_product_redirect(self):
        ans, sources, is_prod, is_out = chat_with_agent(
            "How do I apply for an internship on InternSphere?",
            profile=self.profile,
        )
        self.assertTrue(is_prod)
        self.assertIn("AI Assistant section", ans)

    # 13. Chat routing for irrelevant questions
    def test_13_chat_out_of_scope(self):
        ans, sources, is_prod, is_out = chat_with_agent(
            "What is the capital of France?",
            profile=self.profile,
        )
        self.assertTrue(is_out)
        self.assertIn("outside the scope of the Interview Preparation Agent", ans)

    # 14. Document processing and RAG search
    def test_14_document_processing_and_search(self):
        # Test text extraction with docx/pdf mock or direct text
        sample_doc_content = (
            "System Architecture Guide: In microservice systems, idempotency in REST APIs is critical. "
            "Clients can retry failed POST or PUT operations using unique idempotency keys stored in Redis. "
            "Database connections must use connection pooling to avoid resource starvation under high concurrency."
        )
        # Test search with simulated InterviewDocument
        doc = InterviewDocument(
            user_id=1,
            filename="architecture_guide.pdf",
            stored_filename="fake.pdf",
            file_path="/tmp/fake.pdf",
            file_type=".pdf",
            extracted_text=sample_doc_content,
            chunks=[
                {
                    "chunk_index": 0,
                    "content": sample_doc_content,
                    "embedding": [0.1] * 384,
                }
            ],
        )
        # Search query matching document
        chunks = search_document_chunks(doc, "idempotency keys in Redis", top_k=2)
        self.assertTrue(len(chunks) > 0)
        self.assertIn("idempotency", chunks[0]["content"])

    # 15. Database persistence and session isolation
    def test_15_database_session_isolation(self):
        test_engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(test_engine)
        TestingSession = sessionmaker(bind=test_engine)
        db = TestingSession()

        # Create two distinct users
        user1 = User(username="user1", email="user1@test.com", hashed_password="pw1")
        user2 = User(username="user2", email="user2@test.com", hashed_password="pw2")
        db.add_all([user1, user2])
        db.commit()

        # User 1 creates session A and messages
        session_a = InterviewSession(user_id=user1.id, title="User1 Prep", selected_role="Backend Developer Intern")
        db.add(session_a)
        db.commit()

        msg1 = InterviewMessage(session_id=session_a.id, role="user", content="User 1 question")
        msg2 = InterviewMessage(session_id=session_a.id, role="assistant", content="User 1 answer")
        db.add_all([msg1, msg2])
        db.commit()

        # User 2 creates session B and messages
        session_b = InterviewSession(user_id=user2.id, title="User2 Prep", selected_role="Frontend Developer Intern")
        db.add(session_b)
        db.commit()

        msg3 = InterviewMessage(session_id=session_b.id, role="user", content="User 2 question")
        db.add(msg3)
        db.commit()

        # Verify User 1 cannot see User 2's session
        u1_sessions = db.query(InterviewSession).where(InterviewSession.user_id == user1.id).all()
        self.assertEqual(len(u1_sessions), 1)
        self.assertEqual(u1_sessions[0].title, "User1 Prep")

        # Verify Session A messages do not bleed into Session B
        sa_msgs = db.query(InterviewMessage).where(InterviewMessage.session_id == session_a.id).all()
        sb_msgs = db.query(InterviewMessage).where(InterviewMessage.session_id == session_b.id).all()
        self.assertEqual(len(sa_msgs), 2)
        self.assertEqual(len(sb_msgs), 1)
        self.assertEqual(sb_msgs[0].content, "User 2 question")

        db.close()


if __name__ == "__main__":
    unittest.main()
