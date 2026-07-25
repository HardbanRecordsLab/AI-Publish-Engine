import json
import os
import re
import threading
import time

from loguru import logger
from openai import APIError, RateLimitError, Timeout
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.config import settings
from backend.core import cost_tracker
from backend.core.tokens import generate_design_system as _token_design_system

# ============================================================
# PROVIDER REGISTRY
# ============================================================
PROVIDERS = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.0-flash-001",
        "api_key_env": "GEMINI_API_KEY",
        "site": "aistudio.google.com/apikey",
        "priority": 2,
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        # llama-3.1-8b-instant has a much higher free-tier rate limit (RPM/TPM)
        # than llama-3.3-70b-versatile. Override per-call with GROQ_MODEL in
        # .env if you want the bigger model back (e.g. for final polish runs).
        "model": "llama-3.1-8b-instant",
        "api_key_env": "GROQ_API_KEY",
        "site": "console.groq.com/keys",
        "priority": 2,
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "qwen/qwen-2.5-72b-instruct",
        "api_key_env": "OPENROUTER_API_KEY",
        "site": "openrouter.ai/keys",
        "priority": 3,
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "model": "mistral-small-latest",
        "api_key_env": "MISTRAL_API_KEY",
        "site": "console.mistral.ai",
        "priority": 4,
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
        "site": "platform.openai.com/api-keys",
        "priority": 5,
    },
    "cohere": {
        "base_url": "https://api.cohere.ai/v1",
        "model": "command-r-plus",
        "api_key_env": "COHERE_API_KEY",
        "site": "dashboard.cohere.com",
        "priority": 6,
    },
    "claude": {
        "base_url": "https://api.anthropic.com/v1",
        "model": "claude-sonnet-4-20250514",
        "api_key_env": "ANTHROPIC_API_KEY",
        "site": "console.anthropic.com",
        "priority": 1,
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "api_key_env": "DEEPSEEK_API_KEY",
        "site": "platform.deepseek.com",
        "priority": 3,
    },
}


def _get_api_key(name: str) -> str:
    key = os.getenv(PROVIDERS[name]["api_key_env"]) or ""
    return key


def _client(name: str):
    from openai import OpenAI
    cfg = PROVIDERS[name]
    key = _get_api_key(name)
    if not key:
        return None
    return OpenAI(api_key=key, base_url=cfg["base_url"])


def _model(name: str):
    # Per-provider override (e.g. GROQ_MODEL=llama-3.3-70b-versatile) takes
    # priority over the old global AI_MODEL, which used to leak into every
    # provider at once (setting AI_MODEL for Groq would also silently
    # override Gemini/OpenRouter/etc). Global AI_MODEL is kept as a last
    # resort fallback for backwards compatibility.
    provider_env = f"{name.upper()}_MODEL"
    return os.getenv(provider_env) or os.getenv("AI_MODEL") or PROVIDERS[name]["model"]


def _build_provider_order(preferred: str | None) -> list[str]:
    p = preferred or settings.ai_provider
    order = []
    seen = set()
    if p in PROVIDERS:
        order.append(p)
        seen.add(p)
    for name in sorted(PROVIDERS, key=lambda n: PROVIDERS[n]["priority"]):
        if name not in seen:
            order.append(name)
    return order


# ============================================================
# THROTTLING
# ============================================================
# Simple per-provider minimum-interval limiter so a burst of jobs (e.g. Batch
# Factory) doesn't blow through free-tier rate limits in a few seconds. This
# doesn't guarantee you'll never hit a 429 (server-side limits can be more
# complex than "N seconds between calls"), but it smooths out the obvious
# self-inflicted bursts. Tune via *_MIN_INTERVAL_SECONDS in .env if needed.
_last_call_at: dict[str, float] = {}
_throttle_lock = threading.Lock()

_DEFAULT_MIN_INTERVAL = {
    "groq": 2.0,
    "gemini": 1.0,
    "openrouter": 1.5,
    "mistral": 1.5,
    "openai": 0.5,
    "claude": 1.0,
    "deepseek": 1.5,
    "cohere": 1.5,
}


def _throttle(name: str):
    min_interval = float(os.getenv(f"{name.upper()}_MIN_INTERVAL_SECONDS", _DEFAULT_MIN_INTERVAL.get(name, 1.0)))
    if min_interval <= 0:
        return
    with _throttle_lock:
        now = time.monotonic()
        last = _last_call_at.get(name, 0.0)
        wait = min_interval - (now - last)
        if wait > 0:
            _last_call_at[name] = last + min_interval
        else:
            _last_call_at[name] = now
    if wait > 0:
        logger.debug(f"{name}: throttling {wait:.1f}s before next call")
        time.sleep(wait)


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((RateLimitError, Timeout, APIError)),
    before_sleep=lambda retry_state: logger.warning(f"Retry #{retry_state.attempt_number} after {retry_state.outcome.exception()}"),
)
def _call(name: str, messages: list[dict], max_tokens: int = 6000) -> str | None:
    client = _client(name)
    if not client:
        logger.debug(f"{name}: no API key, skipping")
        return None
    _throttle(name)
    model = _model(name)
    logger.info(f"AI call: {name}/{model}")
    res = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.1,
        max_tokens=max_tokens,
        timeout=60,
    )
    content = res.choices[0].message.content
    logger.success(f"AI OK: {name}/{model} ({len(content)} chars)")
    try:
        usage = getattr(res, "usage", None)
        if usage:
            cost = cost_tracker.record_usage(
                name, model,
                prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            )
            logger.debug(f"{name}/{model}: ~${cost:.5f} this call, ${cost_tracker.get_daily_spend():.4f} today")
    except Exception as e:
        # Cost tracking must never break a successful AI call.
        logger.warning(f"cost_tracker: failed to record usage for {name}/{model}: {e}")
    return content


def _try_providers(system: str, user: str, preferred: str | None = None, max_tokens: int = 6000) -> str:
    cost_tracker.check_budget()  # raises RuntimeError if today's spend already hit the ceiling
    order = _build_provider_order(preferred)
    last_error = None
    for name in order:
        try:
            result = _call(name, [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ], max_tokens=max_tokens)
            if result:
                return result
        except Exception as e:
            logger.warning(f"{name} failed: {e}")
            last_error = e
    raise RuntimeError(f"All providers failed. Last: {last_error}")


def _clean_json(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw, flags=re.IGNORECASE)

    # Find the outermost balanced JSON object (handles nested braces)
    brace_count = 0
    start = -1
    in_string = False
    escape = False
    for i, ch in enumerate(raw):
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            if brace_count == 0:
                start = i
            brace_count += 1
        elif ch == '}':
            if brace_count > 0:
                brace_count -= 1
                if brace_count == 0 and start != -1:
                    candidate = raw[start:i+1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        pass
    raise ValueError("No valid JSON found in AI response")


def _extract_json_array(raw: str) -> list:
    raw = raw.strip()
    if raw.startswith("["):
        return json.loads(raw)
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if match:
        return json.loads(match.group())
    return []


# ============================================================
# PUBLIC API
# ============================================================

def analyze_text(text: str, provider: str | None = None) -> dict:
    trunc = text[:10000]
    system = "You are an ebook author. Return only valid JSON. Your response must start with { and end with }."
    user = f"""Transform this raw text into a structured ebook JSON.

Return EXACTLY this JSON structure, nothing else:

{{
  "title": "...",
  "subtitle": "...",
  "author": "AI Ebook Builder",
  "topic": "technology",
  "tone": "professional",
  "audience": "...",
  "summary": "...",
  "chapters": [
    {{
      "title": "...",
      "introduction": "...",
      "key_takeaway": "...",
      "sections": [
        {{"heading": "...", "content": "..."}}
      ]
    }}
  ],
  "conclusion": {{"title": "...", "content": "..."}}
}}

RULES:
- 4-6 chapters, 3-4 sections each
- Topic must be one: technology|finance|health|education|marketing|psychology|survival|business|general
- Your ENTIRE response must be ONLY valid JSON, starting with {{ and ending with }}
- NO markdown, NO backticks, NO explanations

SOURCE:
{trunc}"""

    # Try primary provider first
    try:
        raw = _try_providers(system, user, preferred=provider)
        return _clean_json(raw)
    except ValueError:
        logger.warning("analyze_text: first attempt failed JSON extraction, retrying with stricter prompt")
        strict_system = "CRITICAL: Respond with ONLY a raw JSON object. No markdown, no backticks, no explanations. Start with { and end with }."
        strict_user = f"""Convert this to JSON ebook. Respond with ONLY the JSON object:

{trunc[:5000]}"""
        # Force a different provider on retry (skip preferred to avoid same failure)
        raw = _try_providers(strict_system, strict_user, preferred=None)
        result = _clean_json(raw)
        logger.success("analyze_text: recovered on retry")
        return result


def generate_design_system(style: str, tone: str) -> dict:
    return _token_design_system(style, tone)


def plan_infographics(analysis: dict, design: dict, provider: str | None = None) -> list:
    chapters = analysis.get("chapters", [])
    chapter_summary = "\n".join(
        f"Ch{i+1}: {c['title']}" for i, c in enumerate(chapters) if c.get("title")
    )
    system = "You are an infographic designer. Return only valid JSON arrays."
    user = f"""Based on this ebook, plan powerful visuals.

EBOOK: {analysis.get('title', '')}
TOPIC: {analysis.get('topic', 'general')}
CHAPTERS:
{chapter_summary}
STYLE: {design.get('vibe', 'professional')}

Return a JSON array of infographic plans:

[
  {{
    "type": "timeline | process | comparison | list | hierarchy",
    "chapter_index": 0,
    "section_index": 0,
    "title": "Clear diagram title",
    "description": "What this shows and why it matters",
    "data_points": ["1956: First AI", "1997: Deep Blue", "2022: ChatGPT", "2026: AGI"]
  }}
]

RULES:
- 3-5 infographics across chapters
- data_points: 3-6 descriptive items each
- Types: timeline (dates), process (steps), comparison (pairs), list (items), hierarchy (levels)
- Only JSON array, no markdown"""

    raw = _try_providers(system, user, preferred=provider, max_tokens=3000)
    return _extract_json_array(raw)


# ============================================================
# NEW AGENT FUNCTIONS — Phase 2
# ============================================================

def research_content(analysis: dict, provider: str | None = None) -> dict:
    """Research Agent: suggest sources, examples, and expansion ideas."""
    chapters = analysis.get("chapters", [])
    chapter_lines = "\n".join(
        f"Ch{i+1}: {c.get('title', '')}"
        for i, c in enumerate(chapters)
    )
    system = "You are a research assistant. Return only valid JSON."
    user = f"""Given this ebook outline, provide specific research suggestions per chapter.

EBOOK: {analysis.get('title', '')}
TOPIC: {analysis.get('topic', 'general')}
AUDIENCE: {analysis.get('audience', '')}
CHAPTERS:
{chapter_lines}

Return JSON:
{{
  "chapters": [
    {{
      "index": 0,
      "title": "Chapter title",
      "suggestions": {{
        "sources": ["Source/Reference 1", "Source/Reference 2"],
        "examples": ["Concrete example 1", "Case study 2"],
        "ideas": ["Expansion idea 1", "Sidebar concept"]
      }}
    }}
  ],
  "overall_suggestions": {{
    "additional_sources": ["Global source 1"],
    "cross_references": ["Topic A relates to Chapter X"],
    "gaps": ["Potential missing topic"]
  }}
}}

RULES:
- 2-3 sources per chapter (real books, papers, reputable sites)
- 1-2 concrete examples per chapter
- 1-2 expansion ideas per chapter
- Only JSON, no markdown"""

    raw = _try_providers(system, user, preferred=provider, max_tokens=4000)
    return _clean_json(raw)


def editorial_rewrite_chapter(chapter: dict, research_suggestions: dict | None = None,
                              provider: str | None = None) -> dict:
    """Editorial Agent: improve a single chapter's writing quality."""
    research_context = ""
    if research_suggestions and research_suggestions.get("suggestions"):
        r = research_suggestions["suggestions"]
        sources = r.get("sources", [])
        examples = r.get("examples", [])
        ideas = r.get("ideas", [])
        if sources or examples or ideas:
            research_context = "\nRESEARCH FOR THIS CHAPTER:\n"
            if sources:
                research_context += "Sources: " + "; ".join(sources) + "\n"
            if examples:
                research_context += "Examples: " + "; ".join(examples) + "\n"
            if ideas:
                research_context += "Ideas: " + "; ".join(ideas) + "\n"

    import json
    chapter_json = json.dumps(chapter, indent=2)
    system = "You are a professional book editor. Return only valid JSON."
    user = f"""Improve this ebook chapter. Focus on: grammar, flow, transitions, tone consistency, clarity.

IMPORTANT: Return the EXACT same JSON structure. Keep all fields.
Only improve "content" fields. Do not change titles unless clearly wrong.
Do not add new factual information. Preserve all existing content, just improve the writing.{research_context}

CHAPTER TO EDIT:
{chapter_json}

Return the edited chapter as JSON with identical structure."""

    raw = _try_providers(system, user, preferred=provider, max_tokens=4000)
    return _clean_json(raw)


def fact_check(analysis: dict, provider: str | None = None) -> list:
    """FactCheck Agent: identify contradictions, unsubstantiated claims, errors."""
    # Build a condensed version for the prompt
    cond = f"Title: {analysis.get('title', '')}\nTopic: {analysis.get('topic', '')}\n"
    for i, ch in enumerate(analysis.get("chapters", [])):
        cond += f"\nCh{i}: {ch.get('title', '')}\n"
        for si, sec in enumerate(ch.get("sections", [])):
            content = sec.get("content", "")
            cond += f"  Sec{si}: {content[:300]}\n"

    system = "You are a fact-checker. Return only valid JSON arrays."
    user = f"""Review this ebook for issues. Identify:

1. INTERNAL CONTRADICTIONS — different statements that conflict
2. UNSUBSTANTIATED CLAIMS — strong assertions without evidence
3. POTENTIAL ERRORS — likely factual mistakes
4. LOGICAL INCONSISTENCIES — arguments that don't follow

EBOOK:
{cond[:8000]}

Return a JSON array:
[
  {{
    "chapter_index": 0,
    "section_index": null,
    "issue_type": "contradiction | unsubstantiated | error | inconsistency",
    "issue": "Clear description of the problem",
    "severity": "high | medium | low",
    "suggestion": "How to address this"
  }}
]

RULES:
- If no issues found, return empty array []
- Be conservative — only flag clear problems
- Only JSON array, no markdown"""

    raw = _try_providers(system, user, preferred=provider, max_tokens=3000)
    return _extract_json_array(raw)


def qa_check(analysis: dict, design: dict, html_summary: str = "",
             provider: str | None = None) -> dict:
    """QA Agent: final quality assessment of the rendered content."""
    chapters = analysis.get("chapters", [])
    ch_info = "\n".join(
        f"Ch{i+1}: {c.get('title', '')} ({len(c.get('sections', []))} sections, "
        f"{sum(len(s.get('content', '')) for s in c.get('sections', []))} chars)"
        for i, c in enumerate(chapters)
    )
    theme_name = design.get("theme", "unknown") if design else "unknown"

    system = "You are a QA specialist for digital publishing. Return only valid JSON."
    user = f"""Review this ebook for quality issues.

TITLE: {analysis.get('title', '')}
TOPIC: {analysis.get('topic', '')}
THEME: {theme_name}
CHAPTERS:
{ch_info}

Return JSON:
{{
  "issues": [
    {{
      "type": "typography | layout | content | structure | contrast",
      "severity": "high | medium | low",
      "description": "What needs attention",
      "location": "Where in the document"
    }}
  ],
  "score": 85,
  "summary": "Overall quality assessment (2-3 sentences)",
  "passed": true
}}

RULES:
- Score 0-100, passed=true if score >= 70
- List real issues visible from the metadata above
- If content looks solid, return empty issues array with high score
- Only JSON, no markdown"""

    raw = _try_providers(system, user, preferred=provider, max_tokens=2000)
    return _clean_json(raw)


def structure_chapter(chapter: dict, chapter_index: int,
                      provider: str | None = None) -> dict:
    """Structure Agent: enhance a chapter with summary, FAQ, checklist, section types."""
    import json
    sections_text = ""
    for si, sec in enumerate(chapter.get("sections", [])):
        content = sec.get("content", "")
        sections_text += f"\n  Section {si}: {sec.get('heading', '')}\n    {content[:500]}"

    ch_json = json.dumps({
        "title": chapter.get("title", ""),
        "introduction": chapter.get("introduction", ""),
        "sections": [{"heading": s.get("heading", ""), "content": s.get("content", "")[:300]} for s in chapter.get("sections", [])],
    }, indent=2)

    system = "You are a book architect. Return only valid JSON."
    user = f"""Review this chapter and enhance it with structural elements.

CHAPTER {chapter_index + 1}: {chapter.get('title', '')}
{ch_json}

Return JSON with these optional fields:
{{
  "chapter_summary": {{
    "title": "Chapter Summary",
    "points": ["Key takeaway 1", "Key takeaway 2"]
  }},
  "faq": [
    {{"question": "Common question?", "answer": "Clear answer"}}
  ],
  "checklist": {{
    "title": "Action Checklist",
    "items": [{{"text": "Action step 1", "checked": false}}]
  }}
}}

RULES:
- chapter_summary: 2-3 bullet highlights. ALWAYS include.
- faq: 0-2 Q&A pairs. Skip for simple non-technical chapters.
- checklist: 3-5 action items. Include for chapters with practical advice.
- Omit fields that don't apply (null, not empty array).
- Only JSON, no markdown."""

    raw = _try_providers(system, user, preferred=provider, max_tokens=3000)
    return _clean_json(raw)


def generate_ebook_sections(ebook_dict: dict, style: str,
                            provider: str | None = None) -> dict:
    """Finalization Agent: generate introduction, author bio, references, glossary, back cover."""
    chapters = ebook_dict.get("chapters", [])
    ch_titles = "\n".join(
        f"  Ch{i+1}: {c.get('title', '')} — {c.get('introduction', '')[:100]}"
        for i, c in enumerate(chapters)
    )
    system = "You are a book publishing specialist. Return only valid JSON."
    user = f"""Generate final sections for this ebook.

TITLE: {ebook_dict.get('title', '')}
SUMMARY: {ebook_dict.get('summary', '')[:300]}
TOPIC: {ebook_dict.get('topic', '')}
AUTHOR: {ebook_dict.get('author', 'AI Design Engine')}
CHAPTERS:
{ch_titles}
STYLE: {style}

Return JSON:
{{
  "introduction": "A compelling foreword/introduction (2-3 paragraphs) that hooks the reader and sets context for the book. Written in the book's tone.",
  "author_bio": "A professional author biography (2-3 sentences) for the author.",
  "references": [
    "Reference 1 — Author, Title, Publisher, Year",
    "Reference 2 — Author, Title, Publisher, Year"
  ],
  "glossary_terms": [
    {{"term": "Keyword", "definition": "Brief definition relevant to this book's topic"}}
  ],
  "back_cover_blurb": "A marketing blurb (2-3 sentences) selling the book to potential readers",
  "back_cover_tagline": "A short tagline (5-8 words) for the back cover"
}}

RULES:
- introduction: compelling, matches the book's tone, 200-400 words
- author_bio: professional, mentions expertise, 2-3 sentences
- references: 3-5 real-looking references relevant to the topic
- glossary_terms: 5-8 key terms with definitions
- back_cover_blurb: persuasive, benefit-focused, 2-3 sentences
- back_cover_tagline: short and memorable
- Only JSON, no markdown"""

    raw = _try_providers(system, user, preferred=provider, max_tokens=3000)
    return _clean_json(raw)
