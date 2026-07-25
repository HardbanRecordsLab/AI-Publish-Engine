from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse

from backend.core import cost_tracker
from backend.core.jobs import count_jobs, delete_job, get_all_jobs, get_job, update_job
from backend.limiter import limiter
from backend.routers.auth import require_admin

router = APIRouter()


@router.get("/api/admin/ai-costs", dependencies=[Depends(require_admin)])
@limiter.limit("30/minute")
def admin_ai_costs(request: Request, days: int = Query(7, ge=1, le=90)):
    """Estimated AI provider spend — see backend/core/cost_tracker.py for
    the pricing table and its accuracy caveats."""
    return cost_tracker.get_summary(days)


@router.get("/api/admin/jobs", dependencies=[Depends(require_admin)])
@limiter.limit("60/minute")
def admin_list_jobs(request: Request, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    jobs = get_all_jobs(offset, limit)
    total = count_jobs()
    return {
        "jobs": [{
        "id": j["id"],
        "status": j["status"],
        "progress": j["progress"],
        "topic": j.get("topic", ""),
        "style": j.get("style", ""),
        "content_type": j.get("content_type", ""),
        "created_at": str(j.get("created_at", "")),
    } for j in jobs],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.delete("/api/admin/jobs/{job_id}", dependencies=[Depends(require_admin)])
@limiter.limit("30/minute")
def admin_delete_job(request: Request, job_id: str):
    delete_job(job_id)
    return {"status": "deleted"}


@router.post("/api/admin/jobs/{job_id}/retry", dependencies=[Depends(require_admin)])
@limiter.limit("20/minute")
def admin_retry_job(request: Request, job_id: str):
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job["status"] != "done":
        update_job(job_id, "queued", 0, error="")
    return {"status": "retrying"}


@router.get("/api/admin/jobs/export", dependencies=[Depends(require_admin)])
@limiter.limit("10/minute")
def admin_export_csv(request: Request, limit: int = Query(10000, ge=1, le=50000)):
    jobs = get_all_jobs(0, limit)
    import csv
    from io import StringIO
    output = StringIO()
    w = csv.writer(output)
    w.writerow(["id", "status", "progress", "topic", "style", "content_type", "created_at"])
    for j in jobs:
        w.writerow([j.get("id", ""), j.get("status", ""), j.get("progress", 0),
                    j.get("topic", ""), j.get("style", ""), j.get("content_type", ""),
                    str(j.get("created_at", ""))])
    return Response(content=output.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=ai_publish_jobs.csv"})
