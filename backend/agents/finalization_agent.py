from loguru import logger
from backend.orchestrator.agent import BaseAgent, PipelineContext
from backend.core.ai import generate_ebook_sections as _generate_sections
from backend.core.jobs import update_job


class FinalizationAgent(BaseAgent):
    """Generates final ebook sections: introduction, about author, references, glossary, back cover."""

    def __init__(self):
        super().__init__("FinalizationAgent")

    def run(self, ctx: PipelineContext) -> PipelineContext:
        logger.info("FinalizationAgent: generating final ebook sections")
        try:
            sections = _generate_sections(ctx.ebook_dict, ctx.style, ctx.provider)
            ctx.introduction = sections.get("introduction", "")
            ctx.author_bio = sections.get("author_bio", "")
            ctx.references = sections.get("references", [])
            ctx.glossary_terms = sections.get("glossary_terms", [])
            ctx.back_cover_blurb = sections.get("back_cover_blurb", "")
            ctx.back_cover_tagline = sections.get("back_cover_tagline", "")
            logger.success("FinalizationAgent: all sections generated")
        except Exception as e:
            logger.warning(f"FinalizationAgent skipped ({e})")
            ctx.introduction = ""
            ctx.author_bio = ""
            ctx.references = []
            ctx.glossary_terms = []
            ctx.back_cover_blurb = ""
            ctx.back_cover_tagline = ""
        ctx.set_progress(70)
        update_job(ctx.job_id, "processing", 70)
        return ctx
