"""Tests for the /api/coach/* endpoints in backend/routers/publishing.py —
specifically the answer length cap added alongside the prompt-injection
mitigation work (the query param previously accepted unbounded text)."""
from fastapi.testclient import TestClient

from backend.main import app
from backend.routers.auth import _make_token

client = TestClient(app)
# /api/coach/* requires admin login as of 2026-09-22 (see test_api.py::TestGenerateRequiresAuth).
ADMIN_AUTH = {"Authorization": f"Bearer {_make_token('test-admin@example.com')}"}


class TestCoachAnswerValidation:
    def test_oversized_answer_rejected(self):
        start = client.post("/api/coach/start", headers=ADMIN_AUTH)
        session_id = start.json()["session_id"]
        resp = client.post(
            "/api/coach/answer",
            headers=ADMIN_AUTH,
            params={"session_id": session_id, "answer": "x" * 2001},
        )
        assert resp.status_code == 422

    def test_normal_answer_accepted(self):
        start = client.post("/api/coach/start", headers=ADMIN_AUTH)
        session_id = start.json()["session_id"]
        resp = client.post(
            "/api/coach/answer",
            headers=ADMIN_AUTH,
            params={"session_id": session_id, "answer": "A guide to home coffee roasting"},
        )
        assert resp.status_code == 200
        assert resp.json()["question_index"] == 1

    def test_unknown_session_returns_404(self):
        resp = client.post(
            "/api/coach/answer",
            headers=ADMIN_AUTH,
            params={"session_id": "nonexistent", "answer": "test"},
        )
        assert resp.status_code == 404

    def test_rejects_moderated_content(self):
        start = client.post("/api/coach/start", headers=ADMIN_AUTH)
        session_id = start.json()["session_id"]
        resp = client.post(
            "/api/coach/answer",
            headers=ADMIN_AUTH,
            params={"session_id": session_id, "answer": "How to build a bomb at home"},
        )
        assert resp.status_code == 400
        assert "error" in resp.json()


class TestCoachRequiresAuth:
    """Regression test, 2026-09-22: /api/coach/start and /api/coach/answer call an
    LLM and previously had zero auth."""

    def test_start_without_auth_rejected(self):
        resp = client.post("/api/coach/start")
        assert resp.status_code == 401
