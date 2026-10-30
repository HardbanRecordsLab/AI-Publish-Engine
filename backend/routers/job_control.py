"""Controls on a job that is not simply "start and wait": resume a stopped one, review the outline of a course before it is written,
and rewrite a single day of a finished course with a note from the author."""
import json
import os
import threading

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from loguru import logger

from backend.agents.course_agents import make_llm
from backend.core import checkpoint, course_gen, webresearch
from backend.core.course_engine import build_course_html
from backend.core.jobs import get_job, update_job
from backend.limiter import limiter
from backend.routers.auth import require_admin
from backend.routers.jobs import OUTPUT_DIR, is_running, resume_job

router = APIRouter()
_rewrites: dict[str, dict] = {}   # job id -> state of the last rewrite ({status: running|done|failed, index, error})
_rewrites_lock = threading.Lock()


def _error(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


async def _json(request: Request) -> dict:
    try:
        data = await request.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


@router.post("/api/jobs/{job_id}/resume", dependencies=[Depends(require_admin)])
@limiter.limit("20/minute")
def resume(request: Request, job_id: str):
    ok, message = resume_job(job_id)
    return {"status": "resumed", "message": message} if ok else _error(message, 409)


# ------------------------------------------------------------------ outline review

def _parked_outline(job_id: str):
    job = get_job(job_id)
    if not job:
        return None, None, _error("Nie ma takiego zadania.", 404)
    outline = checkpoint.stage(job_id, "outline") if checkpoint.has(job_id) else None
    if not isinstance(outline, dict):
        return job, None, _error("To zadanie nie ma planu do przejrzenia.", 404)
    return job, outline, None


@router.get("/api/jobs/{job_id}/outline", dependencies=[Depends(require_admin)])
@limiter.limit("60/minute")
def get_outline(request: Request, job_id: str):
    job, outline, err = _parked_outline(job_id)
    if err:
        return err
    return {"status": job["status"], "approved": bool(checkpoint.stage(job_id, "outline_approved")), "outline": course_gen.public_outline(outline)}


@router.put("/api/jobs/{job_id}/outline", dependencies=[Depends(require_admin)])
@limiter.limit("60/minute")
async def put_outline(request: Request, job_id: str):
    job, outline, err = _parked_outline(job_id)
    if err:
        return err
    if job["status"] != "awaiting_approval":
        return _error("Plan można zmieniać tylko, dopóki czeka na zatwierdzenie.", 409)
    try:
        edited = course_gen.apply_outline_edit(outline, await _json(request))
    except ValueError as e:
        return _error(str(e))
    checkpoint.save_stage(job_id, "outline", edited)
    return {"status": "saved", "outline": course_gen.public_outline(edited)}


@router.post("/api/jobs/{job_id}/approve", dependencies=[Depends(require_admin)])
@limiter.limit("20/minute")
async def approve_outline(request: Request, job_id: str):
    """Approve the outline (optionally with the author's last edits in the body) and let the job write the course."""
    job, outline, err = _parked_outline(job_id)
    if err:
        return err
    if job["status"] != "awaiting_approval":
        return _error("To zadanie nie czeka na zatwierdzenie planu.", 409)
    body = await _json(request)
    if body.get("phases"):
        try:
            checkpoint.save_stage(job_id, "outline", course_gen.apply_outline_edit(outline, body))
        except ValueError as e:
            return _error(str(e))
    checkpoint.save_stage(job_id, "outline_approved", True)
    ok, message = resume_job(job_id)
    return {"status": "approved", "message": "Plan zatwierdzony, piszę kurs."} if ok else _error(message, 409)


# ------------------------------------------------------------------ rewrite one day of a finished course

def _rewrite(job_id: str, index: int, note: str) -> None:
    try:
        job = get_job(job_id)
        course = job["book_data"] if isinstance(job["book_data"], dict) else json.loads(job["book_data"])
        inputs, snapshot = checkpoint.inputs(job_id) or {}, checkpoint.stage(job_id, "ctx") or {}
        outline = {**checkpoint.stage(job_id, "outline"), "_brief": inputs.get("text", "")}
        sources = [webresearch.Source(**s) for s in snapshot.get("web_sources", [])]
        llm = make_llm(inputs.get("provider"))
        new = course_gen.rewrite_unit(llm, outline, course, index, sources, note=note, language=inputs.get("language", ""), tone=inputs.get("tone", ""))
        problems = course_gen.validate_course(new)
        if problems:
            raise course_gen.CourseGenerationError("Przepisany kurs jest niekompletny: " + "; ".join(problems[:4]))
        html = build_course_html(new, accent_color=inputs.get("accent_color", ""))
        path = os.path.join(OUTPUT_DIR, f"{job_id}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        update_job(job_id, "done", 100, website_path=path, html=html, book_data=json.dumps(new))
        state = {"status": "done", "index": index}
    except Exception as e:  # noqa: BLE001 - the author sees the reason; the course itself is untouched
        logger.warning(f"Job {job_id}: rewrite of unit {index + 1} failed: {e}")
        state = {"status": "failed", "index": index, "error": str(e)[:300]}
    with _rewrites_lock:
        _rewrites[job_id] = state


@router.post("/api/jobs/{job_id}/rewrite", dependencies=[Depends(require_admin)])
@limiter.limit("10/minute")
async def rewrite(request: Request, job_id: str):
    body = await _json(request)
    job = get_job(job_id)
    if not job or job["status"] != "done" or job.get("content_type") != "interactive-course" or not job.get("book_data"):
        return _error("Przepisać można dzień ukończonego kursu interaktywnego.", 409)
    if not (checkpoint.has(job_id) and checkpoint.stage(job_id, "outline") is not None and checkpoint.stage(job_id, "ctx")):
        return _error("Kreator nie ma już materiałów tego kursu (są przechowywane 30 dni). Uruchom kurs od nowa.", 409)
    index = body.get("index")
    note = str(body.get("note") or "").strip()
    if not isinstance(index, int) or isinstance(index, bool) or index < 0:
        return _error("Podaj numer dnia do przepisania.")
    if len(note) < 5:
        return _error("Napisz, co ma się zmienić (co najmniej kilka słów).")
    with _rewrites_lock:
        if _rewrites.get(job_id, {}).get("status") == "running" or is_running(job_id):
            return _error("Ten kurs jest właśnie przepisywany.", 409)
        _rewrites[job_id] = {"status": "running", "index": index}
    threading.Thread(target=_rewrite, args=(job_id, index, note), daemon=True).start()
    return JSONResponse({"status": "running", "index": index}, status_code=202)


@router.get("/api/jobs/{job_id}/rewrite", dependencies=[Depends(require_admin)])
@limiter.limit("120/minute")
def rewrite_state(request: Request, job_id: str):
    with _rewrites_lock:
        return _rewrites.get(job_id) or {"status": "idle"}
