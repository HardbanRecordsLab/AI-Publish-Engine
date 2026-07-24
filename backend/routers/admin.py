from fastapi import APIRouter, Response, Depends, Query
from fastapi.responses import JSONResponse, HTMLResponse

from backend.core.jobs import get_all_jobs, get_job, delete_job, update_job, count_jobs
from backend.routers.auth import require_admin

router = APIRouter()


@router.get("/api/admin/jobs", dependencies=[Depends(require_admin)])
def admin_list_jobs(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
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
def admin_delete_job(job_id: str):
    delete_job(job_id)
    return {"status": "deleted"}


@router.post("/api/admin/jobs/{job_id}/retry", dependencies=[Depends(require_admin)])
def admin_retry_job(job_id: str):
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job["status"] != "done":
        update_job(job_id, "queued", 0, error="")
    return {"status": "retrying"}


@router.get("/api/admin/jobs/export", dependencies=[Depends(require_admin)])
def admin_export_csv(limit: int = Query(10000, ge=1, le=50000)):
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
