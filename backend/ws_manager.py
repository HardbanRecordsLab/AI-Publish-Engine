import asyncio
import time
from threading import Lock
from typing import Dict, Set, Optional
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.connections: Dict[str, Set[WebSocket]] = {}
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
_progress_store: Dict[str, dict] = {}
_progress_lock = Lock()


def update_progress(job_id: str, status: str, progress: int, **extra):
    """Called from worker threads to publish progress updates."""
    data = {"job_id": job_id, "status": status, "progress": progress, "timestamp": time.time(), **extra}
    with _progress_lock:
        _progress_store[job_id] = data
    try:
        asyncio.run(manager.broadcast(job_id, data))
    except RuntimeError:
        pass  # no event loop in this thread


def get_progress(job_id: str) -> Optional[dict]:
    with _progress_lock:
        return _progress_store.get(job_id)


# Cancellation store
_cancel_flags: Dict[str, bool] = {}
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
