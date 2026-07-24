"""AI Beta Reader — simulates 5 reader personas giving chapter-by-chapter feedback."""
import json

from loguru import logger

from backend.core.ai import _try_providers

READER_PERSONAS = [
    {
        "id": "casual",
        "name": "Casual Reader",
        "description": "Reads for pleasure, short attention span, wants to be entertained",
    },
    {
        "id": "expert",
        "name": "Subject Expert",
        "description": "Knows the topic well, checks for accuracy and depth",
    },
    {
        "id": "beginner",
        "name": "Complete Beginner",
        "description": "New to the topic, needs clear explanations, patience for basics",
    },
    {
        "id": "critic",
        "name": "Harsh Critic",
        "description": "Hard to impress, points out every flaw, compares to bestsellers",
    },
    {
        "id": "editor",
        "name": "Professional Editor",
        "description": "Focuses on structure, pacing, clarity, marketability",
    },
]


def beta_read(ebook_dict: dict, provider: str | None = None) -> dict:
    """Run all 5 reader personas on the full book."""
    title = ebook_dict.get("title", "Untitled")
    chapters = ebook_dict.get("chapters", [])
    book_text = f"Title: {title}\n\n"
    for i, ch in enumerate(chapters):
        book_text += f"Chapter {i+1}: {ch.get('title', '')}\n"
        book_text += f"Introduction: {ch.get('introduction', '')}\n"
        for sec in ch.get("sections", []):
            book_text += f"  {sec.get('heading', '')}: {sec.get('content', '')[:200]}\n"

    results = []
    for persona in READER_PERSONAS:
        try:
            feedback = _read_as_persona(persona, book_text, provider)
            results.append({
                "persona": persona["id"],
                "persona_name": persona["name"],
                **feedback,
            })
        except Exception as e:
            logger.warning(f"Beta reader {persona['id']} failed: {e}")
            results.append({
                "persona": persona["id"],
                "persona_name": persona["name"],
                "error": str(e),
            })

    # Generate overall summary
    summary = _generate_summary(results, title, provider) if results else {}
    return {"readers": results, "summary": summary}


def _read_as_persona(persona: dict, book_text: str, provider: str | None) -> dict:
    system = f"""You are {persona['name']}. {persona['description']}.

Read the following book excerpt and provide detailed feedback as this specific type of reader.
Return ONLY valid JSON with this exact structure:
{{
  "overall_rating": 1-5,
  "would_finish": true/false,
  "recommend_to_friend": true/false,
  "strengths": ["..."],
  "weaknesses": ["..."],
  "pacing_rating": "too_slow|balanced|too_fast",
  "clarity_rating": 1-5,
  "engagement_rating": 1-5,
  "specific_notes": "...",
  "target_audience_match": "...",
  "improvement_suggestions": ["..."]
}}"""
    raw = _try_providers(system, f"BOOK:\n\n{book_text[:6000]}", preferred=provider, max_tokens=4000)
    return json.loads(raw) if isinstance(raw, str) else raw or {}


def _generate_summary(results: list, title: str, provider: str | None) -> dict:
    ratings = [r.get("overall_rating", 0) for r in results if "overall_rating" in r]
    avg = sum(ratings) / len(ratings) if ratings else 0
    finish = sum(1 for r in results if r.get("would_finish"))
    recommend = sum(1 for r in results if r.get("recommend_to_friend"))

    all_weaknesses = []
    for r in results:
        all_weaknesses.extend(r.get("weaknesses", []))

    return {
        "avg_rating": round(avg, 1),
        "would_finish": f"{finish}/{len(results)}",
        "would_recommend": f"{recommend}/{len(results)}",
        "top_weaknesses": all_weaknesses[:5],
    }
