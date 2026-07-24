import time
import os
from datetime import datetime
from fastapi import APIRouter
from backend.core.ai import PROVIDERS
from backend.core.tokens import list_themes

router = APIRouter()

START_TIME = time.time()


@router.get("/api/health")
def health():
    uptime = time.time() - START_TIME
    # Check DB connectivity
    db_ok = False
    try:
        from backend.core.database import get_pool
        pool = get_pool()
        if pool:
            db_ok = True
    except Exception:
        pass
    return {
        "status": "ok",
        "uptime_seconds": round(uptime),
        "timestamp": datetime.now().isoformat(),
        "version": "2.1.0",
        "database": "connected" if db_ok else "fallback (JSON)",
        "themes_loaded": len(list_themes()),
        "providers_configured": sum(1 for p in PROVIDERS if os.getenv(PROVIDERS[p]["api_key_env"])),
        "python_env": os.getenv("PYTHON_ENV", "production"),
    }


@router.get("/api/health/check")
def health_check():
    """Simple check for load balancers (minimal response)."""
    return {"status": "ok"}


@router.get("/api/providers")
def get_providers():
    return [
        {
            "id": k,
            "model": v["model"],
            "site": v["site"],
            "env_var": v["api_key_env"],
            "configured": bool(os.getenv(v["api_key_env"])),
        }
        for k, v in PROVIDERS.items()
    ]
