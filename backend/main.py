import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend import ws_manager
from backend.config import settings
from backend.limiter import limiter
from backend.routers import (
    admin_router,
    auth_router,
    design_tokens_router,
    editor_router,
    health_router,
    jobs_router,
    publishing_router,
    series_router,
    stats_router,
    templates_router,
)

# Error tracking — entirely opt-in. With no SENTRY_DSN set, sentry_sdk.init()
# is never called and every sentry_sdk.* call below becomes a documented
# no-op, so this has zero effect on anyone who hasn't set up a Sentry
# project. See backend/config.py for the related settings.
if settings.sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        integrations=[FastApiIntegration()],
        traces_sample_rate=settings.sentry_traces_sample_rate,
    )
    logger.info(f"Sentry error tracking enabled (environment={settings.sentry_environment})")


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
    if settings.sentry_dsn:
        import sentry_sdk
        sentry_sdk.capture_exception(exc)
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
