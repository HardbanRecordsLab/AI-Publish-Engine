from loguru import logger

from backend.core.ai import plan_infographics as _plan_infographics
from backend.orchestrator.agent import BaseAgent, PipelineContext


class InfographicArchitectAgent(BaseAgent):
    """Analyses content and plans where infographics are needed."""

    def __init__(self):
        super().__init__("InfographicArchitectAgent")

    def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx.infographics = _plan_infographics(ctx.ebook_dict, ctx.design, ctx.provider) or []
        ctx.set_progress(68)
        logger.success(
            f"InfographicArchitectAgent: {len(ctx.infographics)} infographics planned"
        )
        return ctx
