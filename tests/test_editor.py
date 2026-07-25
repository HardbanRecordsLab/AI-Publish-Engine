import json

from fastapi.testclient import TestClient

from backend.core.jobs import create_job, update_job
from backend.main import app

client = TestClient(app)

BOOK_DATA = {
    "title": "Original Title",
    "author": "Test Author",
    "chapters": [
        {
            "title": "Chapter One",
            "introduction": "Original intro.",
            "sections": [{"heading": "Original Heading", "content": "Original content."}],
        }
    ],
}
BUILD_PARAMS = {"style": "minimal"}


def _make_done_job():
    jid = create_job("minimal")
    update_job(jid, "done", 100, book_data=json.dumps(BOOK_DATA), build_params=json.dumps(BUILD_PARAMS))
    return jid


class TestSaveChaptersValidation:
    def test_oversized_title_rejected(self):
        jid = _make_done_job()
        payload = {"chapters": [{"index": 0, "title": "x" * 501}]}
        resp = client.put(f"/api/editor/{jid}/chapters", json=payload)
        assert resp.status_code == 422

    def test_oversized_content_rejected(self):
        jid = _make_done_job()
        payload = {"chapters": [{
            "index": 0, "title": "ok",
            "sections": [{"index": 0, "heading": "h", "content": "x" * 20001}],
        }]}
        resp = client.put(f"/api/editor/{jid}/chapters", json=payload)
        assert resp.status_code == 422

    def test_valid_payload_saves_and_merges(self):
        jid = _make_done_job()
        payload = {"chapters": [{
            "index": 0, "title": "New Title", "introduction": "New intro.",
            "sections": [{"index": 0, "heading": "New Heading", "content": "New content."}],
        }]}
        resp = client.put(f"/api/editor/{jid}/chapters", json=payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "saved"

        get_resp = client.get(f"/api/editor/{jid}/chapters")
        data = get_resp.json()
        assert data["chapters"][0]["title"] == "New Title"
        assert data["chapters"][0]["sections"][0]["content"] == "New content."

    def test_control_characters_stripped_on_save(self):
        jid = _make_done_job()
        payload = {"chapters": [{"index": 0, "title": "Clean\x07Title"}]}
        resp = client.put(f"/api/editor/{jid}/chapters", json=payload)
        assert resp.status_code == 200
        data = client.get(f"/api/editor/{jid}/chapters").json()
        assert "\x07" not in data["chapters"][0]["title"]

    def test_missing_job_returns_404(self):
        payload = {"chapters": [{"index": 0, "title": "x"}]}
        resp = client.put("/api/editor/nonexistent-id/chapters", json=payload)
        assert resp.status_code == 404

    def test_no_chapters_returns_400(self):
        jid = _make_done_job()
        resp = client.put(f"/api/editor/{jid}/chapters", json={"chapters": []})
        assert resp.status_code == 400
