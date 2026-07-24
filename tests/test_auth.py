"""Tests for backend/routers/auth.py — previously had zero test coverage
despite being the only gate in front of the admin panel.

Token signing/verification is tested directly (pure functions, no DB).
Login itself needs a real Postgres `admins` table, which isn't available
in this environment — so login tests only assert it fails *safely*
(structured error, not an unhandled exception) and that the rate limit
added in this audit actually engages.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.routers.auth import _make_token, _verify_token


class TestTokenSigning:
    def test_round_trip(self):
        token = _make_token("user@example.com")
        assert _verify_token(token) == "user@example.com"

    def test_tampered_signature_is_rejected(self):
        token = _make_token("user@example.com")
        body, sig = token.rsplit(".", 1)
        tampered = f"{body}.{'0' * len(sig)}"
        assert _verify_token(tampered) is None

    def test_tampered_body_is_rejected(self):
        token = _make_token("user@example.com")
        body, sig = token.rsplit(".", 1)
        forged_body = body.replace("user@example.com", "attacker@evil.com")
        assert _verify_token(f"{forged_body}.{sig}") is None

    def test_expired_token_is_rejected(self):
        import backend.routers.auth as auth_module
        raw = f"attacker@evil.com:deadbeef:{int(time.time()) - 10}"
        import hashlib
        import hmac
        sig = hmac.new(auth_module.SECRET_KEY.encode(), raw.encode(), hashlib.sha256).hexdigest()[:16]
        assert _verify_token(f"{raw}.{sig}") is None

    def test_malformed_token_does_not_raise(self):
        assert _verify_token("not-a-valid-token") is None
        assert _verify_token("") is None
        assert _verify_token("a.b.c.d") is None


class TestAdminCheckEndpoint:
    def test_no_auth_header_returns_401(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        client = TestClient(app)
        resp = client.get("/api/admin/check")
        assert resp.status_code == 401

    def test_invalid_bearer_token_returns_401(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        client = TestClient(app)
        resp = client.get("/api/admin/check", headers={"Authorization": "Bearer garbage"})
        assert resp.status_code == 401

    def test_valid_token_returns_200(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        client = TestClient(app)
        token = _make_token("admin@example.com")
        resp = client.get("/api/admin/check", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


class TestAdminLoginRateLimit:
    def test_login_fails_safely_without_a_database(self):
        """No Postgres in this test environment — must not raise an
        unhandled exception, only a structured 5xx."""
        from fastapi.testclient import TestClient
        from backend.main import app
        client = TestClient(app)
        resp = client.post("/api/admin/login", json={"email": "nobody@example.com", "password": "wrong"})
        assert resp.status_code in (401, 500)

    def test_rate_limit_engages_after_repeated_attempts(self):
        """Regression test: /api/admin/login previously had zero rate
        limiting, so brute-forcing the login form was unthrottled."""
        from fastapi.testclient import TestClient
        from backend.main import app
        client = TestClient(app)
        statuses = []
        for _ in range(8):
            resp = client.post("/api/admin/login", json={"email": "brute@example.com", "password": "x"})
            statuses.append(resp.status_code)
        assert 429 in statuses, f"expected a 429 among {statuses} after 8 rapid login attempts"
