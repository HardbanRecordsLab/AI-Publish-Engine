"""Fallback in-memory + JSON file job storage when PostgreSQL is unavailable."""
import json
import os
import uuid
from datetime import datetime

JOBS = {}
JOB_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "jobs", "jobs.json")


def _save():
    serializable = {}
    for jid, job in JOBS.items():
        serializable[jid] = {
            "status": job["status"],
            "progress": job["progress"],
            "created_at": job["created_at"].isoformat(),
            "style": job.get("style"),
            "topic": job.get("topic"),
            "content_type": job.get("content_type"),
            "audience": job.get("audience"),
            "tone": job.get("tone"),
            "chapters": job.get("chapters"),
            "keywords": job.get("keywords"),
            "language": job.get("language"),
            "output_path": job.get("output_path"),
            "epub_path": job.get("epub_path"),
            "docx_path": job.get("docx_path"),
            "html": job.get("html"),
            "website_path": job.get("website_path"),
            "error": job.get("error"),
            "book_data": job.get("book_data"),
            "build_params": job.get("build_params"),
        }
    os.makedirs(os.path.dirname(JOB_FILE), exist_ok=True)
    with open(JOB_FILE, "w") as f:
        json.dump(serializable, f, indent=2)


def _load():
    if os.path.exists(JOB_FILE):
        with open(JOB_FILE) as f:
            data = json.load(f)
            for jid, job in data.items():
                job["created_at"] = datetime.fromisoformat(job["created_at"])
                JOBS[jid] = job


def create_job(style="minimal", content_type="ebook", audience="", tone="", chapters="", keywords="", language=""):
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "status": "queued",
        "progress": 0,
        "style": style,
        "content_type": content_type,
        "audience": audience,
        "tone": tone,
        "chapters": chapters,
        "keywords": keywords,
        "language": language,
        "topic": None,
        "created_at": datetime.now(),
        "output_path": None,
        "epub_path": None,
        "docx_path": None,
        "html": None,
        "website_path": None,
        "error": None,
        "book_data": None,
        "build_params": None,
    }
    _save()
    return job_id


def update_job(job_id, status, progress=None, output_path=None, epub_path=None, docx_path=None, html=None, website_path=None, error=None, topic=None, book_data=None, build_params=None):
    if job_id not in JOBS:
        return
    JOBS[job_id]["status"] = status
    if progress is not None:
        JOBS[job_id]["progress"] = progress
    if output_path:
        JOBS[job_id]["output_path"] = output_path
    if epub_path:
        JOBS[job_id]["epub_path"] = epub_path
    if docx_path:
        JOBS[job_id]["docx_path"] = docx_path
    if html:
        JOBS[job_id]["html"] = html
    if website_path:
        JOBS[job_id]["website_path"] = website_path
    if error:
        JOBS[job_id]["error"] = error
    if topic:
        JOBS[job_id]["topic"] = topic
    if book_data is not None:
        JOBS[job_id]["book_data"] = book_data
    if build_params is not None:
        JOBS[job_id]["build_params"] = build_params
    _save()


def get_job(job_id):
    try:
        if os.path.exists(JOB_FILE):
            with open(JOB_FILE) as f:
                data = json.load(f)
            if job_id in data:
                job = data[job_id]
                job["created_at"] = datetime.fromisoformat(job["created_at"])
                JOBS[job_id] = job
                return job
    except Exception:
        pass
    return JOBS.get(job_id)


def get_all_jobs(offset: int = 0, limit: int = 50):
    results = []
    try:
        if os.path.exists(JOB_FILE):
            with open(JOB_FILE) as f:
                data = json.load(f)
            for jid, job in data.items():
                job["id"] = jid
                results.append(job)
    except Exception:
        for jid, job in JOBS.items():
            job["id"] = jid
            results.append(job)
    results.sort(key=lambda j: j.get("created_at", ""), reverse=True)
    return results[offset:offset + limit]


def count_jobs() -> int:
    try:
        if os.path.exists(JOB_FILE):
            with open(JOB_FILE) as f:
                data = json.load(f)
            return len(data)
    except Exception:
        pass
    return len(JOBS)


def fail_stale_jobs(timeout_minutes: int) -> list:
    """Mark jobs stuck in 'queued'/'processing' for >timeout_minutes as failed."""
    from datetime import timedelta
    now = datetime.now()
    failed = []
    for jid, job in list(JOBS.items()):
        if job.get("status") in ("queued", "processing"):
            created = job.get("created_at")
            if isinstance(created, str):
                created = datetime.fromisoformat(created)
            if created and (now - created) > timedelta(minutes=timeout_minutes):
                job["status"] = "failed"
                job["error"] = "Stale job — automatically failed by watchdog"
                failed.append(jid)
    if failed:
        _save()
    return failed


def delete_job(job_id):
    if job_id in JOBS:
        del JOBS[job_id]
    _save()

    try:
        if os.path.exists(JOB_FILE):
            with open(JOB_FILE) as f:
                data = json.load(f)
            if job_id in data:
                del data[job_id]
                with open(JOB_FILE, "w") as f:
                    json.dump(data, f, indent=2)
    except Exception:
        pass


_load()
