from backend.core.jobs import create_job, update_job, get_job


class TestJobs:
    def test_create_job(self):
        jid = create_job("minimal")
        job = get_job(jid)
        assert job is not None
        assert job["status"] == "queued"
        assert job["style"] == "minimal"

    def test_create_job_generates_unique_ids(self):
        a = create_job("dark")
        b = create_job("minimal")
        assert a != b

    def test_update_job_progress(self):
        jid = create_job("corporate")
        update_job(jid, "processing", 50)
        job = get_job(jid)
        assert job["status"] == "processing"
        assert job["progress"] == 50

    def test_update_job_completion(self):
        jid = create_job("minimal")
        update_job(jid, "done", 100, output_path="/tmp/test.pdf")
        job = get_job(jid)
        assert job["status"] == "done"
        assert job["progress"] == 100
        assert job["output_path"] == "/tmp/test.pdf"

    def test_update_job_error(self):
        jid = create_job("minimal")
        update_job(jid, "failed", error="Something went wrong")
        job = get_job(jid)
        assert job["status"] == "failed"
        assert "went wrong" in job["error"]

    def test_update_job_topic(self):
        jid = create_job("minimal")
        update_job(jid, "processing", 65, topic="technology")
        job = get_job(jid)
        assert job["topic"] == "technology"

    def test_get_nonexistent_job(self):
        assert get_job("nonexistent-id") is None

    def test_update_nonexistent_job_does_not_crash(self):
        update_job("fake-id", "done")  # should not raise
