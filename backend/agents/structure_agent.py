from loguru import logger

from backend.core.ai import structure_chapter as _structure_chapter
from backend.core.jobs import update_job
from backend.orchestrator.agent import BaseAgent, PipelineContext


class StructureAgent(BaseAgent):
    """Enhances chapters with summaries, FAQs, checklists, and section types."""

    def __init__(self):
        super().__init__("StructureAgent")

    def run(self, ctx: PipelineContext) -> PipelineContext:
        chapters = ctx.ebook_dict.get("chapters", [])
        logger.info(f"StructureAgent: enriching {len(chapters)} chapters")

        for ci, ch in enumerate(chapters):
            try:
                enriched = _structure_chapter(ch, ci, ctx.provider)
                summary = enriched.get("chapter_summary")
                faq = enriched.get("faq")
                checklist = enriched.get("checklist")

                if summary and summary.get("points"):
                    ch["chapter_summary"] = summary
                if faq and len(faq) > 0:
                    ch["faq"] = faq
                if checklist and checklist.get("items"):
                    ch["checklist"] = checklist

                logger.info(f"  Ch{ci+1}: enriched")
                # Intermediate progress: 36 → 43 over chapters
                pct = 36 + int(7 * (ci + 1) / max(len(chapters), 1))
                ctx.set_progress(pct)
                update_job(ctx.job_id, "processing", pct)
            except Exception as e:
                logger.warning(f"  Ch{ci+1}: skipped ({e})")

        ctx.set_progress(43)
        total = sum(
            1 for ch in chapters
            if ch.get("chapter_summary") or ch.get("faq") or ch.get("checklist")
        )
        logger.success(f"StructureAgent: {total}/{len(chapters)} chapters enriched")
        return ctx
