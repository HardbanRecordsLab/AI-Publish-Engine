from loguru import logger

from backend.core.ai import fact_check as _fact_check
from backend.orchestrator.agent import BaseAgent, PipelineContext


class FactCheckAgent(BaseAgent):
    """Identifies contradictions, unsubstantiated claims, potential errors."""

    def __init__(self):
        super().__init__("FactCheckAgent")

    def run(self, ctx: PipelineContext) -> PipelineContext:
        logger.info("FactCheckAgent: reviewing content consistency")
        try:
            ctx.fact_check = _fact_check(ctx.ebook_dict, ctx.provider)
            issues = len(ctx.fact_check)
            if issues:
                high = sum(1 for f in ctx.fact_check if f.get("severity") == "high")
                logger.warning(f"FactCheckAgent: {issues} flags ({high} high severity)")
            else:
                logger.success("FactCheckAgent: no issues found")
        except Exception as e:
            logger.warning(f"FactCheckAgent skipped ({e})")
            ctx.fact_check = []
        ctx.set_progress(60)
        return ctx
