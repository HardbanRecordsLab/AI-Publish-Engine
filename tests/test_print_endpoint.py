"""Tests for POST /api/download/{job_id}/print — added 2026-09-22 alongside two
fixes: the endpoint had no test coverage at all, and the frontend called it via
a plain <a href> (GET), which a POST-only route always 404/405s on — independent
of, and pre-dating, the same-day auth-gate change. See jobs.py's downloadPrintPdf
usage / app.js's downloadPrintPdf() for the corresponding frontend fix.
"""
from fastapi.testclient import TestClient

from backend.main import app
from backend.routers.auth import _make_token

client = TestClient(app)
ADMIN_AUTH = {"Authorization": f"Bearer {_make_token('test-admin@example.com')}"}


def _make_done_job_with_html(html="<h1>Test Book</h1><p>Some content.</p>"):
    from backend.core.jobs import create_job, update_job

    job_id = create_job("minimal")
    update_job(job_id, "done", 100, html=html, topic="Test Topic")
    return job_id


class TestPrintEndpoint:
    def test_requires_auth(self):
        job_id = _make_done_job_with_html()
        try:
            resp = client.post(f"/api/download/{job_id}/print")
            assert resp.status_code == 401
        finally:
            from backend.core.jobs import delete_job
            delete_job(job_id)

    def test_job_not_found_returns_404(self):
        resp = client.post("/api/download/does-not-exist/print", headers=ADMIN_AUTH)
        assert resp.status_code == 404

    def test_unfinished_job_returns_400(self):
        from backend.core.jobs import create_job, delete_job

        job_id = create_job("minimal")
        try:
            resp = client.post(f"/api/download/{job_id}/print", headers=ADMIN_AUTH)
            assert resp.status_code == 400
        finally:
            delete_job(job_id)

    def test_invalid_trim_size_returns_400(self):
        job_id = _make_done_job_with_html()
        try:
            resp = client.post(
                f"/api/download/{job_id}/print",
                headers=ADMIN_AUTH,
                params={"trim_size": "nonexistent"},
            )
            assert resp.status_code == 400
        finally:
            from backend.core.jobs import delete_job
            delete_job(job_id)

    def test_no_html_returns_400(self):
        job_id = _make_done_job_with_html(html="")
        try:
            resp = client.post(f"/api/download/{job_id}/print", headers=ADMIN_AUTH)
            assert resp.status_code == 400
        finally:
            from backend.core.jobs import delete_job
            delete_job(job_id)

    def test_returns_a_real_pdf(self):
        """End-to-end: this exact call is what the frontend's downloadPrintPdf()
        makes. Never exercised by a test before this file existed."""
        job_id = _make_done_job_with_html()
        try:
            resp = client.post(f"/api/download/{job_id}/print", headers=ADMIN_AUTH)
            assert resp.status_code == 200, resp.text
            assert resp.headers["content-type"] == "application/pdf"
            assert resp.content[:4] == b"%PDF"
        finally:
            from backend.core.jobs import delete_job
            delete_job(job_id)
