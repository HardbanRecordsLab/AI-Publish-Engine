"""Book Series Manager REST endpoints."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from backend.core.jobs import get_job
from backend.core.series import (
    add_book_to_series,
    create_series,
    delete_series,
    generate_series_landing,
    get_series,
    list_series,
    remove_book_from_series,
    update_series,
)
from backend.limiter import limiter

router = APIRouter()


@router.get("/api/series")
@limiter.limit("60/minute")
def api_list_series(request: Request):
    return list_series()


@router.get("/api/series/{series_id}")
@limiter.limit("60/minute")
def api_get_series(request: Request, series_id: str):
    s = get_series(series_id)
    if not s:
        raise HTTPException(404, "Series not found")
    return s


@router.post("/api/series")
@limiter.limit("30/minute")
def api_create_series(request: Request, body: dict):
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(400, "Series name is required")
    description = body.get("description", "")
    author = body.get("author", "")
    genre = body.get("genre", "")
    return create_series(name, description, author, genre)


@router.put("/api/series/{series_id}")
@limiter.limit("30/minute")
def api_update_series(request: Request, series_id: str, body: dict):
    result = update_series(series_id, body)
    if not result:
        raise HTTPException(404, "Series not found")
    return result


@router.delete("/api/series/{series_id}")
@limiter.limit("30/minute")
def api_delete_series(request: Request, series_id: str):
    if delete_series(series_id):
        return {"status": "deleted"}
    raise HTTPException(404, "Series not found")


@router.post("/api/series/{series_id}/books")
@limiter.limit("30/minute")
def api_add_book(request: Request, series_id: str, body: dict):
    job_id = body.get("job_id", "").strip()
    if not job_id:
        raise HTTPException(400, "job_id is required")
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    title = body.get("title", "") or job.get("topic", f"Book #{body.get('volume', '?')}")
    volume = body.get("volume")
    result = add_book_to_series(series_id, job_id, title, volume)
    if not result:
        raise HTTPException(404, "Series not found")
    return result


@router.delete("/api/series/{series_id}/books/{job_id}")
@limiter.limit("30/minute")
def api_remove_book(request: Request, series_id: str, job_id: str):
    result = remove_book_from_series(series_id, job_id)
    if not result:
        raise HTTPException(404, "Series not found")
    return result


@router.get("/api/series/{series_id}/landing")
@limiter.limit("30/minute")
def api_series_landing(request: Request, series_id: str):
    s = get_series(series_id)
    if not s:
        raise HTTPException(404, "Series not found")
    html = generate_series_landing(series_id)
    return HTMLResponse(content=html)
