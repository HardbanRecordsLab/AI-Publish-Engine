import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from loguru import logger

from backend.limiter import limiter
from backend.config import settings
from backend import ws_manager
from backend.routers import health_router, templates_router, jobs_router, admin_router, publishing_router, editor_router, series_router, auth_router, design_tokens_router, stats_router


async def _stale_job_watchdog():
    """Periodically fail jobs stuck in queued/processing (e.g. after a server
    restart killed their worker thread mid-run), so users never see an
    infinite spinner with no explanation."""
    from backend.core.jobs import fail_stale_jobs
    while True:
        try:
            failed_ids = fail_stale_jobs(settings.stale_job_timeout_minutes)
            if failed_ids:
                logger.warning(f"Watchdog: marked {len(failed_ids)} stale job(s) as failed: {failed_ids}")
        except Exception as e:
            logger.warning(f"Stale job watchdog error: {e}")
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ws_manager.set_event_loop(asyncio.get_running_loop())
    watchdog_task = asyncio.create_task(_stale_job_watchdog())
    try:
        yield
    finally:
        watchdog_task.cancel()


app = FastAPI(title="AI Design Engine", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
_cors = settings.cors_origins.split(",") if settings.cors_origins else ["*"]
if _cors == ["*"]:
    logger.warning(
        "CORS_ORIGINS is not set — allowing all origins ('*'). "
        "Set CORS_ORIGINS in .env to a comma-separated allowlist before running in production."
    )
app.add_middleware(CORSMiddleware, allow_origins=_cors, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

app.include_router(health_router)
app.include_router(templates_router)
app.include_router(jobs_router)
app.include_router(admin_router)
app.include_router(publishing_router)
app.include_router(editor_router)
app.include_router(series_router)
app.include_router(auth_router)
app.include_router(design_tokens_router)
app.include_router(stats_router)
