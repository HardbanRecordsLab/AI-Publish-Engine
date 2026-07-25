"""WYSIWYG Chapter Editor — get/save edited chapters and rebuild HTML."""
import json

from fastapi import APIRouter, HTTPException, Request
from loguru import logger
from pydantic import BaseModel, Field

from backend.core.builder import build_ebook_html
from backend.core.jobs import get_job, update_job
from backend.core.prompt_safety import sanitize_text
from backend.limiter import limiter

router = APIRouter()


class EditedSection(BaseModel):
    index: int
    heading: str = Field("", max_length=500)
    content: str = Field("", max_length=20000)


class EditedChapter(BaseModel):
    index: int
    title: str = Field("", max_length=500)
    introduction: str = Field("", max_length=5000)
    sections: list[EditedSection] = Field(default_factory=list)


class SaveChaptersRequest(BaseModel):
    chapters: list[EditedChapter]


@router.get("/api/editor/{job_id}/chapters")
@limiter.limit("60/minute")
def get_chapters(request: Request, job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] != "done":
        raise HTTPException(400, "Job not ready yet")
    book_data = job.get("book_data")
    if not book_data:
        raise HTTPException(404, "No book data available for this job")
    if isinstance(book_data, str):
        book_data = json.loads(book_data)
    chapters = book_data.get("chapters", [])
    result = []
    for i, ch in enumerate(chapters):
        sections = ch.get("sections", [])
        result.append({
            "index": i,
            "title": ch.get("title", f"Chapter {i+1}"),
            "introduction": ch.get("introduction", ""),
            "sections": [
                {"index": si, "heading": s.get("heading", ""), "content": s.get("content", "")}
                for si, s in enumerate(sections)
            ],
        })
    return {
        "job_id": job_id,
        "title": book_data.get("title", "Untitled"),
        "author": book_data.get("author", ""),
        "chapters": result,
    }


@router.put("/api/editor/{job_id}/chapters")
@limiter.limit("20/minute")
def save_chapters(request: Request, job_id: str, body: SaveChaptersRequest):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] != "done":
        raise HTTPException(400, "Job not ready yet")

    edited_chapters = body.chapters
    if not edited_chapters:
        raise HTTPException(400, "No chapters provided")

    book_data = job.get("book_data")
    if isinstance(book_data, str):
        book_data = json.loads(book_data)

    build_params = job.get("build_params")
    if isinstance(build_params, str):
        build_params = json.loads(build_params)

    # Merge edited chapters into book_data. Field lengths are already capped
    # by SaveChaptersRequest; sanitize_text() additionally strips control
    # characters before this text can re-enter a prompt (proofread/
    # translate/marketing) or get persisted.
    ch_map = {c.index: c for c in edited_chapters}
    for i, ch in enumerate(book_data.get("chapters", [])):
        if i in ch_map:
            edited = ch_map[i]
            ch["title"] = sanitize_text(edited.title, 500) or ch["title"]
            ch["introduction"] = sanitize_text(edited.introduction, 5000)
            sec_map = {s.index: s for s in edited.sections}
            for si, sec in enumerate(ch.get("sections", [])):
                if si in sec_map:
                    sec["heading"] = sanitize_text(sec_map[si].heading, 500)
                    sec["content"] = sanitize_text(sec_map[si].content, 20000)

    # Rebuild HTML
    try:
        new_html = build_ebook_html(
            book_data,
            build_params.get("style", "minimal"),
            build_params.get("infographics", []),
            introduction=build_params.get("introduction", ""),
            author_bio=build_params.get("author_bio", ""),
            references=build_params.get("references", []),
            glossary_terms=build_params.get("glossary_terms", []),
            back_cover_blurb=build_params.get("back_cover_blurb", ""),
            back_cover_tagline=build_params.get("back_cover_tagline", ""),
            cover_svg=build_params.get("cover_svg", ""),
            cover_image=build_params.get("cover_image", ""),
            chapter_illustrations=build_params.get("chapter_illustrations", []),
            accent_color=build_params.get("accent_color", ""),
            bg_color=build_params.get("bg_color", ""),
            heading_font=build_params.get("heading_font", ""),
            body_font=build_params.get("body_font", ""),
        )
    except Exception as e:
        logger.error(f"Editor rebuild failed: {e}")
        raise HTTPException(500, f"Failed to rebuild HTML: {e}")

    # Save updated book_data + new HTML
    update_job(job_id, "done", html=new_html, book_data=json.dumps(book_data))
    return {"status": "saved", "job_id": job_id}
