"""AI Proofreader — grammar check, originality check, and humanization."""
import json
from loguru import logger
from backend.core.ai import _try_providers


def grammar_check(text: str, provider: str | None = None) -> dict:
    """Run grammar and style check on a text passage."""
    system = "You are a professional proofreader. Return only valid JSON."
    user = f"""Proofread this text for grammar, spelling, punctuation, and style issues.

Return EXACTLY this JSON:
{{
  "issues": [
    {{"type": "grammar|spelling|style|punctuation", "original": "...", "suggestion": "...", "explanation": "..."}}
  ],
  "corrected_text": "The full text with all corrections applied",
  "score": 85,
  "summary": "Brief summary of issues found"
}}

Score is 0-100 where 100 is perfect. Be thorough.

TEXT:
{text[:8000]}"""

    try:
        raw = _try_providers(system, user, preferred=provider, max_tokens=8000)
        result = json.loads(raw) if isinstance(raw, str) else raw
        return result
    except Exception as e:
        logger.warning(f"Grammar check failed: {e}")
        return {
            "issues": [{"type": "error", "original": "", "suggestion": "", "explanation": f"Check failed: {e}"}],
            "corrected_text": text,
            "score": 0,
            "summary": f"Grammar check failed: {e}",
        }


def originality_check(text: str, provider: str | None = None) -> dict:
    """Check for AI-generated patterns and suggest humanization."""
    system = "You are an originality expert. Return only valid JSON."
    user = f"""Analyze this text for AI-generated writing patterns.

Return EXACTLY this JSON:
{{
  "ai_score": 75,
  "patterns_found": [
    {{"pattern": "Overly structured lists", "severity": "medium", "suggestion": "Vary sentence structure"}}
  ],
  "humanized_text": "The rewritten version that reads more naturally",
  "recommendations": ["Use more varied sentence lengths", "Add personal anecdotes"],
  "overall": "Brief overall assessment"
}}

AI_SCORE: 0 = clearly human, 100 = clearly AI. Be specific about which patterns you detect.

TEXT:
{text[:8000]}"""

    try:
        raw = _try_providers(system, user, preferred=provider, max_tokens=8000)
        result = json.loads(raw) if isinstance(raw, str) else raw
        return result
    except Exception as e:
        logger.warning(f"Originality check failed: {e}")
        return {
            "ai_score": 50,
            "patterns_found": [{"pattern": "Check failed", "severity": "low", "suggestion": ""}],
            "humanized_text": text,
            "recommendations": ["Could not complete analysis"],
            "overall": f"Originality check failed: {e}",
        }


def full_proofread(ebook_dict: dict, provider: str | None = None) -> dict:
    """Run grammar + originality check on all chapters in an ebook_dict."""
    chapters = ebook_dict.get("chapters", [])
    results = []
    total_grammar_score = 0
    total_ai_score = 0

    for i, ch in enumerate(chapters):
        title = ch.get("title", f"Chapter {i+1}")
        full_text = ch.get("introduction", "") + "\n"
        for sec in ch.get("sections", []):
            full_text += sec.get("content", "") + "\n"

        if not full_text.strip():
            continue

        grammar = grammar_check(full_text, provider)
        originality = originality_check(full_text, provider)

        corrected_text = grammar.get("corrected_text", full_text)
        humanized = originality.get("humanized_text", corrected_text)

        results.append({
            "chapter_index": i,
            "chapter_title": title,
            "grammar": {
                "issues": grammar.get("issues", []),
                "score": grammar.get("score", 0),
                "summary": grammar.get("summary", ""),
                "corrected_text": corrected_text,
            },
            "originality": {
                "ai_score": originality.get("ai_score", 50),
                "patterns": originality.get("patterns_found", []),
                "recommendations": originality.get("recommendations", []),
                "overall": originality.get("overall", ""),
                "humanized_text": humanized,
            },
        })
        total_grammar_score += grammar.get("score", 0)
        total_ai_score += originality.get("ai_score", 50)

    chapter_count = max(len(results), 1)
    return {
        "chapters": results,
        "overall": {
            "avg_grammar_score": round(total_grammar_score / chapter_count, 1),
            "avg_ai_score": round(total_ai_score / chapter_count, 1),
            "total_issues": sum(len(c["grammar"]["issues"]) for c in results),
            "total_patterns": sum(len(c["originality"]["patterns"]) for c in results),
            "grade": _grade(total_grammar_score / chapter_count, total_ai_score / chapter_count),
        },
    }


def _grade(grammar_score: float, ai_score: float) -> str:
    avg = (grammar_score + (100 - ai_score)) / 2
    if avg >= 90:
        return "A — Excellent"
    elif avg >= 80:
        return "B — Good"
    elif avg >= 70:
        return "C — Needs revision"
    elif avg >= 60:
        return "D — Needs significant revision"
    return "F — Requires rewrite"
