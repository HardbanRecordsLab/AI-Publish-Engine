"""Agents of the interactive-course pipeline: research the web, design the course, write every lesson, assemble and check it."""
from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger

from backend.core import checkpoint, course_gen, quality, webresearch
from backend.core.ai import checker_json, writer_json
from backend.core.cost_tracker import BudgetExceeded
from backend.core.jobs import update_job
from backend.orchestrator.agent import AwaitingApproval, BaseAgent, PipelineContext
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
        ctx.research = {"queries": [q["q"] + (f" [{q['lang']}]" if q.get("lang") else "") for q in queries], "providers": webresearch.active_providers(), "sources": len(sources)}
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
        fmt = course_gen.course_format(ctx.course_format)
        units = course_gen.day_count(ctx.chapters) if fmt == "program" else course_gen.lesson_count(ctx.chapters)
        outline = course_gen.design_outline(llm, ctx.text, _sources(ctx), language=ctx.language, audience=ctx.audience, tone=ctx.tone,
                                            lessons=units, fmt=fmt)
        ctx.course = {"outline": {**outline, "_brief": ctx.text}}
        ctx.ebook_dict = {"title": outline["title"], "topic": "education", "kind": "course"}
        if checkpoint.has(ctx.job_id):
            checkpoint.save_stage(ctx.job_id, "outline", outline)
        ctx.set_progress(30)
        return ctx


class CourseOutlineGateAgent(BaseAgent):
    """With "review the outline first" the job parks here until the author approves (and perhaps edits) the plan: a wrong plan is
    the most expensive mistake, and it is visible after seconds instead of after the whole course has been written."""

    def __init__(self):
        super().__init__("CourseOutlineGateAgent")

    def run(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.review_outline or not checkpoint.has(ctx.job_id):
            return ctx
        if not checkpoint.stage(ctx.job_id, "outline_approved"):
            raise AwaitingApproval()
        edited = checkpoint.stage(ctx.job_id, "outline")
        if isinstance(edited, dict) and edited.get("phases"):
            ctx.course["outline"] = {**edited, "_brief": ctx.text}
            ctx.ebook_dict = {"title": edited.get("title") or ctx.ebook_dict.get("title", ""), "topic": "education", "kind": "course"}
        ctx.set_progress(30)
        return ctx


class LessonWriterAgent(BaseAgent):
    """One model call per lesson, each grounded in the sources the outline assigned to it. Lessons are independent, so a few are written
    at a time (the 5-lesson test took 13 minutes one by one); the model helpers throttle and meter calls from several threads safely."""
    WORKERS = 3

    def __init__(self, llm=None):
        super().__init__("LessonWriterAgent")
        self._llm = llm

    def run(self, ctx: PipelineContext) -> PipelineContext:
        llm = self._llm or make_llm(ctx.provider)
        outline = ctx.course["outline"]
        specs = [l for p in outline["phases"] for l in p["lessons"]]
        sources = _sources(ctx)
        if is_cancelled(ctx.job_id):
            raise RuntimeError("Cancelled by user")
        lessons: list = [None] * len(specs)
        write = course_gen.write_day if outline.get("format") == "program" else course_gen.write_lesson
        saved = checkpoint.has(ctx.job_id)
        for i, lesson in (checkpoint.items(ctx.job_id, "lessons") if saved else {}).items():
            if i < len(specs) and isinstance(lesson, dict) and lesson.get("title"):
                lessons[i] = lesson   # written before the job stopped: keep it, do not pay for it twice
        pending = [i for i, l in enumerate(lessons) if l is None]
        if len(pending) < len(specs):
            logger.info(f"LessonWriterAgent: resuming, {len(specs) - len(pending)} of {len(specs)} already written")

        def task(i: int) -> dict:
            lesson = write(llm, outline, specs[i], i, len(specs), sources, language=ctx.language, tone=ctx.tone)
            if saved:
                checkpoint.save_item(ctx.job_id, "lessons", i, lesson)   # in the worker thread, so work that finishes while another day fails is kept
            return lesson

        with ThreadPoolExecutor(max_workers=self.WORKERS) as pool:
            futures = {pool.submit(task, i): i for i in pending}
            finished = len(specs) - len(pending)
            try:
                for f in as_completed(futures):
                    lessons[futures[f]] = f.result()
                    finished += 1
                    pct = 30 + int(55 * finished / len(specs))
                    ctx.set_progress(pct)
                    update_job(ctx.job_id, "processing", pct)
                    logger.info(f"LessonWriterAgent: {finished}/{len(specs)} lessons written")
                    if is_cancelled(ctx.job_id):
                        raise RuntimeError("Cancelled by user")
            except BaseException:
                for f in futures:
                    f.cancel()
                raise
        ctx.course["lessons"] = lessons
        return ctx


class CourseFrameAgent(BaseAgent):
    """The pages around the days: welcome, for whom, what it does and does not promise, when not to use it, worksheets, FAQ, what next.
    Never fails the job: without a usable frame the course is published with the days alone."""

    def __init__(self, llm=None):
        super().__init__("CourseFrameAgent")
        self._llm = llm

    def run(self, ctx: PipelineContext) -> PipelineContext:
        llm = self._llm or make_llm(ctx.provider)
        if is_cancelled(ctx.job_id):
            raise RuntimeError("Cancelled by user")
        ctx.course["frame"] = course_gen.write_frame(llm, ctx.course["outline"], ctx.course["lessons"], language=ctx.language, tone=ctx.tone,
                                                     audience=ctx.audience, brief=ctx.text)
        ctx.set_progress(87)
        update_job(ctx.job_id, "processing", 87)
        logger.info(f"CourseFrameAgent: {len(ctx.course['frame'])} frame parts")
        return ctx


def make_checker(provider: str | None):
    def llm(system: str, user: str, max_tokens: int = 2500) -> dict:
        return checker_json(system, user, provider, max_tokens=max_tokens)
    return llm


class CourseQualityAgent(BaseAgent):
    """The last look before the author reads the course. Plain-code checks (leftover placeholders, citations that point nowhere, text repeated
    between days) plus a short model pass that lists the specific facts a day states without the sources backing them. A day with such claims is
    rewritten once, told which statements to remove or soften; whatever the report still lists is for the author to look at. Never fails the job."""
    WORKERS = 3
    MAX_REWRITES = 8   # a draft that needs more than this is not fixed by patching days one at a time

    def __init__(self, llm=None, checker=None):
        super().__init__("CourseQualityAgent")
        self._llm, self._checker = llm, checker or llm   # an injected model (tests) does the checking too

    def run(self, ctx: PipelineContext) -> PipelineContext:
        try:
            self._review(ctx)
        except BudgetExceeded:
            raise
        except Exception as e:  # noqa: BLE001 - a failed review must not cost the author the course
            logger.warning(f"CourseQualityAgent: review skipped ({e})")
            ctx.course["quality"] = {"error": str(e)[:200]}
        ctx.set_progress(87)
        update_job(ctx.job_id, "processing", 87)
        return ctx

    def _review(self, ctx: PipelineContext) -> None:
        outline, lessons, sources = ctx.course["outline"], ctx.course["lessons"], _sources(ctx)
        program = outline.get("format") == "program"
        labels = [f"{'Day' if program else 'Lesson'} {i + 1}" for i in range(len(lessons))]
        texts = [quality.unit_text(l) for l in lessons]
        units = list(zip(labels, texts))
        sensitive = bool(outline.get("sensitive"))
        report = {"checked": len(lessons), "static": quality.static_issues(units, {s.id for s in sources}) if sources else quality.static_issues(units),
                  "repeats": quality.repeated_passages(units), "unsupported": [], "fixed": 0, "sensitive": sensitive}
        saved = checkpoint.has(ctx.job_id)
        known = checkpoint.items(ctx.job_id, "claims") if saved else {}
        checker = self._checker or make_checker(ctx.provider)

        def check(i: int) -> list:
            if i in known:
                return known[i]
            ids = lessons[i].get("sources") or []
            source_text = course_gen.sources_block(sources, ids or None, chars=1800 if ids else 700) if sources else "(no sources were found)"
            claims = quality.check_claims(checker, texts[i], source_text, sensitive=sensitive, language=ctx.language)
            if saved:
                checkpoint.save_item(ctx.job_id, "claims", i, claims)
            return claims

        claims: dict[int, list] = {}
        with ThreadPoolExecutor(max_workers=self.WORKERS) as pool:
            futures = {pool.submit(check, i): i for i in range(len(lessons))}
            for f in as_completed(futures):
                try:
                    claims[futures[f]] = f.result()
                except BudgetExceeded:
                    raise
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"CourseQualityAgent: {labels[futures[f]]} not checked ({e})")
                    report["unchecked"] = report.get("unchecked", 0) + 1
        flagged = sorted(i for i, c in claims.items() if c)
        titles = [l["title"] for l in lessons]   # as the author saw them in the plan, before any rewrite
        fixed: set[int] = set()
        if flagged and sources:
            write = course_gen.write_day if program else course_gen.write_lesson
            specs = [l for p in outline["phases"] for l in p["lessons"]]

            def rewrite(i: int):
                try:
                    return i, write(self._llm or make_llm(ctx.provider), outline, specs[i], i, len(lessons), sources, language=ctx.language, tone=ctx.tone,
                                    note=quality.fix_note(claims[i]), previous=lessons[i])
                except BudgetExceeded:
                    raise
                except Exception as e:  # noqa: BLE001 - the first version stays
                    logger.warning(f"CourseQualityAgent: {labels[i]} could not be rewritten ({e})")
                    return i, None

            with ThreadPoolExecutor(max_workers=self.WORKERS) as pool:
                for i, new in pool.map(rewrite, flagged[:self.MAX_REWRITES]):
                    if new:
                        lessons[i] = new
                        fixed.add(i)
        for i in flagged:
            for c in claims[i]:
                report["unsupported"].append({"unit": labels[i], "title": titles[i], "claim": c["claim"], "why": c["why"], "fixed": i in fixed})
        report["fixed"] = len(fixed)
        ctx.course["lessons"], ctx.course["quality"] = lessons, report
        logger.info(f"CourseQualityAgent: {len(flagged)} unit(s) with unsupported claims, {len(fixed)} rewritten, {len(report['repeats'])} repeated passage(s), "
                    f"{len(report['static'])} static issue(s)")


class CourseAssemblyAgent(BaseAgent):
    def __init__(self):
        super().__init__("CourseAssemblyAgent")

    def run(self, ctx: PipelineContext) -> PipelineContext:
        course = course_gen.assemble_course(ctx.course["outline"], ctx.course["lessons"], _sources(ctx), language=ctx.language, frame=ctx.course.get("frame"),
                                            quality=ctx.course.get("quality"))
        problems = course_gen.validate_course(course)
        if problems:
            raise course_gen.CourseGenerationError("The course is incomplete: " + "; ".join(problems[:6]))
        ctx.course = course
        ctx.ebook_dict = {"title": course["title"], "topic": "education", "kind": "course", "language": course["language"]}
        ctx.set_progress(88)
        logger.success(f"CourseAssemblyAgent: '{course['title']}', {sum(len(p['lessons']) for p in course['phases'])} lessons, "
                       f"{len(course['final_test'])} test questions, {len(course['sources'])} sources")
        return ctx


def course_pipeline(llm=None, gather=None, checker=None) -> list[BaseAgent]:
    return [CourseResearchAgent(llm, gather), CourseArchitectAgent(llm), CourseOutlineGateAgent(), LessonWriterAgent(llm), CourseFrameAgent(llm), CourseQualityAgent(llm, checker), CourseAssemblyAgent()]
