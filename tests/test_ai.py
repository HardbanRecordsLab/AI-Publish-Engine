import os

import pytest
from backend.core.ai import analyze_text, plan_infographics, generate_design_system, _clean_json, _extract_json_array

# TestAnalyzeText / TestPlanInfographics make real network calls to real AI providers —
# genuine integration tests, not unit tests, and they were never going to pass against
# conftest.py's/CI's placeholder GROQ_API_KEY ("test-placeholder-key" / "test-key"):
# every provider correctly rejects it (401/429/404 depending on provider), _try_providers
# exhausts its whole fallback chain, and the call raises. Confirmed 2026-09-22: `pytest -x`
# (as CI actually runs it) aborted the entire suite on the first of these, independent of
# anything else fixed that day. Opt-in only, like any test that needs live external
# credentials — set RUN_LIVE_AI_TESTS=1 (with real provider keys in the environment) to
# exercise these for real.
live_ai = pytest.mark.skipif(
    os.getenv("RUN_LIVE_AI_TESTS") != "1",
    reason="needs a real AI provider key; set RUN_LIVE_AI_TESTS=1 to run against live providers",
)


class TestCleanJson:
    def test_extracts_from_raw_text(self):
        raw = 'Some text {"key": "value"} trailing'
        assert _clean_json(raw) == {"key": "value"}

    def test_handles_nested(self):
        raw = '{"a": {"b": [1, 2]}}'
        assert _clean_json(raw) == {"a": {"b": [1, 2]}}

    def test_raises_on_no_json(self):
        with pytest.raises(ValueError):
            _clean_json("no json here")

    def test_handles_escaped_chars(self):
        raw = '{"text": "hello\\nworld"}'
        assert _clean_json(raw) == {"text": "hello\nworld"}


class TestExtractJsonArray:
    def test_extracts_array(self):
        raw = '[{"a": 1}, {"b": 2}]'
        assert _extract_json_array(raw) == [{"a": 1}, {"b": 2}]

    def test_handles_markdown_wrapped(self):
        raw = '```json\n[{"x": 1}]\n```'
        result = _extract_json_array(raw)
        assert result == [{"x": 1}]

    def test_returns_empty_on_failure(self):
        assert _extract_json_array("not json") == []


class TestGenerateDesignSystem:
    def test_minimal(self):
        ds = generate_design_system("minimal", "professional")
        assert ds["theme"] == "minimal"
        assert ds["colors"]["accent"] == "#4A4A4A"

    def test_corporate(self):
        ds = generate_design_system("corporate", "professional")
        assert ds["theme"] == "corporate"

    def test_dark(self):
        ds = generate_design_system("dark", "professional")
        assert ds["theme"] == "dark"

    def test_unknown_style_defaults_to_minimal(self):
        ds = generate_design_system("nonexistent", "professional")
        assert ds["theme"] == "minimal"


@live_ai
class TestAnalyzeText:
    def test_returns_structured_ebook(self, sample_text):
        result = analyze_text(sample_text)
        assert isinstance(result, dict)
        assert "title" in result
        assert "chapters" in result
        assert "conclusion" in result
        assert len(result["chapters"]) >= 3
        for ch in result["chapters"]:
            assert "title" in ch
            assert "sections" in ch
            assert len(ch["sections"]) >= 1

    def test_topic_detected(self, sample_text):
        result = analyze_text(sample_text)
        assert result.get("topic") in [
            "technology", "artificial_intelligence", "health", "finance",
            "education", "marketing", "psychology", "survival", "business", "general",
        ]

    def test_summary_present(self, sample_text):
        result = analyze_text(sample_text)
        assert result.get("summary")


@live_ai
class TestPlanInfographics:
    def test_returns_list(self, sample_analysis, sample_design):
        result = plan_infographics(sample_analysis, sample_design)
        assert isinstance(result, list)
        assert len(result) >= 2

    def test_items_have_required_keys(self, sample_analysis, sample_design):
        result = plan_infographics(sample_analysis, sample_design)
        for ig in result:
            assert "type" in ig
            assert "title" in ig
            assert "data_points" in ig
            assert ig["type"] in ["timeline", "process", "comparison", "list", "hierarchy"]
            assert len(ig["data_points"]) >= 2
