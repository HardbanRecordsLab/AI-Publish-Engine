"""arq worker — processes ebook generation jobs from Redis queue."""
import os
import sys
from pathlib import Path
from datetime import datetime
from loguru import logger

# Ensure the project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.jobs import create_job, update_job, get_job
from backend.core.parser import extract_text
from backend.core.builder import build_ebook_html
from backend.core.pdf import html_to_pdf
from backend.core.export import build_epub, build_docx
from backend.core.website import build_website
from backend.core.interactive import build_interactive_book
from backend.orchestrator import Orchestrator, PipelineContext
from backend.ws_manager import update_progress, is_cancelled, clear_cancel
from backend.agents import (
    AnalysisAgent, StructureAgent, ResearchAgent, EditorialAgent, FactCheckAgent,
    DesignSystemAgent, InfographicArchitectAgent, CoverArtAgent, FinalizationAgent, QAAgent,
)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", os.environ.get("OUTPUT_DIR", "outputs"))
os.makedirs(OUTPUT_DIR, exist_ok=True)


async def process_job(ctx):
    """Process a single ebook generation job (called by arq worker)."""
    job_id = ctx["job_id"]
    text = ctx["text"]
    style = ctx.get("style", "minimal")
    provider = ctx.get("provider")
    content_type = ctx.get("content_type", "ebook")
    audience = ctx.get("audience", "")
    tone = ctx.get("tone", "")
    chapters = ctx.get("chapters", "")
    keywords = ctx.get("keywords", "")
    language = ctx.get("language", "")
    accent_color = ctx.get("accent_color", "")
    bg_color = ctx.get("bg_color", "")
    heading_font = ctx.get("heading_font", "")
    body_font = ctx.get("body_font", "")

    try:
        update_progress(job_id, "queued", 0)

        if is_cancelled(job_id):
            update_job(job_id, "cancelled", error="Cancelled by user")
            update_progress(job_id, "cancelled", 0)
            clear_cancel(job_id)
            return

        pipeline_ctx = PipelineContext(
            job_id=job_id, text=text, style=style, provider=provider,
            content_type=content_type, audience=audience, tone=tone,
            chapters=chapters, keywords=keywords, language=language,
            accent_color=accent_color, bg_color=bg_color,
            heading_font=heading_font, body_font=body_font,
        )

        pre_build = Orchestrator([
            AnalysisAgent(),
            StructureAgent(),
            ResearchAgent(),
            EditorialAgent(),
            FactCheckAgent(),
            DesignSystemAgent(),
            InfographicArchitectAgent(),
            CoverArtAgent(),
            FinalizationAgent(),
        ])
        pipeline_ctx = pre_build.run(pipeline_ctx)

        if pipeline_ctx.error:
            update_job(job_id, "failed", error=pipeline_ctx.error)
            update_progress(job_id, "failed", 0, error=pipeline_ctx.error)
            return

        if is_cancelled(job_id):
            update_job(job_id, "cancelled", error="Cancelled by user")
            update_progress(job_id, "cancelled", 0)
            clear_cancel(job_id)
            return

        update_job(job_id, "processing", 72, topic=pipeline_ctx.ebook_dict.get("topic", "general"))
        update_progress(job_id, "processing", 72, agent="Build", topic=pipeline_ctx.ebook_dict.get("topic", "general"))

        is_website = content_type in ("website", "landing-page", "blog-post")
        is_interactive = content_type == "interactive-book"
        if is_interactive:
            html = build_interactive_book(
                pipeline_ctx.ebook_dict, style, pipeline_ctx.infographics,
                introduction=pipeline_ctx.introduction,
                author_bio=pipeline_ctx.author_bio,
                references=pipeline_ctx.references,
                glossary_terms=pipeline_ctx.glossary_terms,
                back_cover_blurb=pipeline_ctx.back_cover_blurb,
                back_cover_tagline=pipeline_ctx.back_cover_tagline,
                cover_svg=pipeline_ctx.cover_svg,
                cover_image=pipeline_ctx.cover_image,
                chapter_illustrations=pipeline_ctx.chapter_illustrations,
                accent_color=accent_color, bg_color=bg_color,
                heading_font=heading_font, body_font=body_font,
            )
        elif is_website:
            html = build_website(
                pipeline_ctx.ebook_dict, style, pipeline_ctx.infographics,
                content_type=content_type,
                accent_color=accent_color, bg_color=bg_color,
                heading_font=heading_font, body_font=body_font,
            )
        else:
            html = build_ebook_html(
                pipeline_ctx.ebook_dict, style, pipeline_ctx.infographics,
                introduction=pipeline_ctx.introduction,
                author_bio=pipeline_ctx.author_bio,
                references=pipeline_ctx.references,
                glossary_terms=pipeline_ctx.glossary_terms,
                back_cover_blurb=pipeline_ctx.back_cover_blurb,
                back_cover_tagline=pipeline_ctx.back_cover_tagline,
                cover_svg=pipeline_ctx.cover_svg,
                cover_image=pipeline_ctx.cover_image,
                chapter_illustrations=pipeline_ctx.chapter_illustrations,
                accent_color=accent_color, bg_color=bg_color,
                heading_font=heading_font, body_font=body_font,
            )
        pipeline_ctx.html = html
        update_job(job_id, "processing", 80, html=html)
        update_progress(job_id, "processing", 80, agent="Quality Check")

        qa = QAAgent()
        pipeline_ctx = qa.run(pipeline_ctx)
        update_job(job_id, "processing", pipeline_ctx.progress)
        update_progress(job_id, "processing", pipeline_ctx.progress, agent="Finalizing")

        # Save book data for WYSIWYG editor
        import json
        book_data_json = json.dumps(pipeline_ctx.ebook_dict)
        build_params_json = json.dumps({
            "style": style, "infographics": pipeline_ctx.infographics,
            "introduction": pipeline_ctx.introduction, "author_bio": pipeline_ctx.author_bio,
            "references": pipeline_ctx.references, "glossary_terms": pipeline_ctx.glossary_terms,
            "back_cover_blurb": pipeline_ctx.back_cover_blurb, "back_cover_tagline": pipeline_ctx.back_cover_tagline,
            "cover_svg": pipeline_ctx.cover_svg, "cover_image": pipeline_ctx.cover_image,
            "chapter_illustrations": pipeline_ctx.chapter_illustrations,
            "accent_color": accent_color, "bg_color": bg_color,
            "heading_font": heading_font, "body_font": body_font,
        })

        if is_interactive:
            website_path = os.path.join(OUTPUT_DIR, f"{job_id}.html")
            with open(website_path, "w", encoding="utf-8") as f:
                f.write(html)
            update_job(job_id, "done", 100, website_path=website_path, html=html,
                       book_data=book_data_json, build_params=build_params_json)
            update_progress(job_id, "done", 100, title=pipeline_ctx.ebook_dict.get('title'))
            logger.success(f"Job {job_id}: {pipeline_ctx.ebook_dict.get('title')} (interactive: {os.path.getsize(website_path)} bytes)")
        elif is_website:
            website_path = os.path.join(OUTPUT_DIR, f"{job_id}.html")
            with open(website_path, "w", encoding="utf-8") as f:
                f.write(html)
            update_job(job_id, "done", 100, website_path=website_path, html=html,
                       book_data=book_data_json, build_params=build_params_json)
            update_progress(job_id, "done", 100, title=pipeline_ctx.ebook_dict.get('title'))
            logger.success(f"Job {job_id}: {pipeline_ctx.ebook_dict.get('title')} (website: {os.path.getsize(website_path)} bytes)")
        else:
            pdf_path = os.path.join(OUTPUT_DIR, f"{job_id}.pdf")
            html_to_pdf(html, pdf_path)

            epub_path = os.path.join(OUTPUT_DIR, f"{job_id}.epub")
            build_epub(pipeline_ctx.ebook_dict, style, pipeline_ctx.infographics, epub_path,
                       introduction=pipeline_ctx.introduction, author_bio=pipeline_ctx.author_bio,
                       references=pipeline_ctx.references, glossary_terms=pipeline_ctx.glossary_terms,
                       back_cover_blurb=pipeline_ctx.back_cover_blurb, back_cover_tagline=pipeline_ctx.back_cover_tagline,
                       cover_svg=pipeline_ctx.cover_svg, cover_image=pipeline_ctx.cover_image,
                       chapter_illustrations=pipeline_ctx.chapter_illustrations)

            docx_path = os.path.join(OUTPUT_DIR, f"{job_id}.docx")
            build_docx(pipeline_ctx.ebook_dict, style, pipeline_ctx.infographics, docx_path,
                       introduction=pipeline_ctx.introduction, author_bio=pipeline_ctx.author_bio,
                       references=pipeline_ctx.references, glossary_terms=pipeline_ctx.glossary_terms,
                       back_cover_blurb=pipeline_ctx.back_cover_blurb, back_cover_tagline=pipeline_ctx.back_cover_tagline,
                       cover_svg=pipeline_ctx.cover_svg, cover_image=pipeline_ctx.cover_image,
                       chapter_illustrations=pipeline_ctx.chapter_illustrations)

            update_job(job_id, "done", 100, output_path=pdf_path, epub_path=epub_path, docx_path=docx_path, html=html,
                       book_data=book_data_json, build_params=build_params_json)
            update_progress(job_id, "done", 100, title=pipeline_ctx.ebook_dict.get('title'))
            logger.success(f"Job {job_id}: {pipeline_ctx.ebook_dict.get('title')} (PDF: {os.path.getsize(pdf_path)} bytes)")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        update_job(job_id, "failed", error=str(e))
        update_progress(job_id, "failed", 0, error=str(e))


# Note: process_job() above is called directly from a background thread
# spawned in backend/routers/jobs.py (_queue_job). There is no separate
# worker process to run — everything happens inside the main FastAPI
# process. This used to also support enqueueing to a Redis/arq queue via a
# `WorkerSettings` class run as `arq backend.worker.WorkerSettings`, but
# that path was never actually reachable (see the comment in jobs.py) and
# has been removed to avoid the false impression that a Redis worker needs
# to be running for jobs to process.
