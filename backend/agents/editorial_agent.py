from loguru import logger

from backend.core.ai import build_brief, words_per_section
from backend.core.ai import write_chapter as _write_chapter
from backend.core.jobs import update_job
from backend.models.content_block import ContentBlock
from backend.orchestrator.agent import BaseAgent, PipelineContext
from backend.ws_manager import is_cancelled


class EditorialAgent(BaseAgent):
    """Writes each chapter out in full from the outline, using the research notes."""

    def __init__(self):
        super().__init__("EditorialAgent")

    def run(self, ctx: PipelineContext) -> PipelineContext:
        chapters = ctx.ebook_dict.get("chapters", [])
        logger.info(f"EditorialAgent: writing {len(chapters)} chapters")
        brief = build_brief(ctx.audience, ctx.tone, ctx.keywords, ctx.language)
        target_words = words_per_section(ctx.content_type)

        research_chapters = {}
        if ctx.research:
            for rc in ctx.research.get("chapters", []):
                research_chapters[rc.get("index")] = rc

        improved = []
        previous_summaries: list[str] = []
        for i, ch in enumerate(chapters):
            if is_cancelled(ctx.job_id):
                # The orchestrator marks the job cancelled before the next agent.
                improved.extend(chapters[i:])
                break
            try:
                written = _write_chapter(
                    ch, book=ctx.ebook_dict, chapter_index=i,
                    research_suggestions=research_chapters.get(i),
                    previous_summaries=previous_summaries,
                    words_per_section=target_words, brief=brief,
                    language=ctx.language, provider=ctx.provider,
                )
                improved.append(written)
                words = sum(len(s.get("content", "").split()) for s in written.get("sections", []))
                logger.info(f"  Ch{i+1}: written ({words} words)")
            except Exception as e:
                logger.warning(f"  Ch{i+1}: kept outline draft ({e})")
                written = ch
                improved.append(ch)
            previous_summaries.append(
                f"Ch{i+1} {written.get('title', '')}: {written.get('key_takeaway', '')}"
            )
            # Intermediate progress: 37 → 53 over chapters (the longest step)
            pct = 37 + int(16 * (i + 1) / max(len(chapters), 1))
            ctx.set_progress(pct)
            update_job(ctx.job_id, "processing", pct)

        ctx.ebook_dict["chapters"] = improved

        ctx.document = _rebuild_document(ctx.ebook_dict)
        ctx.set_progress(53)
        logger.success(f"EditorialAgent: {len(improved)} chapters written")
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
