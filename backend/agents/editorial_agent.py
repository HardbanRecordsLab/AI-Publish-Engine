from loguru import logger

from backend.core.ai import editorial_rewrite_chapter as _rewrite_chapter
from backend.core.jobs import update_job
from backend.models.content_block import ContentBlock
from backend.orchestrator.agent import BaseAgent, PipelineContext


class EditorialAgent(BaseAgent):
    """Improves chapter writing: grammar, flow, transitions, tone consistency."""

    def __init__(self):
        super().__init__("EditorialAgent")

    def run(self, ctx: PipelineContext) -> PipelineContext:
        chapters = ctx.ebook_dict.get("chapters", [])
        logger.info(f"EditorialAgent: editing {len(chapters)} chapters")

        research_chapters = {}
        if ctx.research:
            for rc in ctx.research.get("chapters", []):
                research_chapters[rc.get("index")] = rc

        improved = []
        for i, ch in enumerate(chapters):
            try:
                r = research_chapters.get(i)
                edited = _rewrite_chapter(ch, r, ctx.provider)
                improved.append(edited)
                logger.info(f"  Ch{i+1}: edited")
                # Intermediate progress: 46 → 55 over chapters
                pct = 46 + int(9 * (i + 1) / max(len(chapters), 1))
                ctx.set_progress(pct)
                update_job(ctx.job_id, "processing", pct)
            except Exception as e:
                logger.warning(f"  Ch{i+1}: skipped ({e})")
                improved.append(ch)

        ctx.ebook_dict["chapters"] = improved

        ctx.document = _rebuild_document(ctx.ebook_dict)
        ctx.set_progress(55)
        logger.success(f"EditorialAgent: {len(improved)} chapters processed")
        return ctx


def _rebuild_document(ebook_dict: dict) -> ContentBlock:
    """Rebuild ContentBlock tree from updated ebook_dict."""
    doc = ContentBlock(type="document", data={
        "title": ebook_dict.get("title", ""),
        "subtitle": ebook_dict.get("subtitle", ""),
        "author": ebook_dict.get("author", "AI Design Engine"),
        "topic": ebook_dict.get("topic", "general"),
        "tone": ebook_dict.get("tone", "professional"),
        "audience": ebook_dict.get("audience", ""),
        "summary": ebook_dict.get("summary", ""),
    })
    for ci, ch in enumerate(ebook_dict.get("chapters", [])):
        chapter = ContentBlock(
            type="chapter",
            data={
                "title": ch.get("title", f"Chapter {ci+1}"),
                "introduction": ch.get("introduction", ""),
                "key_takeaway": ch.get("key_takeaway", ""),
            },
            meta={"index": ci},
        )
        for si, sec in enumerate(ch.get("sections", [])):
            section = ContentBlock(
                type="section",
                data={"heading": sec.get("heading", "")},
                meta={"index": si},
            )
            section.add(ContentBlock(
                type="paragraph",
                data={"text": sec.get("content", "")},
            ))
            chapter.add(section)
        doc.add(chapter)
    conclusion = ebook_dict.get("conclusion", {})
    doc.add(ContentBlock(type="conclusion", data={
        "title": conclusion.get("title", "Conclusion"),
        "content": conclusion.get("content", ""),
    }))
    return doc
