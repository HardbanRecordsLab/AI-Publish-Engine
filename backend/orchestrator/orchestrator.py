
from loguru import logger

from backend.core import checkpoint
from backend.core.jobs import update_job
from backend.orchestrator.agent import AwaitingApproval, BaseAgent, PipelineContext
from backend.ws_manager import is_cancelled, update_progress


class Orchestrator:
    """Runs a sequence of agents, passing PipelineContext through.

    A job whose inputs were checkpointed (see backend.core.checkpoint) also saves the context after every agent, so a job
    that stopped half way is resumed after the last agent that finished instead of starting over.
    """

    def __init__(self, agents: list[BaseAgent]):
        self.agents = agents

    def run(self, ctx: PipelineContext) -> PipelineContext:
        logger.info(f"Orchestrator starting pipeline with {len(self.agents)} agents")
        saved = checkpoint.has(ctx.job_id)
        done: list[str] = list(checkpoint.stage(ctx.job_id, "done_agents") or []) if saved else []
        snap = checkpoint.stage(ctx.job_id, "ctx") if done else None
        if done and snap:
            ctx = ctx.restored(snap)
            logger.info(f"Orchestrator resuming after {done[-1]} (progress {ctx.progress}%)")
        else:
            done = []
        for idx, agent in enumerate(self.agents):
            if agent.name in done:
                continue
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
                if saved:
                    done.append(agent.name)
                    checkpoint.save_stage(ctx.job_id, "ctx", ctx.snapshot())
                    checkpoint.save_stage(ctx.job_id, "done_agents", done)
            except AwaitingApproval:
                ctx.awaiting_approval = True
                if saved:
                    checkpoint.save_stage(ctx.job_id, "ctx", ctx.snapshot())
                    checkpoint.save_stage(ctx.job_id, "done_agents", done)
                update_job(ctx.job_id, "awaiting_approval", ctx.progress)
                update_progress(ctx.job_id, "awaiting_approval", ctx.progress, agent=agent.name)
                logger.info(f"Orchestrator: {agent.name} waits for the author's approval")
                return ctx
            except Exception as e:
                logger.error(f"Agent {agent.name} failed: {e}")
                ctx.error = str(e)
                update_job(ctx.job_id, "failed", error=str(e))
                update_progress(ctx.job_id, "failed", ctx.progress, error=str(e))
                break
        logger.info(f"Orchestrator pipeline finished (error={ctx.error is not None})")
        return ctx
