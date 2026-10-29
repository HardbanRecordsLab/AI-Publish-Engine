"""Agents of the interactive-course pipeline: research the web, design the course, write every lesson, assemble and check it."""
from loguru import logger

from backend.core import course_gen, webresearch
from backend.core.ai import writer_json
from backend.core.jobs import update_job
from backend.orchestrator.agent import BaseAgent, PipelineContext
from backend.ws_manager import is_cancelled


def make_llm(provider: str | None):
    """Adapter from the engine's model helpers to the (system, user, max_tokens) callable course_gen expects."""
    def llm(system: str, user: str, max_tokens: int = 6000) -> dict:
        return writer_json(system, user, provider, temperature=0.5, max_tokens=max_tokens)
    return llm


class CourseResearchAgent(BaseAgent):
    """Plans search queries, searches the web and reads the best pages; the author's own URLs are read first."""

    def __init__(self, llm=None, gather=None):
        super().__init__("CourseResearchAgent")
        self._llm, self._gather = llm, gather or webresearch.gather_sources

    def run(self, ctx: PipelineContext) -> PipelineContext:
        llm = self._llm or make_llm(ctx.provider)
        queries = course_gen.plan_queries(llm, ctx.text, ctx.language, ctx.audience)
        ctx.set_progress(8)
        sources = self._gather(queries, course_gen.lang_code(ctx.language) or "en", user_urls=webresearch.urls_in(ctx.text))
        ctx.web_sources = webresearch.sources_as_dicts(sources)
        ctx.research = {"queries": queries, "providers": webresearch.active_providers(), "sources": len(sources)}
        if not sources:
            logger.warning("CourseResearchAgent: no web sources found; the course will rest on the author's material and general knowledge")
        ctx.set_progress(22)
        return ctx


def _sources(ctx: PipelineContext) -> list[webresearch.Source]:
    return [webresearch.Source(**s) for s in ctx.web_sources]


class CourseArchitectAgent(BaseAgent):
    def __init__(self, llm=None):
        super().__init__("CourseArchitectAgent")
        self._llm = llm

    def run(self, ctx: PipelineContext) -> PipelineContext:
        llm = self._llm or make_llm(ctx.provider)
        outline = course_gen.design_outline(llm, ctx.text, _sources(ctx), language=ctx.language, audience=ctx.audience, tone=ctx.tone,
                                            lessons=course_gen.lesson_count(ctx.chapters))
        outline["_brief"] = ctx.text
        ctx.course = {"outline": outline}
        ctx.ebook_dict = {"title": outline["title"], "topic": "education", "kind": "course"}
        ctx.set_progress(30)
        return ctx


class LessonWriterAgent(BaseAgent):
    """One model call per lesson, each grounded in the sources the outline assigned to it."""

    def __init__(self, llm=None):
        super().__init__("LessonWriterAgent")
        self._llm = llm

    def run(self, ctx: PipelineContext) -> PipelineContext:
        llm = self._llm or make_llm(ctx.provider)
        outline = ctx.course["outline"]
        specs = [l for p in outline["phases"] for l in p["lessons"]]
        sources = _sources(ctx)
        lessons = []
        for i, spec in enumerate(specs):
            if is_cancelled(ctx.job_id):
                raise RuntimeError("Cancelled by user")
            lessons.append(course_gen.write_lesson(llm, outline, spec, i, len(specs), sources, language=ctx.language, tone=ctx.tone))
            pct = 30 + int(55 * (i + 1) / len(specs))
            ctx.set_progress(pct)
            update_job(ctx.job_id, "processing", pct)
            logger.info(f"LessonWriterAgent: lesson {i + 1}/{len(specs)} written")
        ctx.course["lessons"] = lessons
        return ctx


class CourseAssemblyAgent(BaseAgent):
    def __init__(self):
        super().__init__("CourseAssemblyAgent")

    def run(self, ctx: PipelineContext) -> PipelineContext:
        course = course_gen.assemble_course(ctx.course["outline"], ctx.course["lessons"], _sources(ctx), language=ctx.language)
        problems = course_gen.validate_course(course)
        if problems:
            raise course_gen.CourseGenerationError("The course is incomplete: " + "; ".join(problems[:6]))
        ctx.course = course
        ctx.ebook_dict = {"title": course["title"], "topic": "education", "kind": "course", "language": course["language"]}
        ctx.set_progress(88)
        logger.success(f"CourseAssemblyAgent: '{course['title']}', {sum(len(p['lessons']) for p in course['phases'])} lessons, "
                       f"{len(course['final_test'])} test questions, {len(course['sources'])} sources")
        return ctx


def course_pipeline(llm=None, gather=None) -> list[BaseAgent]:
    return [CourseResearchAgent(llm, gather), CourseArchitectAgent(llm), LessonWriterAgent(llm), CourseAssemblyAgent()]
