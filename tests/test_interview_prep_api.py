"""API endpoint tests for AI-Powered Interview Preparation Agent."""

from __future__ import annotations

import unittest
from unittest.mock import patch
from io import BytesIO

from fastapi.testclient import TestClient

from auth import create_access_token
from database import Base, SessionLocal, engine
from main import app
from models import Resume, User


class TestInterviewPrepAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)
        cls.db = SessionLocal()

        # Create or fetch test user
        cls.user = cls.db.query(User).filter(User.username == "prep_test_user").first()
        if not cls.user:
            cls.user = User(
                username="prep_test_user",
                email="prep_test@example.com",
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

    def setUp(self):
        self.patcher = patch(
            "services.interview_prep_service.call_gemini",
            side_effect=lambda prompt, fallback_text="": fallback_text,
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_01_unauthenticated_request_rejected(self):
        resp = self.client.get("/interview-prep/status")
        self.assertEqual(resp.status_code, 401)

    def test_02_status_endpoint_authenticated(self):
        resp = self.client.get("/interview-prep/status", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("has_resume", data)

    def test_03_create_and_list_sessions(self):
        # Create new session
        create_resp = self.client.post(
            "/interview-prep/sessions",
            headers=self.headers,
            json={"title": "Test Prep Session", "selected_role": "Backend Developer Intern"},
        )
        self.assertEqual(create_resp.status_code, 201)
        session_data = create_resp.json()
        session_id = session_data["id"]
        self.assertEqual(session_data["title"], "Test Prep Session")
        self.assertEqual(session_data["selected_role"], "Backend Developer Intern")

        # List sessions
        list_resp = self.client.get("/interview-prep/sessions", headers=self.headers)
        self.assertEqual(list_resp.status_code, 200)
        sessions = list_resp.json()
        self.assertTrue(any(s["id"] == session_id for s in sessions))

        # Update session role
        up_resp = self.client.put(
            f"/interview-prep/sessions/{session_id}/role",
            headers=self.headers,
            json={"selected_role": "Full Stack Developer Intern"},
        )
        self.assertEqual(up_resp.status_code, 200)
        self.assertEqual(up_resp.json()["selected_role"], "Full Stack Developer Intern")

        # Delete session
        del_resp = self.client.delete(f"/interview-prep/sessions/{session_id}", headers=self.headers)
        self.assertEqual(del_resp.status_code, 200)

    def test_04_chat_product_redirection(self):
        resp = self.client.post(
            "/interview-prep/chat",
            headers=self.headers,
            json={"question": "How do I apply for an internship?"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["is_product_redirect"])
        self.assertIn("AI Assistant", data["answer"])

    def test_05_chat_out_of_scope(self):
        resp = self.client.post(
            "/interview-prep/chat",
            headers=self.headers,
            json={"question": "What is the capital of France?"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["is_out_of_scope"])
        self.assertIn("outside the scope", data["answer"])

    def test_06_document_upload_and_validation(self):
        # Unsupported file extension
        bad_file = BytesIO(b"Hello world")
        bad_resp = self.client.post(
            "/interview-prep/documents/upload",
            headers=self.headers,
            files={"file": ("notes.txt", bad_file, "text/plain")},
        )
        self.assertEqual(bad_resp.status_code, 415)

        # Empty file
        empty_pdf = BytesIO(b"")
        empty_resp = self.client.post(
            "/interview-prep/documents/upload",
            headers=self.headers,
            files={"file": ("empty.pdf", empty_pdf, "application/pdf")},
        )
        self.assertEqual(empty_resp.status_code, 422)

    def test_07_roadmap_endpoint(self):
        resp = self.client.post(
            "/interview-prep/roadmap",
            headers=self.headers,
            json={"role": "Backend Developer Intern"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["role"], "Backend Developer Intern")
        self.assertTrue(len(data["roadmap"]) >= 5)


if __name__ == "__main__":
    unittest.main()
