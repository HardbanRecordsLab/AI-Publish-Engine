import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger

from backend.core import checkpoint
from backend.core.ai import build_brief, words_per_section
from backend.core.ai import review_chapter as _review_chapter
from backend.core.ai import write_chapter as _write_chapter
from backend.core.book_kinds import get_kind
from backend.core.cost_tracker import BudgetExceeded
from backend.core.jobs import update_job
from backend.models.content_block import ContentBlock
from backend.orchestrator.agent import BaseAgent, PipelineContext
from backend.ws_manager import is_cancelled

# One editor's review per chapter; a chapter scoring below this (or far under
# its target length) gets exactly one rewrite with the review's notes.
REVIEW_ENABLED = os.getenv("AI_CHAPTER_REVIEW", "1") != "0"
REVIEW_MIN_SCORE = int(os.getenv("AI_REVIEW_MIN_SCORE", "7"))
MIN_LENGTH_RATIO = 0.6


def _word_count(chapter: dict) -> int:
    return sum(len(s.get("content", "").split()) for s in chapter.get("sections", []))


class EditorialAgent(BaseAgent):
    """Writes each chapter out in full from the outline, using the research notes.

    Non-fiction chapters are independent given the outline, so a few are written at a time (AI_CHAPTER_WORKERS, default 3; 1 writes them one
    after another as before). Each chapter is told what the earlier ones are *planned* to cover, and QAAgent looks for passages repeated
    between chapters afterwards. Fiction stays sequential: a chapter needs the events and character state of the one before it.
    Every finished chapter is checkpointed, so a job that stops resumes with the chapters it already has."""
    WORKERS = max(1, int(os.getenv("AI_CHAPTER_WORKERS", "3")))

    def __init__(self):
        super().__init__("EditorialAgent")

    def run(self, ctx: PipelineContext) -> PipelineContext:
        chapters = ctx.ebook_dict.get("chapters", [])
        logger.info(f"EditorialAgent: writing {len(chapters)} chapters")
        brief = build_brief(ctx.audience, ctx.tone, ctx.keywords, ctx.language)
        target_words = words_per_section(ctx.content_type, ctx.kind)
        story = get_kind(ctx.kind).is_story

        research_chapters = {}
        if ctx.research:
            for rc in ctx.research.get("chapters", []):
                research_chapters[rc.get("index")] = rc

        saved = checkpoint.has(ctx.job_id)
        improved: list = [None] * len(chapters)
        for i, item in (checkpoint.items(ctx.job_id, "chapters") if saved else {}).items():
            if i < len(chapters) and isinstance(item, dict) and item.get("chapter"):
                improved[i] = item["chapter"]   # written before the job stopped: keep it, do not pay for it twice
                if item.get("review"):
                    ctx.chapter_reviews.append(item["review"])
        resumed = sum(1 for c in improved if c is not None)
        if resumed:
            logger.info(f"EditorialAgent: resuming, {resumed} of {len(chapters)} chapters already written")
        finished = resumed
        lock = threading.Lock()

        def gist(ch: dict) -> str:
            return ch.get("recap") or ch.get("key_takeaway") or ch.get("introduction", "")[:200]

        def write_one(i: int, previous: list[str]) -> dict | None:
            if is_cancelled(ctx.job_id):
                return None   # the orchestrator marks the job cancelled before the next agent
            ch = chapters[i]
            ok = True
            try:
                written = _write_chapter(
                    ch, book=ctx.ebook_dict, chapter_index=i,
                    research_suggestions=research_chapters.get(i),
                    previous_summaries=previous,
                    words_per_section=target_words, brief=brief,
                    language=ctx.language, provider=ctx.provider, kind=ctx.kind,
                )
                logger.info(f"  Ch{i+1}: written ({_word_count(written)} words)")
                written = self._review_and_revise(ctx, written, i, research_chapters.get(i),
                                                  previous, target_words, brief)
            except BudgetExceeded:
                raise
            except Exception as e:
                logger.warning(f"  Ch{i+1}: kept outline draft ({e})")
                written, ok = ch, False
            if saved and ok:
                review = next((r for r in ctx.chapter_reviews if r.get("chapter") == i + 1), None)
                checkpoint.save_item(ctx.job_id, "chapters", i, {"chapter": written, "review": review})
            return written

        def progress() -> None:
            nonlocal finished
            with lock:
                finished += 1
                # Intermediate progress: 37 -> 53 over chapters (the longest step)
                pct = 37 + int(16 * finished / max(len(chapters), 1))
                ctx.set_progress(pct)
            update_job(ctx.job_id, "processing", pct)

        pending = [i for i, c in enumerate(improved) if c is None]
        if story or self.WORKERS <= 1 or len(pending) <= 1:
            # One after another; what later chapters are told has already happened: a fiction recap carries events and character
            # state, otherwise the takeaway / intro.
            previous_summaries = [f"Ch{j+1} {improved[j].get('title', '')}: {gist(improved[j])}" for j in range(len(chapters)) if improved[j] is not None and j < (pending[0] if pending else 0)]
            for i in pending:
                written = write_one(i, previous_summaries)
                if written is None:
                    break   # cancelled: the chapters not written keep their outline draft (filled in below)
                improved[i] = written
                previous_summaries.append(f"Ch{i+1} {written.get('title', '')}: {gist(written)}")
                progress()
        else:
            planned = [f"Ch{j+1} {c.get('title', '')}: {gist(c)}" for j, c in enumerate(chapters)]
            with ThreadPoolExecutor(max_workers=min(self.WORKERS, len(pending))) as pool:
                futures = {pool.submit(write_one, i, planned[:i]): i for i in pending}
                try:
                    for f in as_completed(futures):
                        i = futures[f]
                        improved[i] = f.result() or chapters[i]
                        progress()
                except BaseException:
                    for f in futures:
                        f.cancel()
                    raise
        improved = [c if c is not None else chapters[i] for i, c in enumerate(improved)]
        ctx.chapter_reviews.sort(key=lambda r: r.get("chapter", 0))

        ctx.ebook_dict["chapters"] = improved

        ctx.document = _rebuild_document(ctx.ebook_dict)
        if ctx.chapter_reviews:
            scores = [r["score"] for r in ctx.chapter_reviews if r.get("score")]
            if scores:
                logger.info(f"EditorialAgent: average chapter score {sum(scores) / len(scores):.1f}/10")
        ctx.set_progress(53)
        logger.success(f"EditorialAgent: {len(improved)} chapters written")
        return ctx

    def _review_and_revise(self, ctx: PipelineContext, chapter: dict, i: int, research: dict | None,
                           previous_summaries: list[str], target_words: int, brief: str) -> dict:
        """Review a freshly written chapter; rewrite it once if it falls short.
        Any failure here keeps the chapter as written."""
        if not REVIEW_ENABLED:
            return chapter
        record: dict = {"chapter": i + 1, "words": _word_count(chapter), "revised": False}
        notes: list[str] = []
        target_total = target_words * max(len(chapter.get("sections", [])), 1)
        if record["words"] < MIN_LENGTH_RATIO * target_total:
            notes.append(f"The chapter is far too short ({record['words']} words); develop every "
                         f"section to about {target_words} words with examples and concrete steps.")
        try:
            review = _review_chapter(chapter, book=ctx.ebook_dict, chapter_index=i,
                                     words_per_section=target_words, language=ctx.language,
                                     provider=ctx.provider, kind=ctx.kind)
            record["score"] = review["score"]
            if review["score"] < REVIEW_MIN_SCORE:
                notes.extend(review["issues"])
        except BudgetExceeded:
            raise
        except Exception as e:
            logger.warning(f"  Ch{i+1}: review skipped ({e})")

        if notes:
            try:
                chapter = _write_chapter(
                    chapter, book=ctx.ebook_dict, chapter_index=i, research_suggestions=research,
                    previous_summaries=previous_summaries, words_per_section=target_words,
                    brief=brief, language=ctx.language, revision_notes=notes, provider=ctx.provider,
                    kind=ctx.kind,
                )
                record.update(revised=True, words=_word_count(chapter), notes=notes)
                logger.info(f"  Ch{i+1}: revised after review ({record['words']} words)")
            except BudgetExceeded:
                raise
            except Exception as e:
                logger.warning(f"  Ch{i+1}: revision failed, keeping first version ({e})")
        ctx.chapter_reviews.append(record)
        return chapter


def _rebuild_document(ebook_dict: dict) -> ContentBlock:
    """Rebuild ContentBlock tree from updated ebook_dict."""
    doc = ContentBlock(type="document", data={
        "title": ebook_dict.get("title", ""),
        "subtitle": ebook_dict.get("subtitle", ""),
        "author": ebook_dict.get("author", ""),
        "topic": ebook_dict.get("topic", "general"),
        "tone": ebook_dict.get("tone", "professional"),
        "audience": ebook_dict.get("audience", ""),
        "summary": ebook_dict.get("summary", ""),
    })
    for ci, ch in enumerate(ebook_dict.get("chapters", [])):
        chapter = ContentBlock(
            type="chapter",
            data={
                "title": ch.get("title", f"Chapter {ci+1}"),
                "introduction": ch.get("introduction", ""),
                "key_takeaway": ch.get("key_takeaway", ""),
            },
            meta={"index": ci},
        )
        for si, sec in enumerate(ch.get("sections", [])):
            section = ContentBlock(
                type="section",
                data={"heading": sec.get("heading", "")},
                meta={"index": si},
            )
            section.add(ContentBlock(
                type="paragraph",
                data={"text": sec.get("content", "")},
            ))
            chapter.add(section)
        doc.add(chapter)
    conclusion = ebook_dict.get("conclusion", {})
    doc.add(ContentBlock(type="conclusion", data={
        "title": conclusion.get("title", "Conclusion"),
        "content": conclusion.get("content", ""),
    }))
    return doc
