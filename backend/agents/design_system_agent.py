from loguru import logger
from backend.orchestrator.agent import BaseAgent, PipelineContext
from backend.core.ai import generate_design_system as _generate_design_system
from backend.core.tokens import list_themes, get_tokens_for_ai, get_theme_topics


class DesignSystemAgent(BaseAgent):
    """Selects or generates visual design tokens for the project."""

    def __init__(self):
        super().__init__("DesignSystemAgent")

    def run(self, ctx: PipelineContext) -> PipelineContext:
        tone = ctx.ebook_dict.get("tone", "professional") if ctx.ebook_dict else "professional"
        topic = ctx.ebook_dict.get("topic", "") if ctx.ebook_dict else ""
        # Theme selection: prefer style override, then auto-detect from topic
        style = ctx.style
        if style == "auto" and topic:
            from backend.core.tokens import TOPIC_MAP
            candidates = TOPIC_MAP.get(topic, ["minimal"])
            style = candidates[0] if isinstance(candidates, list) else "minimal"
        ctx.design = _generate_design_system(style, tone)
        ctx.set_progress(62)
        logger.success(f"DesignSystemAgent: theme={ctx.design.get('theme')} vibe={ctx.design.get('vibe')}")
        return ctx
