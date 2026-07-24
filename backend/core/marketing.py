"""AI Marketing Suite — generates Amazon listing, social media, press materials from book content."""
import json
from backend.core.ai import _try_providers
from backend.config import settings


def _book_summary(ebook_dict: dict) -> str:
    title = ebook_dict.get("title", "Untitled")
    author = ebook_dict.get("author", "Unknown")
    summary = ebook_dict.get("summary", "")
    chapters = ebook_dict.get("chapters", [])
    ch_info = "\n".join(
        f"- {ch.get('title', '')}: {ch.get('introduction', '')[:100]}"
        for ch in chapters[:5]
    )
    return f"Title: {title}\nAuthor: {author}\nSummary: {summary}\nChapters:\n{ch_info}"


def generate_amazon_listing(ebook_dict: dict) -> dict:
    summary = _book_summary(ebook_dict)
    system = "You are an expert Amazon KDP copywriter. Return only valid JSON."
    user = f"""Based on this book, create a complete Amazon KDP listing:

{summary}

Return JSON:
- title: optimized title (max 200 chars)
- subtitle: compelling subtitle
- description: compelling book description with hooks (max 4000 chars)
- author_bio: short author bio (max 500 chars)
- keywords: 7 Amazon search keywords (comma-separated)
- categories: 2 Amazon categories from Business & Money, Computers & Technology, Education & Reference, Health & Wellness, Self-Help, Science & Math, Arts & Photography
- target_audience: who is this book for
- price_suggestion: suggested USD price"""
    raw = _try_providers(system, user, preferred=settings.ai_provider)
    return json.loads(raw)


def generate_social_media(ebook_dict: dict) -> dict:
    summary = _book_summary(ebook_dict)
    system = "You are a social media marketing expert. Return only valid JSON."
    user = f"""Based on this book, create social media content:

{summary}

Return JSON:
- twitter: 4 tweets (max 280 chars each) as array
- linkedin: 2 long-form LinkedIn posts as array
- instagram: 3 Instagram captions with hashtags as array
- facebook: 2 Facebook posts as array"""
    raw = _try_providers(system, user, preferred=settings.ai_provider)
    return json.loads(raw)


def generate_press_release(ebook_dict: dict) -> dict:
    summary = _book_summary(ebook_dict)
    system = "You are a PR professional. Return only valid JSON."
    user = f"""Based on this book, create press materials:

{summary}

Return JSON:
- headline: press release headline
- body: full press release body (3-4 paragraphs)
- boilerplate: standard company/author boilerplate (2-3 sentences)
- talking_points: 5 key talking points as array
- hook: one-line hook for journalists"""
    raw = _try_providers(system, user, preferred=settings.ai_provider)
    return json.loads(raw)


def generate_email_sequence(ebook_dict: dict) -> dict:
    summary = _book_summary(ebook_dict)
    system = "You are an email marketing specialist. Return only valid JSON."
    user = f"""Based on this book, create a 5-email launch sequence:

{summary}

Return JSON:
- emails: array of 5 objects, each with:
  - subject: email subject line
  - preview: preview text
  - body: full email body (plain text, 100-200 words each)
- sequence_name: name for this sequence"""
    raw = _try_providers(system, user, preferred=settings.ai_provider)
    return json.loads(raw)


def generate_all_marketing(ebook_dict: dict) -> dict:
    return {
        "amazon_listing": generate_amazon_listing(ebook_dict),
        "social_media": generate_social_media(ebook_dict),
        "press_release": generate_press_release(ebook_dict),
        "email_sequence": generate_email_sequence(ebook_dict),
    }
