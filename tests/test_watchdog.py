"""Tests for stale job watchdog and database fail_stale_jobs."""
import os
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


class TestFailStaleJobsFallback:
    def test_fail_stale_jobs_no_stuck(self):
        from backend.core.jobs_fallback import JOBS, fail_stale_jobs
        JOBS.clear()
        JOBS["fresh_job"] = {
            "status": "queued", "progress": 0,
            "created_at": datetime.now(),
        }
        result = fail_stale_jobs(20)
        assert result == []

    def test_fail_stale_jobs_stuck(self):
        from backend.core.jobs_fallback import JOBS, fail_stale_jobs
        JOBS.clear()
        old = datetime.now() - timedelta(minutes=30)
        JOBS["stuck_job"] = {
            "status": "processing", "progress": 35,
            "created_at": old,
        }
        result = fail_stale_jobs(20)
        assert "stuck_job" in result
        assert JOBS["stuck_job"]["status"] == "failed"

    def test_fail_stale_jobs_ignores_done(self):
        from backend.core.jobs_fallback import JOBS, fail_stale_jobs
        JOBS.clear()
        old = datetime.now() - timedelta(minutes=30)
        JOBS["done_job"] = {
            "status": "done", "progress": 100,
            "created_at": old,
        }
        result = fail_stale_jobs(20)
        assert result == []

    def test_fail_stale_jobs_ignores_recent(self):
        from backend.core.jobs_fallback import JOBS, fail_stale_jobs
        JOBS.clear()
        recent = datetime.now() - timedelta(minutes=5)
        JOBS["recent_job"] = {
            "status": "queued", "progress": 0,
            "created_at": recent,
        }
        result = fail_stale_jobs(20)
        assert result == []


class TestJobFallback:
    def test_create_and_get_job(self):
        from backend.core.jobs_fallback import JOBS, create_job, get_job
        JOBS.clear()
        jid = create_job("dark", "ebook", "devs", "professional", "5", "ai", "en")
        job = get_job(jid)
        assert job is not None
        assert job["status"] == "queued"
        assert job["style"] == "dark"
        assert job["content_type"] == "ebook"

    def test_update_job(self):
        from backend.core.jobs_fallback import JOBS, create_job, update_job, get_job
        JOBS.clear()
        jid = create_job()
        update_job(jid, "done", 100)
        job = get_job(jid)
        assert job["status"] == "done"
        assert job["progress"] == 100

    def test_delete_job(self):
        from backend.core.jobs_fallback import JOBS, create_job, delete_job, get_job
        JOBS.clear()
        jid = create_job()
        delete_job(jid)
        assert get_job(jid) is None

    def test_get_all_jobs(self):
        from backend.core.jobs_fallback import JOBS, create_job, get_all_jobs
        JOBS.clear()
        jid1 = create_job()
        jid2 = create_job()
        all_jobs = get_all_jobs()
        assert len(all_jobs) >= 2
        ids = [j["id"] for j in all_jobs]
        assert jid1 in ids
        assert jid2 in ids
