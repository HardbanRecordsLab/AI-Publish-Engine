"""AI spend tracking + a hard daily budget ceiling.

Every AI provider call in this app funnels through backend.core.ai._call(),
which is the single place this module is hooked into — no other call site
needs to change. Before this existed, there was no cost visibility and no
limit at all: a bug, an abuse pattern, or just an unexpectedly busy day
could run up an unbounded bill across 8 paid providers with nothing to
stop it.

Pricing is illustrative, not exact. Providers change prices and some
(notably OpenRouter, which proxies many underlying models) don't expose a
single stable rate — treat get_daily_spend() as an order-of-magnitude
signal for the budget ceiling, not a reconciliation-grade billing figure.
"""
import json
import os
import threading
from datetime import date, datetime, timezone
from pathlib import Path

from loguru import logger

# USD per 1M tokens (input, output). Approximate published rates as of
# this module's introduction — update PRICING if a provider reprices.
PRICING: dict[str, tuple[float, float]] = {
    "gemini/gemini-2.0-flash-001": (0.10, 0.40),
    "groq/llama-3.1-8b-instant": (0.05, 0.08),
    "openrouter/qwen/qwen-2.5-72b-instruct": (0.35, 0.40),
    "mistral/mistral-small-latest": (0.20, 0.60),
    "openai/gpt-4o-mini": (0.15, 0.60),
    "cohere/command-r-plus": (2.50, 10.00),
    "claude/claude-sonnet-4-20250514": (3.00, 15.00),
    "deepseek/deepseek-chat": (0.14, 0.28),
}
DEFAULT_PRICE = (0.50, 1.50)  # conservative fallback for an unlisted model

LEDGER_FILE = Path(os.environ.get("AI_COST_LEDGER_FILE", "jobs/ai_cost_ledger.json"))
_lock = threading.Lock()


def _today() -> str:
    return date.today().isoformat()


def _load() -> dict:
    if LEDGER_FILE.exists():
        try:
            with open(LEDGER_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.warning(f"cost_tracker: ledger file unreadable, starting fresh: {LEDGER_FILE}")
    return {"days": {}}


def _save(data: dict) -> None:
    LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = LEDGER_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    tmp.replace(LEDGER_FILE)


def estimate_cost(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    in_price, out_price = PRICING.get(f"{provider}/{model}", DEFAULT_PRICE)
    return (prompt_tokens / 1_000_000) * in_price + (completion_tokens / 1_000_000) * out_price


def record_usage(provider: str, model: str, prompt_tokens: int, completion_tokens: int,
                  job_id: str | None = None) -> float:
    """Append a usage record to today's ledger entry. Returns the estimated
    cost of this single call (USD)."""
    cost = estimate_cost(provider, model, prompt_tokens, completion_tokens)
    with _lock:
        data = _load()
        day = data["days"].setdefault(_today(), {"total_usd": 0.0, "calls": []})
        day["total_usd"] = round(day["total_usd"] + cost, 6)
        day["calls"].append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "provider": provider,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": round(cost, 6),
            "job_id": job_id,
        })
        _save(data)
    return cost


def get_daily_spend(day: str | None = None) -> float:
    data = _load()
    return data["days"].get(day or _today(), {}).get("total_usd", 0.0)


def get_summary(days: int = 7) -> dict:
    """Last N days of spend, most recent first — for the admin dashboard."""
    data = _load()
    all_days = sorted(data["days"].keys(), reverse=True)[:days]
    return {
        "daily_budget_usd": get_daily_budget(),
        "today_spend_usd": get_daily_spend(),
        "days": [{"date": d, "total_usd": data["days"][d]["total_usd"],
                   "call_count": len(data["days"][d]["calls"])} for d in all_days],
    }


def get_daily_budget() -> float:
    """0 (default) means unlimited — no ceiling enforced."""
    try:
        return float(os.environ.get("DAILY_AI_BUDGET_USD", "0") or "0")
    except ValueError:
        return 0.0


def check_budget() -> None:
    """Raise RuntimeError if today's spend has already reached the
    configured ceiling. Called before attempting a new AI call, not after —
    the call that would tip it over never gets a chance to run."""
    budget = get_daily_budget()
    if budget <= 0:
        return  # unlimited
    spent = get_daily_spend()
    if spent >= budget:
        raise RuntimeError(
            f"Daily AI budget exceeded (${spent:.4f} spent of ${budget:.4f} limit). "
            "Set DAILY_AI_BUDGET_USD higher in .env, or wait for the daily reset."
        )
