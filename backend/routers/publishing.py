"""Endpoints for AI Marketing Suite, Multi-language, Book Coach, Direct Publishing."""
import json
import os

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.core.beta_reader import beta_read
from backend.core.coach import process_answer, start_interview
from backend.core.format_checker import check_kdp_requirements
from backend.core.jobs import get_job
from backend.core.launch_page import generate_launch_page
from backend.core.marketing import generate_all_marketing
from backend.core.moderation import check_content
from backend.core.proofreader import full_proofread, grammar_check, originality_check
from backend.core.publish_prep import PREPARERS
from backend.core.publish_validators import validate_apple_books, validate_epub, validate_kdp, validate_metadata
from backend.core.publisher import (
    generate_google_play_metadata,
    generate_kdp_metadata,
    generate_onix_metadata,
    generate_polish_metadata,
    get_platforms,
)
from backend.core.translator import SUPPORTED_LANGUAGES, translate_book
from backend.limiter import limiter
from backend.routers.auth import require_admin

router = APIRouter()

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", settings.output_dir)
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ─── Marketing Suite ────────────────────────────────────────────────
@router.post("/api/marketing/generate/{job_id}", dependencies=[Depends(require_admin)])
@limiter.limit("10/minute")
def api_generate_marketing(request: Request, job_id: str):
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job["status"] != "done":
        return JSONResponse({"error": "Job not ready"}, status_code=400)
    ebook_dict = {
        "title": job.get("topic", "Book"),
        "author": "AI Design Engine",
        "summary": job.get("topic", ""),
        "chapters": [],
    }
    try:
        return generate_all_marketing(ebook_dict)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── Multi-language Publishing ──────────────────────────────────────
@router.get("/api/languages")
@limiter.limit("60/minute")
def api_languages(request: Request):
    return [{"code": k, "name": v} for k, v in SUPPORTED_LANGUAGES.items()]


@router.post("/api/translate/{job_id}", dependencies=[Depends(require_admin)])
@limiter.limit("5/minute")
async def api_translate(request: Request, job_id: str, languages: str = "pl,de,fr,es"):
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job["status"] != "done":
        return JSONResponse({"error": "Job not ready"}, status_code=400)

    target_codes = [lang.strip() for lang in languages.split(",") if lang.strip()]
    invalid = [c for c in target_codes if c not in SUPPORTED_LANGUAGES]
    if invalid:
        return JSONResponse({"error": f"Invalid language codes: {', '.join(invalid)}"}, status_code=400)

    results = []
    for lang in target_codes[:5]:  # max 5 per request
        try:
            from backend.core.builder import build_ebook_html

            ebook_dict = {
                "title": job.get("topic", "Book"),
                "author": "AI Design Engine",
                "summary": job.get("topic", ""),
                "chapters": [],
            }
            translated = translate_book(ebook_dict, lang)
            translated_path = os.path.join(OUTPUT_DIR, f"{job_id}_{lang}.html")
            html = build_ebook_html(translated, job.get("style", "minimal"), [])
            with open(translated_path, "w", encoding="utf-8") as f:
                f.write(html)
            results.append({
                "language": lang,
                "name": SUPPORTED_LANGUAGES[lang],
                "path": translated_path,
                "size": os.path.getsize(translated_path),
            })
        except Exception as e:
            results.append({"language": lang, "name": SUPPORTED_LANGUAGES.get(lang, lang), "error": str(e)})
    return {"job_id": job_id, "translations": results}


# ─── Book Coach ─────────────────────────────────────────────────────
_coach_sessions = {}


@router.post("/api/coach/start", dependencies=[Depends(require_admin)])
@limiter.limit("10/minute")
def api_coach_start(request: Request):
    session = start_interview()
    _coach_sessions[session["session_id"]] = session
    return session


@router.post("/api/coach/answer", dependencies=[Depends(require_admin)])
@limiter.limit("20/minute")
def api_coach_answer(request: Request, session_id: str, answer: str = Query(..., max_length=2000)):
    session = _coach_sessions.get(session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    rejection = check_content(answer)
    if rejection:
        return JSONResponse({"error": rejection}, status_code=400)
    session = process_answer(session, answer)
    _coach_sessions[session_id] = session
    return session


@router.get("/api/coach/session/{session_id}")
@limiter.limit("60/minute")
def api_coach_session(request: Request, session_id: str):
    session = _coach_sessions.get(session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    return session


# ─── Direct Publishing ──────────────────────────────────────────────
@router.get("/api/publish/platforms")
@limiter.limit("60/minute")
def api_platforms(request: Request):
    return get_platforms()


@router.post("/api/publish/metadata/{job_id}", dependencies=[Depends(require_admin)])
@limiter.limit("30/minute")
def api_generate_metadata(request: Request, job_id: str):
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job["status"] != "done":
        return JSONResponse({"error": "Job not ready"}, status_code=400)
    ebook_dict = {
        "title": job.get("topic", "Book"),
        "author": "AI Design Engine",
        "summary": job.get("topic", ""),
    }
    return {
        "onix": generate_onix_metadata(ebook_dict),
        "kdp": generate_kdp_metadata(ebook_dict),
        "google_play": generate_google_play_metadata(ebook_dict),
        "polish": generate_polish_metadata(ebook_dict),
    }


def _job_metadata(job: dict) -> dict:
    """Build a platform-metadata dict from a finished job's book_data."""
    book_data = job.get("book_data")
    if isinstance(book_data, str):
        try:
            book_data = json.loads(book_data)
        except (TypeError, ValueError):
            book_data = {}
    book_data = book_data or {}
    return {
        "title": book_data.get("title") or job.get("topic", "Book"),
        "author": book_data.get("author") or "AI Design Engine",
        "description": book_data.get("summary", ""),
        "language": book_data.get("language", "pl"),
        "keywords": book_data.get("keywords", []),
        "category": book_data.get("category", ""),
        "isbn": book_data.get("isbn", ""),
        "publicationDate": book_data.get("publicationDate", ""),
    }


# ─── Platform compliance validators (ported from Kiro eBook Studio) ──
@router.get("/api/publish/validate/{job_id}")
@limiter.limit("30/minute")
def api_publish_validate(request: Request, job_id: str, platform: str = "metadata", cover_path: str = None):  # noqa: PLR0911
    """Validate a job's outputs against a store's technical requirements.
    One return per platform branch is the clearest shape for a simple dispatcher; splitting
    it up to satisfy the 6-return limit would add indirection for no real readability gain.

    platform: metadata | amazon-kdp | apple-books | epub
    """
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)

    metadata = _job_metadata(job)
    try:
        if platform == "metadata":
            return validate_metadata(metadata)
        if platform == "amazon-kdp":
            return validate_kdp(metadata, cover_path=cover_path, epub_path=job.get("epub_path"), pdf_path=job.get("output_path"))
        if platform == "apple-books":
            return validate_apple_books(metadata, cover_path=cover_path, epub_path=job.get("epub_path"))
        if platform == "epub":
            return validate_epub(job.get("epub_path"))
        return JSONResponse({"error": f"Unknown platform: {platform}"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── Platform packaging (ported from Kiro eBook Studio) ──────────────
@router.post("/api/publish/prepare/{job_id}", dependencies=[Depends(require_admin)])
@limiter.limit("20/minute")
def api_publish_prepare(request: Request, job_id: str, platform: str, cover_path: str = None):
    """Prepare a store-ready package: copies EPUB/PDF, resizes the cover to
    the store's required dimensions, writes metadata + validation JSON.

    platform: amazon-kdp | apple-books | kobo | google-play
    """
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job["status"] != "done":
        return JSONResponse({"error": "Job not ready"}, status_code=400)

    preparer = PREPARERS.get(platform)
    if not preparer:
        return JSONResponse({"error": f"Unknown platform: {platform}. Use one of: {', '.join(PREPARERS)}"}, status_code=400)

    metadata = _job_metadata(job)
    output_dir = os.path.join(OUTPUT_DIR, "platforms", platform, job_id)
    kwargs = {"epub_path": job.get("epub_path"), "cover_path": cover_path}
    if platform in ("amazon-kdp", "google-play"):
        kwargs["pdf_path"] = job.get("output_path")

    try:
        return preparer(metadata, output_dir, **kwargs)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── AI Proofreader ──────────────────────────────────────────────────
@router.post("/api/proofread/{job_id}", dependencies=[Depends(require_admin)])
@limiter.limit("10/minute")
def api_proofread(request: Request, job_id: str, provider: str = None):
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job["status"] != "done":
        return JSONResponse({"error": "Job not ready"}, status_code=400)

    book_data = job.get("book_data")
    if not book_data:
        return JSONResponse({"error": "No book data available. Generate a book first."}, status_code=400)
    if isinstance(book_data, str):
        book_data = json.loads(book_data)

    try:
        result = full_proofread(book_data, provider)
        return result
    except Exception as e:
        return JSONResponse({"error": f"Proofread failed: {e}"}, status_code=500)


@router.post("/api/proofread/{job_id}/chapter/{chapter_index}", dependencies=[Depends(require_admin)])
@limiter.limit("20/minute")
def api_proofread_chapter(request: Request, job_id: str, chapter_index: int, provider: str = None):
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job["status"] != "done":
        return JSONResponse({"error": "Job not ready"}, status_code=400)

    book_data = job.get("book_data")
    if not book_data:
        return JSONResponse({"error": "No book data"}, status_code=400)
    if isinstance(book_data, str):
        book_data = json.loads(book_data)

    chapters = book_data.get("chapters", [])
    if chapter_index < 0 or chapter_index >= len(chapters):
        return JSONResponse({"error": f"Chapter {chapter_index} not found"}, status_code=404)

    ch = chapters[chapter_index]
    full_text = ch.get("introduction", "") + "\n"
    for sec in ch.get("sections", []):
        full_text += sec.get("content", "") + "\n"

    try:
        return {
            "chapter_index": chapter_index,
            "chapter_title": ch.get("title", f"Chapter {chapter_index+1}"),
            "grammar": grammar_check(full_text, provider),
            "originality": originality_check(full_text, provider),
        }
    except Exception as e:
        return JSONResponse({"error": f"Proofread failed: {e}"}, status_code=500)


# ─── AI Beta Reader ──────────────────────────────────────────────────
@router.post("/api/beta-read/{job_id}", dependencies=[Depends(require_admin)])
@limiter.limit("10/minute")
def api_beta_read(request: Request, job_id: str, provider: str = None):
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    book_data = job.get("book_data")
    if not book_data:
        return JSONResponse({"error": "No book data available"}, status_code=400)
    if isinstance(book_data, str):
        book_data = json.loads(book_data)
    try:
        return beta_read(book_data, provider)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── KDP Format Checker ─────────────────────────────────────────────
@router.get("/api/format-check/{job_id}")
@limiter.limit("30/minute")
def api_format_check(request: Request, job_id: str, platform: str = "kdp"):
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    html = job.get("html", "")
    if not html:
        return JSONResponse({"error": "No HTML content"}, status_code=400)
    try:
        return check_kdp_requirements(html, platform)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── Book Launch Page ───────────────────────────────────────────────
@router.post("/api/launch-page/{job_id}", dependencies=[Depends(require_admin)])
@limiter.limit("30/minute")
def api_launch_page(request: Request, job_id: str, launch_date: str = None, accent_color: str = "#6366F1"):
    from fastapi.responses import HTMLResponse
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    book_data = job.get("book_data")
    if isinstance(book_data, str):
        book_data = json.loads(book_data)
    if not book_data:
        book_data = {"title": job.get("topic", "Book"), "author": "AI Design Engine", "summary": ""}
    try:
        html = generate_launch_page(book_data, launch_date, accent_color, job_id)
        return HTMLResponse(content=html)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
