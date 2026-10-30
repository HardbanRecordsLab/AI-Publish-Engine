"""A job that stops half way is resumed, not re-run; a course can wait for the author's approval of its outline; one day can be rewritten."""
import json
import re

import pytest
from fastapi.testclient import TestClient
from test_course_pipeline import fake_llm, good_day, make_ctx, src

from backend.agents import course_agents
from backend.core import checkpoint, course_gen, webresearch
from backend.core.course_gen import BudgetExceeded   # not cost_tracker.BudgetExceeded: another test reloads that module and the class changes
from backend.core.jobs import create_job, get_job, update_job
from backend.orchestrator import Orchestrator, orchestrator
from backend.orchestrator.agent import AwaitingApproval, BaseAgent, PipelineContext

JOB = "resume-job-0001"


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_CHECKPOINT_DIR", str(tmp_path / "checkpoints"))
    for name in ("update_job", "update_progress"):
        monkeypatch.setattr(orchestrator, name, lambda *a, **k: None)
    monkeypatch.setattr(orchestrator, "is_cancelled", lambda job_id: False)
    monkeypatch.setattr(course_agents, "update_job", lambda *a, **k: None)
    monkeypatch.setattr(course_agents, "is_cancelled", lambda job_id: False)


def gather(qs, lang, user_urls=None):
    return [src(1), src(2, provider="author")]


def start(job_id=JOB, **kw):
    ctx = make_ctx(job_id=job_id, course_format="program", chapters="6", **kw)
    checkpoint.save_inputs(job_id, {"job_id": job_id, "text": ctx.text})
    return ctx


# ------------------------------------------------------------------ the checkpoint store

def test_the_store_keeps_stages_and_items_and_refuses_odd_ids():
    checkpoint.save_inputs(JOB, {"text": "brief"})
    checkpoint.save_inputs(JOB, {"text": "ignored: inputs are written once"})
    checkpoint.save_stage(JOB, "outline", {"title": "T"})
    checkpoint.save_item(JOB, "lessons", 2, {"title": "two"})
    checkpoint.save_item(JOB, "lessons", 0, {"title": "zero"})
    assert checkpoint.inputs(JOB) == {"text": "brief"} and checkpoint.stage(JOB, "outline") == {"title": "T"}
    assert checkpoint.items(JOB, "lessons") == {0: {"title": "zero"}, 2: {"title": "two"}} and checkpoint.stage(JOB, "nope", 7) == 7
    for bad in ("../x", "a/b", "x", "", "a" * 90):
        assert not checkpoint.has(bad)
        with pytest.raises(ValueError):
            checkpoint.save_inputs(bad, {})
    checkpoint.clear(JOB)
    assert not checkpoint.has(JOB) and checkpoint.items(JOB, "lessons") == {}


def test_old_checkpoints_are_purged():
    import os
    import time
    checkpoint.save_inputs(JOB, {"text": "brief"})
    old = time.time() - 40 * 86400
    for p in checkpoint._dir().glob("*.json"):
        os.utime(p, (old, old))
    checkpoint.save_inputs("fresh-job-0002", {"text": "new"})
    assert checkpoint.purge_older_than(30) == 1 and checkpoint.has("fresh-job-0002") and not checkpoint.has(JOB)


# ------------------------------------------------------------------ resuming

class Step(BaseAgent):
    def __init__(self, name, field, fail_first=False):
        super().__init__(name)
        self.field, self.fail_first, self.runs = field, fail_first, 0

    def run(self, ctx):
        self.runs += 1
        if self.fail_first and self.runs == 1:
            raise RuntimeError("provider down")
        ctx.research = {**ctx.research, self.field: True}
        ctx.set_progress(ctx.progress + 10)
        return ctx


def test_a_resumed_job_continues_after_the_last_finished_agent():
    a, b, c = Step("A", "a"), Step("B", "b", fail_first=True), Step("C", "c")
    first = Orchestrator([a, b, c]).run(start())
    assert first.error == "provider down" and (a.runs, b.runs, c.runs) == (1, 1, 0)
    again = Orchestrator([a, b, c]).run(make_ctx(job_id=JOB, course_format="program"))
    assert again.error is None and (a.runs, b.runs, c.runs) == (1, 2, 1)
    assert again.research == {"a": True, "b": True, "c": True} and again.progress == 30


def test_a_job_without_stored_inputs_is_not_checkpointed():
    a = Step("A", "a")
    Orchestrator([a]).run(make_ctx(job_id="job-x"))
    assert not list(checkpoint._dir().glob("*.json"))


def test_the_snapshot_leaves_out_the_brief_and_restores_it():
    ctx = start()
    ctx.course = {"outline": {"title": "T", "_brief": ctx.text, "phases": []}}
    snap = ctx.snapshot()
    assert "text" not in snap and "_brief" not in snap["course"]["outline"]
    assert ctx.restored(snap).course["outline"]["_brief"] == ctx.text


def day_calls(prompts):
    return [p for p in prompts if re.search(r"Day \d+ of", p)]


def test_a_resumed_course_does_not_pay_for_finished_days_again(monkeypatch):
    prompts, base = [], fake_llm()
    state = {"fail": True}

    def llm(system, user, max_tokens=6000):
        prompts.append(user)
        if state["fail"] and "Day 4 of" in user:
            raise RuntimeError("provider down")
        return base(system, user, max_tokens)

    first = Orchestrator(course_agents.course_pipeline(llm, gather)).run(start())
    assert first.error and "Day 4" in first.error
    kept = checkpoint.items(JOB, "lessons")
    assert kept and 3 not in kept and all(v["title"] for v in kept.values())

    state["fail"] = False
    before = len(day_calls(prompts))
    second = Orchestrator(course_agents.course_pipeline(llm, gather)).run(make_ctx(job_id=JOB, course_format="program", chapters="6"))
    assert second.error is None and course_gen.validate_course(second.course) == []
    assert len(day_calls(prompts)) - before == 6 - len(kept)   # only the missing days were written
    assert sum(len(p["lessons"]) for p in second.course["phases"]) == 6


# ------------------------------------------------------------------ outline review

def test_the_course_waits_for_approval_and_writes_the_edited_outline():
    prompts = []
    llm = fake_llm(prompts=prompts)
    first = Orchestrator(course_agents.course_pipeline(llm, gather)).run(start(review_outline=True))
    assert first.awaiting_approval and first.error is None
    assert not day_calls(prompts)   # nothing was written yet
    outline = checkpoint.stage(JOB, "outline")
    assert "_brief" not in outline and sum(len(p["lessons"]) for p in outline["phases"]) == 6

    edit = course_gen.public_outline(outline)
    edit["title"] = "My own title"
    edit["phases"][1]["lessons"].pop()                    # drop the last day
    edit["phases"][0]["lessons"][0]["title"] = "Day 1: A better start"
    checkpoint.save_stage(JOB, "outline", course_gen.apply_outline_edit(outline, edit))
    checkpoint.save_stage(JOB, "outline_approved", True)

    second = Orchestrator(course_agents.course_pipeline(llm, gather)).run(make_ctx(job_id=JOB, course_format="program", chapters="6", review_outline=True))
    assert second.error is None and not second.awaiting_approval
    days = [d for p in second.course["phases"] for d in p["lessons"]]
    assert len(days) == 5 and second.course["title"] == "My own title"
    assert any("A better start" in p and "Day 1 of 5" in p for p in prompts)   # the edited title reached the writer, without the day label
    assert len(day_calls(prompts)) == 5


def test_without_review_the_course_is_written_straight_away():
    first = Orchestrator(course_agents.course_pipeline(fake_llm(), gather)).run(start())
    assert not first.awaiting_approval and first.error is None and first.course["phases"]


def outline_of(days=6):
    ctx = start()
    for agent in course_agents.course_pipeline(fake_llm(), gather)[:2]:
        ctx = agent.run(ctx)
    return ctx.course["outline"]


def test_outline_edits_keep_what_the_writer_relies_on():
    outline = outline_of()
    edit = course_gen.public_outline(outline)
    edit["phases"][0]["lessons"][0]["title"] = "Dzień 3: Nowy początek"
    out = course_gen.apply_outline_edit(outline, edit)
    assert out["phases"][0]["lessons"][0]["title"] == "Nowy początek"
    assert all(out[k] == outline[k] for k in ("format", "sensitive", "level", "labels", "session_kind"))


@pytest.mark.parametrize("mutate, message", [
    (lambda e: e["phases"].clear(), "co najmniej jedną fazę"),
    (lambda e: [ph["lessons"].clear() for ph in e["phases"]], "od 3 do 60"),
    (lambda e: e["phases"][0]["lessons"][0].update(title="  "), "potrzebuje tytułu"),
    (lambda e: e["phases"][0]["lessons"].extend({"title": f"x{i}"} for i in range(70)), "od 3 do 60"),
])
def test_outline_edits_are_validated_with_a_message_for_the_author(mutate, message):
    outline = outline_of()
    edit = course_gen.public_outline(outline)
    mutate(edit)
    with pytest.raises(ValueError, match=message):
        course_gen.apply_outline_edit(outline, edit)


# ------------------------------------------------------------------ the daily budget

def test_the_budget_error_is_not_swallowed_into_a_hollow_day():
    def llm(system, user, max_tokens=6000):
        raise BudgetExceeded("limit")
    outline = outline_of()
    spec = outline["phases"][0]["lessons"][0]
    with pytest.raises(BudgetExceeded):
        course_gen.write_day(llm, outline, spec, 0, 6, [src(1)], language="English", tone="")
    with pytest.raises(BudgetExceeded):
        course_gen.write_frame(llm, outline, [good_day(1)] * 6, language="English", tone="", audience="", brief="")


def test_a_job_stopped_by_the_budget_keeps_its_days():
    base = fake_llm()

    def llm(system, user, max_tokens=6000):
        if "Day 5 of" in user:
            raise BudgetExceeded("Dzienny limit kosztów AI wyczerpany")
        return base(system, user, max_tokens)

    result = Orchestrator(course_agents.course_pipeline(llm, gather)).run(start())
    assert result.error and "limit kosztów" in result.error
    assert checkpoint.items(JOB, "lessons") and 4 not in checkpoint.items(JOB, "lessons")


# ------------------------------------------------------------------ rewriting one day

def test_one_day_is_rewritten_with_the_authors_note_and_the_rest_is_untouched():
    prompts, base = [], fake_llm()
    ctx = start()
    for agent in course_agents.course_pipeline(fake_llm(), gather)[:5]:
        ctx = agent.run(ctx)
    outline, lessons = ctx.course["outline"], ctx.course["lessons"]
    sources = [webresearch.Source(**s) for s in ctx.web_sources]
    course = course_gen.assemble_course(outline, lessons, sources, language="English", frame=ctx.course["frame"])

    def llm(system, user, max_tokens=6000):
        prompts.append(user)
        if "writing one day" in system:
            return {**good_day(3), "title": "Rewritten day"}
        return base(system, user, max_tokens)

    new = course_gen.rewrite_unit(llm, outline, course, 2, sources, note="Add a real example from a small shop", language="English", tone="")
    old_days = [d for p in course["phases"] for d in p["lessons"]]
    new_days = [d for p in new["phases"] for d in p["lessons"]]
    assert [d["title"] for d in new_days][2] == "Rewritten day"
    assert [d for i, d in enumerate(new_days) if i != 2] == [d for i, d in enumerate(old_days) if i != 2]
    assert len(prompts) == 1 and "Add a real example from a small shop" in prompts[0] and "current version of this unit" in prompts[0]
    assert new["frame"] == course["frame"] and course_gen.validate_course(new) == []
    with pytest.raises(ValueError):
        course_gen.rewrite_unit(llm, outline, course, 99, sources, note="x" * 10, language="English", tone="")


# ------------------------------------------------------------------ the HTTP side

@pytest.fixture
def api(monkeypatch):
    from backend.main import app
    from backend.routers import jobs as jobs_router
    from backend.routers.auth import require_admin
    started = []
    monkeypatch.setattr(jobs_router, "_start", lambda ctx: started.append(ctx))
    app.dependency_overrides[require_admin] = lambda: True
    yield TestClient(app), started
    app.dependency_overrides.pop(require_admin, None)


def new_job(status, **inputs):
    job_id = create_job("minimal", "interactive-course")
    update_job(job_id, status, 40)
    if inputs:
        checkpoint.save_inputs(job_id, {"job_id": job_id, "text": "brief", "content_type": "interactive-course", **inputs})
    return job_id


def test_a_failed_job_is_resumable_and_resuming_restarts_it_with_the_same_inputs(api):
    client, started = api
    job_id = new_job("failed", language="Polish")
    assert client.get(f"/api/status/{job_id}").json()["resumable"] is True
    r = client.post(f"/api/jobs/{job_id}/resume")
    assert r.status_code == 200 and started[0]["language"] == "Polish" and started[0]["job_id"] == job_id
    assert get_job(job_id)["status"] == "queued" and get_job(job_id)["progress"] == 40
    assert client.post(f"/api/admin/jobs/{job_id}/retry").status_code == 200   # the admin button resumes too, it used to do nothing


def test_resume_refuses_what_cannot_be_resumed(api):
    client, started = api
    assert client.post(f"/api/jobs/{new_job('done', language='x')}/resume").status_code == 409
    old = new_job("failed")   # started before inputs were stored
    assert client.get(f"/api/status/{old}").json()["resumable"] is False
    r = client.post(f"/api/jobs/{old}/resume")
    assert r.status_code == 409 and "nie ma zapisanych danych" in r.json()["error"] and not started
    assert client.post("/api/jobs/does-not-exist/resume").status_code == 409


def test_outline_review_over_http(api):
    client, started = api
    job_id = new_job("awaiting_approval", language="English")
    outline = outline_of()
    checkpoint.save_stage(job_id, "outline", outline)
    got = client.get(f"/api/jobs/{job_id}/outline").json()
    assert got["status"] == "awaiting_approval" and "_brief" not in got["outline"] and not got["approved"]
    assert client.get(f"/api/status/{job_id}").json()["awaiting_approval"] is True

    bad = course_gen.public_outline(outline)
    for ph in bad["phases"]:
        ph["lessons"].clear()
    assert client.put(f"/api/jobs/{job_id}/outline", json=bad).status_code == 400
    good = course_gen.public_outline(outline)
    good["title"] = "Edited title"
    assert client.put(f"/api/jobs/{job_id}/outline", json=good).json()["outline"]["title"] == "Edited title"

    r = client.post(f"/api/jobs/{job_id}/approve", json={})
    assert r.status_code == 200 and checkpoint.stage(job_id, "outline_approved") is True and started[0]["job_id"] == job_id
    assert checkpoint.stage(job_id, "outline")["title"] == "Edited title"
    update_job(job_id, "processing", 30)
    assert client.put(f"/api/jobs/{job_id}/outline", json=good).status_code == 409   # too late to edit
    assert client.post(f"/api/jobs/{job_id}/approve", json={}).status_code == 409


def test_a_day_can_only_be_rewritten_with_a_note_on_a_finished_course(api):
    client, _ = api
    running = new_job("processing", language="English")
    assert client.post(f"/api/jobs/{running}/rewrite", json={"index": 0, "note": "make it longer please"}).status_code == 409
    finished = new_job("done", language="English")
    update_job(finished, "done", 100, book_data=json.dumps({"phases": []}))
    assert client.post(f"/api/jobs/{finished}/rewrite", json={"index": 0, "note": "make it longer please"}).status_code == 409   # no materials kept
    checkpoint.save_stage(finished, "outline", outline_of())
    checkpoint.save_stage(finished, "ctx", {"web_sources": []})
    assert client.get(f"/api/status/{finished}").json()["rewritable"] is True
    assert client.post(f"/api/jobs/{finished}/rewrite", json={"index": "zero", "note": "make it longer please"}).status_code == 400
    assert client.post(f"/api/jobs/{finished}/rewrite", json={"index": 0, "note": "x"}).status_code == 400
    assert client.get(f"/api/jobs/{finished}/rewrite").json() == {"status": "idle"}


def test_the_awaiting_exception_is_an_exception_not_a_failure():
    class Park(BaseAgent):
        def __init__(self):
            super().__init__("Park")

        def run(self, ctx: PipelineContext):
            raise AwaitingApproval()
    ctx = Orchestrator([Park()]).run(start())
    assert ctx.awaiting_approval and ctx.error is None
