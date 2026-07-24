from fastapi import APIRouter
from backend.core.jobs import get_all_jobs

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/dashboard")
def dashboard_stats():
    jobs = get_all_jobs(0, 10000)
    total = len(jobs)
    statuses = {}
    topics = {}
    styles = {}
    daily = {}

    for j in jobs:
        s = j.get("status", "unknown")
        statuses[s] = statuses.get(s, 0) + 1

        t = j.get("topic", "unknown")
        topics[t] = topics.get(t, 0) + 1

        st = j.get("style", "unknown")
        styles[st] = styles.get(st, 0) + 1

        created = str(j.get("created_at", ""))[:10]
        if created:
            daily[created] = daily.get(created, 0) + 1

    success_rate = round((statuses.get("done", 0) / max(total, 1)) * 100, 1)

    return {
        "total_jobs": total,
        "statuses": statuses,
        "success_rate": success_rate,
        "topics": topics,
        "styles": styles,
        "daily_counts": dict(sorted(daily.items())[-30:]),
    }
