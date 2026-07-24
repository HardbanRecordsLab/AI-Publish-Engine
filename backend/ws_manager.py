import asyncio
import time
from threading import Lock

from fastapi import WebSocket
from loguru import logger


class ConnectionManager:
    def __init__(self):
        self.connections: dict[str, set[WebSocket]] = {}
        self._lock = Lock()

    async def connect(self, job_id: str, ws: WebSocket):
        await ws.accept()
        with self._lock:
            self.connections.setdefault(job_id, set()).add(ws)

    def disconnect(self, job_id: str, ws: WebSocket):
        with self._lock:
            self.connections.get(job_id, set()).discard(ws)

    async def broadcast(self, job_id: str, data: dict):
        dead = set()
        with self._lock:
            targets = list(self.connections.get(job_id, set()))
        for ws in targets:
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        if dead:
            with self._lock:
                for ws in dead:
                    self.connections.get(job_id, set()).discard(ws)

    @property
    def active_jobs(self) -> list:
        with self._lock:
            return list(self.connections.keys())


manager = ConnectionManager()

# Thread-safe progress store for worker -> WebSocket bridge
_progress_store: dict[str, dict] = {}
_progress_lock = Lock()

# The FastAPI/uvicorn event loop, captured at startup (see main.py) so worker
# threads can schedule a broadcast onto it via run_coroutine_threadsafe.
# Previously this called asyncio.run(...) per-update, which spins up (and
# tears down) a brand-new event loop on every single progress tick, and
# silently swallowed the RuntimeError it raises when called from a thread
# that already has a running loop — i.e. the broadcast would vanish with no
# log line if this were ever called from async code instead of a worker
# thread.
_main_loop: asyncio.AbstractEventLoop | None = None


def set_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _main_loop
    _main_loop = loop


def update_progress(job_id: str, status: str, progress: int, **extra):
    """Called from worker threads (or async code) to publish progress updates."""
    data = {"job_id": job_id, "status": status, "progress": progress, "timestamp": time.time(), **extra}
    with _progress_lock:
        _progress_store[job_id] = data
    if _main_loop is None:
        logger.warning(f"update_progress({job_id}): no event loop registered, WS broadcast skipped")
        return
    try:
        asyncio.run_coroutine_threadsafe(manager.broadcast(job_id, data), _main_loop)
    except RuntimeError as e:
        logger.warning(f"update_progress({job_id}): failed to schedule WS broadcast: {e}")


def get_progress(job_id: str) -> dict | None:
    with _progress_lock:
        return _progress_store.get(job_id)


# Cancellation store
_cancel_flags: dict[str, bool] = {}
_cancel_lock = Lock()


def cancel_job(job_id: str):
    with _cancel_lock:
        _cancel_flags[job_id] = True


def is_cancelled(job_id: str) -> bool:
    with _cancel_lock:
        return _cancel_flags.get(job_id, False)


def clear_cancel(job_id: str):
    with _cancel_lock:
        _cancel_flags.pop(job_id, None)
