"""The quality gate (claims against sources, repeats, leftovers) and chapters written side by side."""
import threading
import time

import pytest
from test_course_pipeline import fake_llm, good_day, make_ctx, src

from backend.agents import course_agents, editorial_agent, qa_agent
from backend.core import checkpoint, course_engine, course_gen, quality
from backend.core.cost_tracker import BudgetExceeded as _CostBudgetExceeded  # noqa: F401  (only the class the agents import is used below)
from backend.core.course_gen import BudgetExceeded
from backend.orchestrator import Orchestrator, orchestrator
from backend.orchestrator.agent import PipelineContext

JOB = "quality-job-0001"
CLAIM = "Exactly 83% of online shops already use webhooks."


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_CHECKPOINT_DIR", str(tmp_path / "checkpoints"))
    for name in ("update_job", "update_progress"):
        monkeypatch.setattr(orchestrator, name, lambda *a, **k: None)
    monkeypatch.setattr(orchestrator, "is_cancelled", lambda job_id: False)
    for module in (course_agents, editorial_agent):
        monkeypatch.setattr(module, "update_job", lambda *a, **k: None)
        monkeypatch.setattr(module, "is_cancelled", lambda job_id: False)
    monkeypatch.setattr(editorial_agent, "REVIEW_ENABLED", False)


# ------------------------------------------------------------------ plain-code checks

PARA = ("Webhooks let one system tell another the moment something happens, so the second system does not have to ask over and over "
        "whether anything changed, which saves requests and delivers the news faster.")


def test_a_paragraph_repeated_between_two_units_is_found_but_not_within_one():
    units = [("Chapter 1", PARA + "\n\nSomething only the first chapter says, with enough words to count as a paragraph of its own here today."),
             ("Chapter 2", "A different opening paragraph that talks about signatures and secrets and how to check them before trusting a request.\n\n" + PARA.replace("saves", "spares")),
             ("Chapter 3", PARA + "\n\n" + PARA)]
    found = quality.repeated_passages(units)
    assert {(r["a"], r["b"]) for r in found} >= {("Chapter 1", "Chapter 2"), ("Chapter 1", "Chapter 3"), ("Chapter 2", "Chapter 3")}
    assert all(r["a"] != r["b"] for r in found)
    assert quality.repeated_passages([("A", "Short line."), ("B", "Short line.")]) == []


def test_plain_leftovers_are_named():
    found = quality.static_issues([("Day 1", "Fine text [S1]."), ("Day 2", "Lorem ipsum dolor sit amet."), ("Day 3", "A **bold start never closed"),
                                   ("Day 4", "Cites a ghost [S9] and a real one [S1].")], {"S1"})
    assert [(f["where"], f["issue"].split(":")[0]) for f in found] == [("Day 2", "placeholder text left in"), ("Day 3", "unbalanced bold markers (**)"),
                                                                        ("Day 4", "cites a source that does not exist")]


def test_a_day_is_read_as_the_learner_reads_it():
    text = quality.unit_text(good_day(1))
    assert "Where does this show up" in text and "Open your project" in text and "Push beats polling" in text


# ------------------------------------------------------------------ the course quality step

def gather(qs, lang, user_urls=None):
    return [src(1), src(2, provider="author")]


def start(**kw):
    ctx = make_ctx(job_id=JOB, course_format="program", chapters="5", **kw)
    checkpoint.save_inputs(JOB, {"job_id": JOB, "text": ctx.text})
    return ctx


def llm_with_a_claim(prompts, rewrite_fails=False):
    """Day 2 states a number the sources do not back; the checker says so; a rewrite is clean (or fails)."""
    base = fake_llm()
    seen = {"day2": 0}

    def llm(system, user, max_tokens=6000):
        prompts.append((system, user))
        if "careful fact-checker" in system:
            return {"unsupported": [{"claim": CLAIM, "why": "no source gives this figure"}]} if CLAIM in user else {"unsupported": []}
        if "writing one day" in system and "Day 2 of" in user:
            seen["day2"] += 1
            if seen["day2"] == 1:
                day = good_day(2)
                day["sections"][0]["body"] += "\n\n" + CLAIM
                return day
            if rewrite_fails:
                raise RuntimeError("model unavailable")
            return {**good_day(2), "title": "Theme 2 rewritten"}
        return base(system, user, max_tokens)
    return llm


def test_a_day_with_an_unsupported_claim_is_rewritten_once_and_reported():
    prompts = []
    result = Orchestrator(course_agents.course_pipeline(llm_with_a_claim(prompts), gather)).run(start())
    assert result.error is None
    review = result.course["quality"]
    days = [d for p in result.course["phases"] for d in p["lessons"]]
    assert review["checked"] == 5 and review["fixed"] == 1 and review["static"] == [] and review["sensitive"] is False
    assert review["unsupported"] == [{"unit": "Day 2", "title": "Theme 2", "claim": CLAIM, "why": "no source gives this figure", "fixed": True}]
    assert days[1]["title"] == "Theme 2 rewritten" and CLAIM not in quality.unit_text(days[1])
    rewrites = [u for s, u in prompts if "writing one day" in s and "Day 2 of" in u and "AUTHOR'S REQUEST" in u]
    assert len(rewrites) == 1 and CLAIM in rewrites[0] and "Remove or rephrase" in rewrites[0]
    assert [d["title"] for i, d in enumerate(days) if i != 1] == [f"Theme {i}" for i in (1, 3, 4, 5)]   # nothing else was touched
    # the report is for the author: the learners' page does not carry it
    html = course_engine.build_course_html(result.course)
    assert CLAIM not in html and "no source gives this figure" not in html


def test_a_failed_rewrite_keeps_the_day_and_says_so():
    result = Orchestrator(course_agents.course_pipeline(llm_with_a_claim([], rewrite_fails=True), gather)).run(start())
    assert result.error is None
    assert result.course["quality"]["fixed"] == 0 and result.course["quality"]["unsupported"][0]["fixed"] is False
    assert CLAIM in quality.unit_text([d for p in result.course["phases"] for d in p["lessons"]][1])   # the first version stays


def test_a_checker_that_breaks_never_costs_the_course():
    def checker(system, user, max_tokens=2500):
        raise RuntimeError("provider down")
    result = Orchestrator(course_agents.course_pipeline(fake_llm(), gather, checker)).run(start())
    assert result.error is None and course_gen.validate_course(result.course) == []
    assert result.course["quality"]["unchecked"] == 5 and result.course["quality"]["unsupported"] == []


def test_the_budget_stops_the_review_instead_of_skipping_it():
    def checker(system, user, max_tokens=2500):
        raise BudgetExceeded("Dzienny limit kosztów AI wyczerpany")
    result = Orchestrator(course_agents.course_pipeline(fake_llm(), gather, checker)).run(start())
    assert result.error and "limit kosztów" in result.error


def test_claim_checks_of_finished_days_are_not_paid_for_again_on_resume():
    prompts = []
    llm = llm_with_a_claim(prompts)
    counted = lambda: sum(1 for s, _ in prompts if "fact-checker" in s)  # noqa: E731
    calls = {"n": 0}

    def flaky(system, user, max_tokens=6000):
        if "careful fact-checker" in system:
            calls["n"] += 1
            if calls["n"] == 4:
                raise BudgetExceeded("Dzienny limit kosztów AI wyczerpany")
        return llm(system, user, max_tokens)

    first = Orchestrator(course_agents.course_pipeline(flaky, gather)).run(start())
    assert first.error and checkpoint.items(JOB, "claims")
    done = len(checkpoint.items(JOB, "claims"))
    before = counted()
    second = Orchestrator(course_agents.course_pipeline(llm, gather)).run(make_ctx(job_id=JOB, course_format="program", chapters="5"))
    assert second.error is None and counted() - before == 5 - done


# ------------------------------------------------------------------ chapters written side by side

def outline_book(n=6):
    return {"title": "Book", "topic": "general", "conclusion": {},
            "chapters": [{"title": f"Chapter {i + 1}", "introduction": f"intro {i + 1}", "key_takeaway": f"takeaway {i + 1}",
                          "sections": [{"heading": "h", "content": "draft"}]} for i in range(n)]}


def book_ctx(n=6, kind="guide", job="book-job-0001"):
    ctx = PipelineContext(job_id=job, text="x", style="m", kind=kind, language="English")
    ctx.ebook_dict = outline_book(n)
    return ctx


def fake_writer(log, delay=0.0, fail_on=None, budget_on=None):
    state = {"now": 0, "peak": 0}
    lock = threading.Lock()

    def write(ch, **kw):
        with lock:
            state["now"] += 1
            state["peak"] = max(state["peak"], state["now"])
        try:
            log.append((ch["title"], list(kw["previous_summaries"])))
            time.sleep(delay)
            if fail_on == ch["title"]:
                raise ValueError("bad json")
            if budget_on == ch["title"]:
                raise BudgetExceeded("Dzienny limit kosztów AI wyczerpany")
            return dict(ch, key_takeaway="learned " + ch["title"], sections=[{"heading": "h", "content": "written " + ch["title"]}])
        finally:
            with lock:
                state["now"] -= 1
    write.state = state
    return write


def test_non_fiction_chapters_are_written_at_the_same_time_and_stay_in_order(monkeypatch):
    log = []
    writer = fake_writer(log, delay=0.05)
    monkeypatch.setattr(editorial_agent, "_write_chapter", writer)
    ctx = editorial_agent.EditorialAgent().run(book_ctx(6))
    assert writer.state["peak"] > 1
    assert [c["title"] for c in ctx.ebook_dict["chapters"]] == [f"Chapter {i + 1}" for i in range(6)]
    assert all(c["sections"][0]["content"] == f"written {c['title']}" for c in ctx.ebook_dict["chapters"])
    by_title = dict(log)
    assert by_title["Chapter 1"] == [] and by_title["Chapter 3"] == ["Ch1 Chapter 1: takeaway 1", "Ch2 Chapter 2: takeaway 2"]   # told what the earlier ones are planned to cover
    assert ctx.progress == 53


def test_one_worker_writes_one_after_another_with_what_was_actually_written(monkeypatch):
    log = []
    monkeypatch.setattr(editorial_agent.EditorialAgent, "WORKERS", 1)
    monkeypatch.setattr(editorial_agent, "_write_chapter", fake_writer(log))
    editorial_agent.EditorialAgent().run(book_ctx(3))
    assert [t for t, _ in log] == ["Chapter 1", "Chapter 2", "Chapter 3"]
    assert log[2][1] == ["Ch1 Chapter 1: learned Chapter 1", "Ch2 Chapter 2: learned Chapter 2"]


def test_fiction_stays_sequential(monkeypatch):
    log = []
    writer = fake_writer(log, delay=0.02)
    monkeypatch.setattr(editorial_agent, "_write_chapter", writer)
    editorial_agent.EditorialAgent().run(book_ctx(4, kind="novel"))
    assert writer.state["peak"] == 1 and [t for t, _ in log] == [f"Chapter {i + 1}" for i in range(4)]
    assert log[3][1][-1] == "Ch3 Chapter 3: learned Chapter 3"


def test_a_chapter_that_cannot_be_written_keeps_its_outline_draft_and_is_not_checkpointed(monkeypatch):
    monkeypatch.setattr(editorial_agent, "_write_chapter", fake_writer([], fail_on="Chapter 2"))
    ctx = book_ctx(4)
    checkpoint.save_inputs(ctx.job_id, {"job_id": ctx.job_id, "text": "x"})
    ctx = editorial_agent.EditorialAgent().run(ctx)
    chapters = ctx.ebook_dict["chapters"]
    assert chapters[1]["sections"][0]["content"] == "draft" and chapters[0]["sections"][0]["content"].startswith("written")
    assert sorted(checkpoint.items(ctx.job_id, "chapters")) == [0, 2, 3]   # a resume retries chapter 2


def test_a_resumed_book_writes_only_the_missing_chapters(monkeypatch):
    log = []
    ctx = book_ctx(5)
    checkpoint.save_inputs(ctx.job_id, {"job_id": ctx.job_id, "text": "x"})
    monkeypatch.setattr(editorial_agent, "_write_chapter", fake_writer(log, budget_on="Chapter 4"))
    with pytest.raises(BudgetExceeded):
        editorial_agent.EditorialAgent().run(ctx)
    kept = checkpoint.items(ctx.job_id, "chapters")
    assert kept and 3 not in kept
    log.clear()
    monkeypatch.setattr(editorial_agent, "_write_chapter", fake_writer(log))
    again = editorial_agent.EditorialAgent().run(book_ctx(5))
    assert sorted(t for t, _ in log) == sorted(f"Chapter {i + 1}" for i in range(5) if i not in kept)
    assert all(c["sections"][0]["content"].startswith("written") for c in again.ebook_dict["chapters"])


def test_the_budget_is_not_swallowed_into_an_outline_draft(monkeypatch):
    monkeypatch.setattr(editorial_agent, "_write_chapter", fake_writer([], budget_on="Chapter 1"))
    with pytest.raises(BudgetExceeded):
        editorial_agent.EditorialAgent().run(book_ctx(3))


def test_qa_names_paragraphs_repeated_between_chapters_and_leftovers():
    ctx = book_ctx(3)
    for ch in ctx.ebook_dict["chapters"][:2]:
        ch["sections"] = [{"heading": "h", "content": PARA}]
    ctx.ebook_dict["chapters"][2]["sections"] = [{"heading": "h", "content": "Lorem ipsum dolor sit amet"}]
    issues = qa_agent._text_issues(ctx)
    assert {i["type"] for i in issues} == {"repetition", "content"}
    assert any("chapter 1 / chapter 2" == i["location"] for i in issues) and any("placeholder" in i["description"] for i in issues)
