"""Tests for session isolation, password validation, and AI assistant scope behavior."""

from __future__ import annotations

import unittest
from fastapi.testclient import TestClient

from auth import create_access_token
from database import Base, SessionLocal, engine
from main import app
from models import ChatMessage, ChatSession, InterviewMessage, InterviewSession, User
from services.product_assistant import answer


class TestAgentSessionsAndCorrections(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)
        cls.db = SessionLocal()

        # Create or fetch test user
        cls.user = cls.db.query(User).filter(User.username == "session_test_user").first()
        if not cls.user:
            cls.user = User(
                username="session_test_user",
                email="session_test@example.com",
                hashed_password="hashed_pw_test_123",
            )
            cls.db.add(cls.user)
            cls.db.commit()
            cls.db.refresh(cls.user)

        cls.token = create_access_token(cls.user.id)
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_password_validation_error_message(self):
        # 1. Invalid password (< 8 chars, no digit)
        bad_payload = {
            "username": "valid_user_123",
            "email": "valid_email@example.com",
            "password": "short",
        }
        resp = self.client.post("/register", json=bad_payload)
        self.assertEqual(resp.status_code, 422)
        data = resp.json()
        self.assertEqual(data.get("error", {}).get("message"), "Invalid password")

        # 2. Unrelated validation error (e.g. invalid email, missing fields)
        unrelated_payload = {
            "username": "valid_user_123",
            "email": "not-an-email",
            "password": "ValidPassword123!",
        }
        resp = self.client.post("/register", json=unrelated_payload)
        self.assertEqual(resp.status_code, 422)
        data = resp.json()
        self.assertNotEqual(data.get("error", {}).get("message"), "Invalid password")
        self.assertIn("Invalid request data", data.get("error", {}).get("message"))

    def test_ai_assistant_scope_general_vs_product(self):
        # General question outside InternSphere
        ans, sources = answer("Who is the Prime Minister of India?")
        self.assertIn("Narendra Modi", ans)
        self.assertIn("not directly related to InternSphere", ans)

        # In-scope product question
        prod_ans, prod_sources = answer("How do I apply for an internship?")
        self.assertNotIn("not directly related to InternSphere", prod_ans)
        self.assertNotIn("outside the scope", prod_ans.lower())

    def test_interview_prep_messages_retrieval_and_session_isolation(self):
        # 1. Create an Interview Session
        int_session = InterviewSession(
            user_id=self.user.id,
            title="Software Engineer Interview Session",
            selected_role="Software Engineer Intern",
        )
        self.db.add(int_session)
        self.db.commit()
        self.db.refresh(int_session)

        # Add messages to Interview Session
        msg1 = InterviewMessage(
            session_id=int_session.id,
            role="user",
            content="What are my strongest skills?",
        )
        msg2 = InterviewMessage(
            session_id=int_session.id,
            role="assistant",
            content="Based on your resume, your strongest skills are Python and FastAPI.",
            context_metadata={"sources": ["Resume Analysis"]},
        )
        self.db.add_all([msg1, msg2])
        self.db.commit()

        # 2. Create an AI Assistant Chat Session
        chat_session = ChatSession(
            user_id=self.user.id,
            title="Product Matching Chat",
        )
        self.db.add(chat_session)
        self.db.commit()
        self.db.refresh(chat_session)

        c_msg1 = ChatMessage(
            session_id=chat_session.id,
            role="user",
            content="How does internship matching work?",
        )
        c_msg2 = ChatMessage(
            session_id=chat_session.id,
            role="assistant",
            content="InternSphere uses hybrid RAG vector similarity.",
        )
        self.db.add_all([c_msg1, c_msg2])
        self.db.commit()

        # 3. Fetch Interview Session messages via API
        resp = self.client.get(
            f"/interview-prep/sessions/{int_session.id}",
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        messages = resp.json()
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], "What are my strongest skills?")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertIn("Python and FastAPI", messages[1]["content"])

        # 4. Verify AI Assistant does not see Interview Prep sessions
        asst_sessions = self.client.get("/assistant/sessions", headers=self.headers).json()
        asst_ids = [s["id"] for s in asst_sessions]
        self.assertNotIn(int_session.id, asst_ids)
        self.assertIn(chat_session.id, asst_ids)

        # 5. Verify Interview Prep does not see AI Assistant sessions
        prep_sessions = self.client.get("/interview-prep/sessions", headers=self.headers).json()
        prep_ids = [s["id"] for s in prep_sessions]
        self.assertNotIn(chat_session.id, prep_ids)
        self.assertIn(int_session.id, prep_ids)


if __name__ == "__main__":
    unittest.main()
