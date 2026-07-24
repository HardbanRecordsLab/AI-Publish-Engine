"""Tests for AI agent pipeline."""
from backend.orchestrator.agent import PipelineContext, BaseAgent


class TestPipelineContext:
    def test_default_values(self):
        ctx = PipelineContext(job_id="test-123", text="hello", style="minimal")
        assert ctx.job_id == "test-123"
        assert ctx.text == "hello"
        assert ctx.style == "minimal"
        assert ctx.progress == 0
        assert ctx.content_type == "ebook"
        assert ctx.error is None
        assert ctx.ebook_dict == {}

    def test_set_progress(self):
        ctx = PipelineContext(job_id="t", text="x", style="m")
        ctx.set_progress(50)
        assert ctx.progress == 50


class TestQALocalChecks:
    def test_empty_section_detected(self):
        from backend.agents.qa_agent import _local_checks
        ctx = PipelineContext(job_id="t", text="x", style="m")
        ctx.ebook_dict = {
            "chapters": [{
                "title": "Ch1",
                "introduction": "Intro",
                "key_takeaway": "KT",
                "sections": [
                    {"heading": "", "content": ""},
                ],
            }],
            "conclusion": {"title": "C", "content": "End"},
        }
        issues = _local_checks(ctx)
        assert len(issues) >= 1
        assert any(i["type"] == "content" and i["severity"] == "high" for i in issues)

    def test_no_issues_for_good_content(self):
        from backend.agents.qa_agent import _local_checks
        ctx = PipelineContext(job_id="t", text="x", style="m")
        ctx.ebook_dict = {
            "chapters": [{
                "title": "Ch1",
                "introduction": "Intro text",
                "key_takeaway": "Key point",
                "sections": [
                    {"heading": "Section 1", "content": "Some content here"},
                ],
            }],
            "conclusion": {"title": "C", "content": "Valid conclusion"},
        }
        issues = _local_checks(ctx)
        content_issues = [i for i in issues if i["type"] == "content"]
        assert len(content_issues) == 0

    def test_missing_introduction(self):
        from backend.agents.qa_agent import _local_checks
        ctx = PipelineContext(job_id="t", text="x", style="m")
        ctx.ebook_dict = {
            "chapters": [{
                "title": "Ch1",
                "introduction": "",
                "key_takeaway": "KT",
                "sections": [{"heading": "H", "content": "C"}],
            }],
            "conclusion": {"title": "C", "content": "End"},
        }
        issues = _local_checks(ctx)
        assert any(i["type"] == "structure" and "introduction" in i["description"].lower() for i in issues)

    def test_missing_conclusion(self):
        from backend.agents.qa_agent import _local_checks
        ctx = PipelineContext(job_id="t", text="x", style="m")
        ctx.ebook_dict = {
            "chapters": [{
                "title": "Ch1",
                "introduction": "Intro",
                "key_takeaway": "KT",
                "sections": [{"heading": "H", "content": "C"}],
            }],
            "conclusion": {"title": "C", "content": ""},
        }
        issues = _local_checks(ctx)
        assert any(i["type"] == "structure" and i["severity"] == "medium" for i in issues)
