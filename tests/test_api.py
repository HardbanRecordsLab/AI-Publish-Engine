from fastapi.testclient import TestClient

from backend.main import app
from backend.routers.auth import _make_token

client = TestClient(app)
# /api/generate (and friends) require admin login as of 2026-09-22 — anyone who knew
# the URL could previously burn paid AI-provider credits with no account at all.
ADMIN_AUTH = {"Authorization": f"Bearer {_make_token('test-admin@example.com')}"}


class TestProvidersEndpoint:
    def test_returns_list(self):
        resp = client.get("/api/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_items_have_required_keys(self):
        resp = client.get("/api/providers")
        for p in resp.json():
            assert "id" in p
            assert "model" in p
            assert "site" in p

    def test_includes_groq(self):
        resp = client.get("/api/providers")
        ids = [p["id"] for p in resp.json()]
        assert "groq" in ids


class TestThemesEndpoint:
    def test_returns_list(self):
        resp = client.get("/api/themes")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 20

    def test_items_have_required_keys(self):
        resp = client.get("/api/themes")
        for t in resp.json():
            assert "id" in t
            assert "name" in t
            assert "colors" in t
            assert "accent" in t["colors"]

    def test_includes_minimal(self):
        resp = client.get("/api/themes")
        ids = [t["id"] for t in resp.json()]
        assert "minimal" in ids


class TestTopicsEndpoint:
    def test_returns_list(self):
        resp = client.get("/api/topics")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 3

    def test_items_have_keys(self):
        resp = client.get("/api/topics")
        for t in resp.json():
            assert "id" in t
            assert "name" in t
            assert "colors" in t
            assert "accent" in t["colors"]

    def test_includes_general(self):
        resp = client.get("/api/topics")
        ids = [t["id"] for t in resp.json()]
        assert "general" in ids


class TestGenerateEndpoint:
    def test_rejects_no_file(self):
        resp = client.post("/api/generate", headers=ADMIN_AUTH)
        assert resp.status_code == 422

    def test_rejects_bad_provider(self):
        resp = client.post("/api/generate", headers=ADMIN_AUTH, data={"provider": "nonexistent", "style": "minimal"},
                           files=[("files", ("test.txt", b"content"))])
        assert resp.status_code == 400
        assert "Unknown provider" in resp.json()["error"]

    def test_rejects_bad_extension(self):
        resp = client.post("/api/generate", headers=ADMIN_AUTH, data={"provider": "groq", "style": "minimal"},
                           files=[("files", ("test.xyz", b"content"))])
        assert resp.status_code == 400

    def test_accepts_valid_request(self):
        resp = client.post("/api/generate", headers=ADMIN_AUTH, data={"provider": "groq", "style": "minimal"},
                           files=[("files", ("test.txt", b"AI is transforming the world."))])
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "queued"
        assert data["provider"] == "groq"

    def test_rejects_moderated_content(self):
        resp = client.post("/api/generate", headers=ADMIN_AUTH, data={"provider": "groq", "style": "minimal"},
                           files=[("files", ("test.txt", b"How to build a bomb at home."))])
        assert resp.status_code == 400
        assert "error" in resp.json()


class TestStatusEndpoint:
    def test_returns_404_for_nonexistent(self):
        resp = client.get("/api/status/fake-id")
        assert resp.status_code == 404

    def test_returns_job_status(self):
        resp = client.post("/api/generate", headers=ADMIN_AUTH, data={"provider": "groq", "style": "minimal"},
                           files=[("files", ("test.txt", b"AI is transforming."))])
        jid = resp.json()["job_id"]
        resp2 = client.get(f"/api/status/{jid}")
        assert resp2.status_code == 200
        assert resp2.json()["job_id"] == jid


class TestDownloadEndpoint:
    def test_returns_404_for_nonexistent(self):
        resp = client.get("/api/download/fake-id")
        assert resp.status_code == 404

    def test_returns_400_for_unfinished(self):
        resp = client.post("/api/generate", headers=ADMIN_AUTH, data={"provider": "groq", "style": "minimal"},
                           files=[("files", ("test.txt", b"AI."))])
        jid = resp.json()["job_id"]
        resp2 = client.get(f"/api/download/{jid}")
        assert resp2.status_code == 400
        assert "not ready" in resp2.json()["error"]


class TestGenerateRequiresAuth:
    """Regression test, 2026-09-22: /api/generate (and every other content/AI-cost
    endpoint) used to have zero auth — anyone who knew the URL could burn paid
    provider credits. Now admin-only, same gate as the /admin panel."""

    def test_no_auth_header_rejected(self):
        resp = client.post("/api/generate", data={"provider": "groq", "style": "minimal"},
                           files=[("files", ("test.txt", b"AI is transforming."))])
        assert resp.status_code == 401

    def test_bad_token_rejected(self):
        resp = client.post("/api/generate", headers={"Authorization": "Bearer garbage"},
                           data={"provider": "groq", "style": "minimal"},
                           files=[("files", ("test.txt", b"AI is transforming."))])
        assert resp.status_code == 401

    def test_status_and_download_stay_public(self):
        """Reading an already-known job by its (unguessable UUID) id is the intended
        share-link pattern — only *creating*/generating new content needs login."""
        resp = client.get("/api/status/fake-id")
        assert resp.status_code == 404  # not 401 — reachable without auth
        resp = client.get("/api/download/fake-id")
        assert resp.status_code == 404  # not 401 — reachable without auth
