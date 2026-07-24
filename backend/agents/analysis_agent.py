from loguru import logger
from backend.orchestrator.agent import BaseAgent, PipelineContext
from backend.models.content_block import ContentBlock
from backend.core.ai import analyze_text as _analyze_text


class AnalysisAgent(BaseAgent):
    """Transforms raw text into a structured ContentBlock document tree."""

    def __init__(self):
        super().__init__("AnalysisAgent")

    def run(self, ctx: PipelineContext) -> PipelineContext:
        logger.info(f"AnalysisAgent: analyzing {len(ctx.text)} chars")
        raw = _analyze_text(ctx.text, ctx.provider)

        doc = ContentBlock(type="document", data={
            "title": raw.get("title", ""),
            "subtitle": raw.get("subtitle", ""),
            "author": raw.get("author", "AI Design Engine"),
            "topic": raw.get("topic", "general"),
            "tone": raw.get("tone", "professional"),
            "audience": raw.get("audience", ""),
            "summary": raw.get("summary", ""),
        })

        for ci, ch in enumerate(raw.get("chapters", [])):
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

        conclusion = raw.get("conclusion", {})
        doc.add(ContentBlock(type="conclusion", data={
            "title": conclusion.get("title", "Conclusion"),
            "content": conclusion.get("content", ""),
        }))

        ctx.document = doc
        ctx.ebook_dict = doc.to_ebook_dict()
        ctx.set_progress(35)
        logger.success(
            f"AnalysisAgent: {len(raw.get('chapters', []))} chapters, "
            f"topic={raw.get('topic', 'unknown')}"
        )
        return ctx
