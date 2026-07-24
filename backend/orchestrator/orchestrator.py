
from loguru import logger

from backend.core.jobs import update_job
from backend.orchestrator.agent import BaseAgent, PipelineContext
from backend.ws_manager import is_cancelled, update_progress


class Orchestrator:
    """Runs a sequence of agents, passing PipelineContext through."""

    def __init__(self, agents: list[BaseAgent]):
        self.agents = agents

    def run(self, ctx: PipelineContext) -> PipelineContext:
        logger.info(f"Orchestrator starting pipeline with {len(self.agents)} agents")
        for idx, agent in enumerate(self.agents):
            if is_cancelled(ctx.job_id):
                ctx.error = "Cancelled by user"
                update_job(ctx.job_id, "cancelled", error="Cancelled by user")
                update_progress(ctx.job_id, "cancelled", 0)
                return ctx
            logger.info(f"Running agent: {agent.name}")
            try:
                ctx = agent.run(ctx)
                topic = None
                if ctx.ebook_dict:
                    topic = ctx.ebook_dict.get("topic")
                update_job(
                    ctx.job_id, "processing", ctx.progress,
                    topic=topic, html=ctx.html,
                )
                update_progress(ctx.job_id, "processing", ctx.progress, agent=agent.name, topic=topic)
            except Exception as e:
                logger.error(f"Agent {agent.name} failed: {e}")
                ctx.error = str(e)
                update_job(ctx.job_id, "failed", error=str(e))
                update_progress(ctx.job_id, "failed", ctx.progress, error=str(e))
                break
        logger.info(f"Orchestrator pipeline finished (error={ctx.error is not None})")
        return ctx
