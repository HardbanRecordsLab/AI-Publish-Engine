"""Tests for backend/core/cost_tracker.py — the AI spend ceiling that
protects against an unbounded bill across 8 paid providers. Every test
uses its own ledger file (via AI_COST_LEDGER_FILE) so they can't
interfere with each other or with a real ledger on disk.
"""
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def tracker(tmp_path, monkeypatch):
    """A cost_tracker module instance pointed at an isolated ledger file."""
    monkeypatch.setenv("AI_COST_LEDGER_FILE", str(tmp_path / "ledger.json"))
    monkeypatch.delenv("DAILY_AI_BUDGET_USD", raising=False)
    from backend.core import cost_tracker
    importlib.reload(cost_tracker)  # picks up the env var into LEDGER_FILE
    return cost_tracker


class TestEstimateCost:
    def test_known_model_uses_its_own_price(self, tracker):
        cost = tracker.estimate_cost("openai", "gpt-4o-mini", prompt_tokens=1_000_000, completion_tokens=0)
        assert cost == pytest.approx(0.15)  # $0.15 / 1M input tokens

    def test_unknown_model_uses_fallback_price(self, tracker):
        cost = tracker.estimate_cost("some-new-provider", "some-new-model", prompt_tokens=1_000_000, completion_tokens=0)
        assert cost == pytest.approx(tracker.DEFAULT_PRICE[0])

    def test_zero_tokens_costs_zero(self, tracker):
        assert tracker.estimate_cost("openai", "gpt-4o-mini", 0, 0) == 0.0


class TestRecordUsage:
    def test_accumulates_across_calls(self, tracker):
        c1 = tracker.record_usage("openai", "gpt-4o-mini", 1000, 500)
        c2 = tracker.record_usage("openai", "gpt-4o-mini", 1000, 500)
        assert tracker.get_daily_spend() == pytest.approx(c1 + c2)

    def test_persists_to_the_ledger_file(self, tracker):
        tracker.record_usage("mistral", "mistral-small-latest", 2000, 1000, job_id="job-abc")
        assert tracker.LEDGER_FILE.exists()
        summary = tracker.get_summary()
        assert summary["days"][0]["call_count"] == 1

    def test_job_id_is_recorded(self, tracker):
        tracker.record_usage("groq", "llama-3.1-8b-instant", 500, 500, job_id="job-xyz")
        data = tracker._load()
        today = tracker._today()
        assert data["days"][today]["calls"][0]["job_id"] == "job-xyz"


class TestBudgetCeiling:
    def test_no_budget_set_never_raises(self, tracker):
        tracker.record_usage("openai", "gpt-4o-mini", 10_000_000, 10_000_000)  # deliberately huge
        tracker.check_budget()  # must not raise

    def test_under_budget_does_not_raise(self, tracker, monkeypatch):
        monkeypatch.setenv("DAILY_AI_BUDGET_USD", "10.00")
        tracker.record_usage("openai", "gpt-4o-mini", 1000, 500)
        tracker.check_budget()  # must not raise

    def test_over_budget_raises_and_blocks_the_next_call(self, tracker, monkeypatch):
        monkeypatch.setenv("DAILY_AI_BUDGET_USD", "0.001")
        tracker.record_usage("openai", "gpt-4o-mini", 100_000, 50_000)  # ~$0.045, over the $0.001 ceiling
        with pytest.raises(RuntimeError, match="Daily AI budget exceeded"):
            tracker.check_budget()

    def test_negative_or_garbage_budget_treated_as_unlimited(self, tracker, monkeypatch):
        monkeypatch.setenv("DAILY_AI_BUDGET_USD", "not-a-number")
        tracker.record_usage("openai", "gpt-4o-mini", 100_000, 50_000)
        tracker.check_budget()  # must not raise — invalid config fails open to "unlimited", not closed


class TestGetSummary:
    def test_includes_budget_and_today(self, tracker, monkeypatch):
        monkeypatch.setenv("DAILY_AI_BUDGET_USD", "5.00")
        tracker.record_usage("openai", "gpt-4o-mini", 1000, 1000)
        summary = tracker.get_summary()
        assert summary["daily_budget_usd"] == 5.00
        assert summary["today_spend_usd"] > 0
        assert summary["days"][0]["date"] == tracker._today()
