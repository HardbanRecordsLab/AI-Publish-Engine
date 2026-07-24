from loguru import logger

from backend.core.ai import research_content as _research_content
from backend.orchestrator.agent import BaseAgent, PipelineContext


class ResearchAgent(BaseAgent):
    """Suggests sources, examples, and expansion ideas for each chapter."""

    def __init__(self):
        super().__init__("ResearchAgent")

    def run(self, ctx: PipelineContext) -> PipelineContext:
        logger.info(f"ResearchAgent: researching {len(ctx.ebook_dict.get('chapters', []))} chapters")
        try:
            ctx.research = _research_content(ctx.ebook_dict, ctx.provider)
            ch_count = len(ctx.research.get("chapters", []))
            logger.success(f"ResearchAgent: {ch_count} chapters researched")
        except Exception as e:
            logger.warning(f"ResearchAgent skipped ({e})")
            ctx.research = {"chapters": [], "overall_suggestions": {}}
        ctx.set_progress(45)
        return ctx
