"""Write and AI-cost endpoints must reject anonymous callers.

Before 2026-10-11 these routes had no auth: anyone could call the AI provider
through /api/themes/generate, edit or cancel jobs, manage series, and
/api/templates/upload wrote client-named files outside templates/custom.
"""
import io

import pytest
from fastapi.testclient import TestClient

import backend.routers.templates as templates_module
from backend.main import app
from backend.routers.auth import _make_token

client = TestClient(app)
ADMIN_AUTH = {"Authorization": f"Bearer {_make_token('test-admin@example.com')}"}

TEMPLATE_HTML = b"<html><body>{{title}}{{content}}</body></html>"


@pytest.mark.parametrize(
    "method,path,kwargs",
    [
        ("post", "/api/themes/generate", {"params": {"description": "calm ocean"}}),
        ("post", "/api/cancel/some-job", {}),
        ("put", "/api/editor/some-job/chapters", {"json": {"chapters": []}}),
        ("get", "/api/series", {}),
        ("get", "/api/series/some-series", {}),
        ("post", "/api/series", {"json": {"name": "x"}}),
        ("put", "/api/series/some-series", {"json": {"name": "x"}}),
        ("delete", "/api/series/some-series", {}),
        ("post", "/api/series/some-series/books", {"json": {"job_id": "x"}}),
        ("delete", "/api/series/some-series/books/some-job", {}),
        ("get", "/api/stats/dashboard", {}),
    ],
)
def test_anonymous_request_is_rejected(method, path, kwargs):
    resp = getattr(client, method)(path, **kwargs)
    assert resp.status_code == 401, f"{method.upper()} {path} -> {resp.status_code}"


def test_template_upload_requires_admin():
    files = {"file": ("t.html", io.BytesIO(TEMPLATE_HTML), "text/html")}
    resp = client.post("/api/templates/upload", files=files)
    assert resp.status_code == 401


def test_template_upload_name_cannot_escape_custom_dir(tmp_path, monkeypatch):
    custom = tmp_path / "templates" / "custom"
    custom.mkdir(parents=True)
    monkeypatch.setattr(templates_module, "CUSTOM_TEMPLATES_DIR", custom)

    files = {"file": ("t.html", io.BytesIO(TEMPLATE_HTML), "text/html")}
    resp = client.post(
        "/api/templates/upload",
        files=files,
        data={"name": "../../frontend/index"},
        headers=ADMIN_AUTH,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "frontend-index"
    assert (custom / "frontend-index.html").exists()
    assert not (tmp_path / "frontend").exists()
    assert sorted(p.name for p in tmp_path.rglob("*.html")) == ["frontend-index.html"]


def test_template_upload_rejects_empty_name_after_sanitizing(tmp_path, monkeypatch):
    custom = tmp_path / "custom"
    custom.mkdir()
    monkeypatch.setattr(templates_module, "CUSTOM_TEMPLATES_DIR", custom)

    files = {"file": ("t.html", io.BytesIO(TEMPLATE_HTML), "text/html")}
    resp = client.post("/api/templates/upload", files=files, data={"name": "../.."}, headers=ADMIN_AUTH)

    assert resp.status_code == 400
    assert list(custom.iterdir()) == []
