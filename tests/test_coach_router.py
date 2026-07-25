"""Tests for the /api/coach/* endpoints in backend/routers/publishing.py —
specifically the answer length cap added alongside the prompt-injection
mitigation work (the query param previously accepted unbounded text)."""
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


class TestCoachAnswerValidation:
    def test_oversized_answer_rejected(self):
        start = client.post("/api/coach/start")
        session_id = start.json()["session_id"]
        resp = client.post(
            "/api/coach/answer",
            params={"session_id": session_id, "answer": "x" * 2001},
        )
        assert resp.status_code == 422

    def test_normal_answer_accepted(self):
        start = client.post("/api/coach/start")
        session_id = start.json()["session_id"]
        resp = client.post(
            "/api/coach/answer",
            params={"session_id": session_id, "answer": "A guide to home coffee roasting"},
        )
        assert resp.status_code == 200
        assert resp.json()["question_index"] == 1

    def test_unknown_session_returns_404(self):
        resp = client.post(
            "/api/coach/answer",
            params={"session_id": "nonexistent", "answer": "test"},
        )
        assert resp.status_code == 404

    def test_rejects_moderated_content(self):
        start = client.post("/api/coach/start")
        session_id = start.json()["session_id"]
        resp = client.post(
            "/api/coach/answer",
            params={"session_id": session_id, "answer": "How to build a bomb at home"},
        )
        assert resp.status_code == 400
        assert "error" in resp.json()
