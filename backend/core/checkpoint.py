"""Per-job checkpoints: the inputs of a job and the result of every expensive step.

A job that stops half way (provider error, server restart, the daily AI budget) is resumed from where it stopped
instead of being run, and paid for, from zero. Three plain JSON files per job next to the job ledger: the inputs
(written once), the results of whole steps (rewritten as a step finishes) and the finished units of a long step
(a day, a chapter; small, rewritten often). They are removed when they are no longer needed.
"""
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

from loguru import logger

_ID = re.compile(r"[0-9A-Za-z_-]{6,64}")
_lock = threading.Lock()


def _dir() -> Path:
    d = Path(os.environ.get("AI_CHECKPOINT_DIR") or Path(__file__).resolve().parents[2] / "jobs" / "checkpoints")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _file(job_id: str, kind: str) -> Path:
    if not isinstance(job_id, str) or not _ID.fullmatch(job_id):
        raise ValueError("invalid job id")
    return _dir() / f"{job_id}.{kind}.json"


def _read(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        logger.warning(f"checkpoint: {path.name} unreadable ({e})")
        return {}


def _write(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    tmp.replace(path)


def save_inputs(job_id: str, inputs: dict) -> None:
    """The arguments the job was started with; written once, so a resume runs with exactly the same brief."""
    with _lock:
        path = _file(job_id, "in")
        if not path.exists():
            _write(path, inputs)


def inputs(job_id: str) -> dict | None:
    with _lock:
        data = _read(_file(job_id, "in"))
    return data or None


def has(job_id: str) -> bool:
    try:
        return _file(job_id, "in").exists()
    except ValueError:
        return False


def stage(job_id: str, name: str, default: Any = None) -> Any:
    with _lock:
        return _read(_file(job_id, "st")).get(name, default)


def save_stage(job_id: str, name: str, value: Any) -> None:
    with _lock:
        path = _file(job_id, "st")
        data = _read(path)
        data[name] = value
        _write(path, data)


def save_item(job_id: str, name: str, index: int, value: Any) -> None:
    """One finished unit of a long step (a day, a chapter), so a resume only redoes the missing ones."""
    with _lock:
        path = _file(job_id, "it")
        data = _read(path)
        data.setdefault(name, {})[str(index)] = value
        _write(path, data)


def items(job_id: str, name: str) -> dict[int, Any]:
    with _lock:
        raw = _read(_file(job_id, "it")).get(name) or {}
    return {int(k): v for k, v in raw.items() if str(k).isdigit()} if isinstance(raw, dict) else {}


def clear(job_id: str, *, keep_inputs: bool = False) -> None:
    with _lock:
        for kind in ("st", "it") if keep_inputs else ("st", "it", "in"):
            try:
                _file(job_id, kind).unlink(missing_ok=True)
            except (ValueError, OSError):
                pass


def purge_older_than(days: float) -> int:
    """Delete checkpoints nobody touched for `days` days; returns how many files went."""
    cutoff, gone = time.time() - days * 86400, 0
    with _lock:
        for p in _dir().glob("*.json"):
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink()
                    gone += 1
            except OSError:
                pass
    return gone
