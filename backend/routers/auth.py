import hashlib
import hmac
import secrets
import time
from pathlib import Path

import bcrypt
from fastapi import APIRouter, HTTPException, Request
from loguru import logger
from pydantic import BaseModel

from backend.config import settings
from backend.core.database import get_conn
from backend.limiter import limiter

router = APIRouter()


def _load_or_create_secret_key() -> str:
    """Resolve a stable admin-auth secret.

    Priority:
    1. SECRET_KEY from .env / environment (settings.secret_key)
    2. A previously generated key persisted in backend/.secret_key
    3. Freshly generated key, written to backend/.secret_key so it survives restarts

    This fixes a bug where a brand-new random key was generated on every
    process start (and would differ across multiple worker processes),
    silently invalidating every admin session on restart/redeploy.
    """
    if settings.secret_key:
        return settings.secret_key

    key_file = Path(__file__).resolve().parent.parent / ".secret_key"
    try:
        if key_file.exists():
            existing = key_file.read_text().strip()
            if existing:
                return existing
    except Exception as e:
        logger.warning(f"Could not read {key_file}: {e}")

    new_key = secrets.token_hex(32)
    try:
        key_file.write_text(new_key)
        key_file.chmod(0o600)
        logger.info(f"Generated new persistent admin secret key at {key_file}")
    except Exception as e:
        logger.warning(f"Could not persist secret key to {key_file} ({e}). "
                        f"Admin sessions will not survive a restart — set SECRET_KEY in .env instead.")
    return new_key


SECRET_KEY = _load_or_create_secret_key()


def _make_token(email: str) -> str:
    raw = f"{email}:{secrets.token_hex(32)}:{int(time.time()) + 86400}"
    sig = hmac.new(SECRET_KEY.encode(), raw.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{raw}.{sig}"


def _verify_token(token: str) -> str | None:
    try:
        body, sig = token.rsplit(".", 1)
        expected = hmac.new(SECRET_KEY.encode(), body.encode(), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected):
            return None
        email, _, expiry = body.rsplit(":", 2)
        if int(time.time()) > int(expiry):
            return None
        return email
    except (ValueError, IndexError):
        return None


def create_admin(email: str, password: str) -> bool:
    """Create or update an admin account. Use this via shell, not HTTP."""
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO admins (email, password_hash) VALUES (%s, %s) "
                "ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash",
                (email, password_hash),
            )
        logger.info(f"Admin account created/updated: {email}")
        return True
    except Exception as e:
        logger.warning(f"Failed to create admin: {e}")
        return False


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    email: str


@router.post("/api/admin/login")
@limiter.limit("5/minute")
def admin_login(request: Request, body: LoginRequest):
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT password_hash FROM admins WHERE email = %s", (body.email,))
            row = cur.fetchone()
    except Exception as e:
        logger.warning(f"Admin login DB error: {e}")
        raise HTTPException(status_code=500, detail="Database unavailable")

    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    stored_hash = row[0]
    if isinstance(stored_hash, memoryview):
        stored_hash = bytes(stored_hash)
    if isinstance(stored_hash, (bytes, memoryview)):
        stored_hash = stored_hash.decode()

    if not bcrypt.checkpw(body.password.encode(), stored_hash.encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = _make_token(body.email)
    return LoginResponse(token=token, email=body.email)


@router.get("/api/admin/check")
def admin_check(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or not _verify_token(auth[7:]):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"ok": True}


def require_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or not _verify_token(auth[7:]):
        raise HTTPException(status_code=401, detail="Unauthorized")
