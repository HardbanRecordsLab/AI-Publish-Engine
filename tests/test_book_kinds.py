"""Kinds of book (guide, DIY, cookbook, workbook, course, novel, children's):
prompts, pipeline selection, structured blocks and their rendering."""
import json

import pytest

from backend.core import ai
from backend.core.book_kinds import KINDS, get_kind, list_kinds, normalize_blocks
from backend.core.builder import build_ebook_html
from backend.core.export import build_docx, build_epub
from backend.core.publish_validators import validate_epub

DIY_BOOK = {
    "title": "Buda dla psa", "author": "Jan", "language": "Polish", "kind": "diy",
    "chapters": [{
        "title": "Buda", "introduction": "Wstęp.", "key_takeaway": "Mierz dwa razy.",
        "blocks": [
            {"type": "facts", "items": [{"label": "Czas", "value": "4 h"}]},
            {"type": "list", "title": "Materiały", "style": "checklist", "items": ["deski <18 mm>", "wkręty"]},
            {"type": "callout", "kind": "warning", "text": "Używaj okularów."},
            {"type": "quiz", "title": "Sprawdź się", "questions": [{"q": "Ile?", "options": ["1", "2"], "answer": "2"}]},
            {"type": "exercise", "prompt": "Narysuj plan", "lines": 2},
        ],
        "sections": [{"heading": "Cięcie", "content": "Tnij.\n\nMierz.",
                      "blocks": [{"type": "steps", "items": [{"text": "Zmierz", "tip": "dwa razy"}, "Tnij"]}]}],
    }],
    "conclusion": {"content": "Koniec."},
}


class TestKinds:
    def test_catalogue(self):
        assert [k["id"] for k in list_kinds()] == list(KINDS)
        assert {"guide", "diy", "cookbook", "workbook", "course", "novel", "children"} <= set(KINDS)

    def test_unknown_falls_back_to_guide(self):
        assert get_kind(None).id == get_kind("") .id == get_kind("nonsense").id == "guide"
        assert get_kind(" DIY ").id == "diy"

    def test_fiction_skips_nonfiction_steps(self):
        for k in ("novel", "children"):
            spec = get_kind(k)
            assert not (spec.research or spec.structure or spec.fact_check or spec.show_takeaway or spec.glossary)
        assert get_kind("diy").fact_check, "DIY safety advice must still be fact-checked"

    def test_words_per_section(self):
        assert ai.words_per_section("ebook", "novel") > ai.words_per_section("ebook", "guide") > \
            ai.words_per_section("ebook", "children")
        assert ai.words_per_section("landing-page", "novel") == ai.words_per_section("landing-page", "guide")
        assert ai.words_per_section("ebook") == 550

    def test_endpoint(self):
        from fastapi.testclient import TestClient

        from backend.main import app
        data = TestClient(app).get("/api/book-kinds").json()
        assert {k["id"] for k in data} == set(KINDS) and all(k["label"] and k["description"] for k in data)


class TestNormalizeBlocks:
    def test_valid_blocks_pass_and_junk_is_dropped(self):
        out = normalize_blocks([
            {"type": "list", "items": ["a", "", " b "], "style": "weird"},
            {"type": "evil", "items": ["x"]}, "junk", None, {"type": "steps", "items": []},
            {"type": "facts", "items": [{"label": "T", "value": "1h"}, {"label": "", "value": "z"}]},
            {"type": "callout", "kind": "danger", "text": "careful"},
            {"type": "exercise", "prompt": "p", "lines": 99},
        ])
        assert [b["type"] for b in out] == ["list", "facts", "callout", "exercise"]
        assert out[0]["items"] == ["a", "b"] and out[0]["style"] == "bullets"
        assert out[2]["kind"] == "note" and out[3]["lines"] == 12

    def test_non_list_and_idempotent(self):
        assert normalize_blocks(None) == normalize_blocks("x") == normalize_blocks({}) == []
        once = normalize_blocks(DIY_BOOK["chapters"][0]["blocks"])
        assert normalize_blocks(once) == once

    def test_bounds(self):
        big = normalize_blocks([{"type": "list", "items": [str(i) for i in range(500)]}])
        assert len(big[0]["items"]) == 40


class _Capture:
    def __init__(self, response):
        self.response, self.calls = response, []

    def __call__(self, system, user, *a, **kw):
        self.calls.append((system, user))
        return self.response


class TestPrompts:
    def test_novel_outline_asks_for_story_bible(self, monkeypatch):
        cap = _Capture({"title": "t", "chapters": []})
        monkeypatch.setattr(ai, "_writer_json", cap)
        ai.analyze_text("brief", kind="novel", language="Polish")
        system, user = cap.calls[0]
        assert "novelist" in system and '"story"' in user and "FICTION" in user and "8-12 chapters" in user

    def test_guide_outline_is_the_original(self, monkeypatch):
        cap = _Capture({"title": "t", "chapters": []})
        monkeypatch.setattr(ai, "_writer_json", cap)
        ai.analyze_text("brief")
        system, user = cap.calls[0]
        assert system.startswith("You are an ebook author") and '"story"' not in user and "4-6 chapters" in user

    def test_explicit_chapter_count_beats_kind_default(self, monkeypatch):
        cap = _Capture({"title": "t", "chapters": []})
        monkeypatch.setattr(ai, "_writer_json", cap)
        ai.analyze_text("brief", kind="novel", chapters="5")
        assert "exactly 5 chapters" in cap.calls[0][1]

    def test_diy_chapter_gets_blocks_and_merges_them(self, monkeypatch):
        written = {"title": "B", "sections": [{"heading": "h", "content": "c", "blocks": [
            {"type": "steps", "items": ["one"]}, {"type": "evil"}]}],
            "blocks": [{"type": "facts", "items": [{"label": "t", "value": "1h"}]}]}
        cap = _Capture(written)
        monkeypatch.setattr(ai, "_writer_json", cap)
        result = ai.write_chapter({"title": "B", "sections": [{"heading": "h", "content": "d"}]},
                                  book={"chapters": [{"title": "B"}]}, chapter_index=0, kind="diy")
        assert '"blocks"' in cap.calls[0][1] and "warning" in cap.calls[0][1]
        assert [b["type"] for b in result["sections"][0]["blocks"]] == ["steps"]
        assert result["blocks"][0]["type"] == "facts"

    def test_guide_chapter_has_no_blocks(self, monkeypatch):
        cap = _Capture({"title": "B", "sections": [{"heading": "h", "content": "c", "blocks": [{"type": "list", "items": ["x"]}]}]})
        monkeypatch.setattr(ai, "_writer_json", cap)
        result = ai.write_chapter({"title": "B", "sections": []}, book={}, chapter_index=0)
        assert '"blocks"' not in cap.calls[0][1] and "blocks" not in result["sections"][0]
        assert "Teach, don't summarize" in cap.calls[0][1]

    def test_novel_chapter_uses_story_bible_and_returns_recap(self, monkeypatch):
        cap = _Capture({"title": "I", "sections": [{"heading": "", "content": "Scena."}], "recap": " Ala odchodzi. "})
        monkeypatch.setattr(ai, "_writer_json", cap)
        book = {"story": {"premise": "Ucieczka", "point_of_view": "first person past",
                          "characters": [{"name": "Ala", "role": "hero", "description": "d", "arc": "a"}]},
                "chapters": [{"title": "I"}]}
        result = ai.write_chapter({"title": "I", "sections": [{"heading": "", "content": "b"}]},
                                  book=book, chapter_index=0, kind="novel")
        user = cap.calls[0][1]
        assert "STORY BIBLE" in user and "Ala" in user and "first person past" in user
        assert "Teach, don't summarize" not in user and '"recap"' in user
        assert result["recap"] == "Ala odchodzi."

    def test_review_uses_kind_criteria_and_sees_blocks(self, monkeypatch):
        cap = _Capture({"score": 7, "issues": []})
        monkeypatch.setattr(ai, "_writer_json", cap)
        ai.review_chapter(DIY_BOOK["chapters"][0], book=DIY_BOOK, chapter_index=0, kind="diy")
        system, user = cap.calls[0]
        assert "project manual" in system.lower() or "diy" in system.lower()
        assert "safety" in user and "Materiały" in user and "Zmierz" in user
        cap2 = _Capture({"score": 7, "issues": []})
        monkeypatch.setattr(ai, "_writer_json", cap2)
        ai.review_chapter({"sections": [{"heading": "", "content": "x"}]}, book={}, chapter_index=0, kind="novel")
        assert "continuity" in cap2.calls[0][1] and "concreteness" not in cap2.calls[0][1]


class TestPipeline:
    def test_agents_per_kind(self):
        from backend.worker import pipeline_agents
        names = lambda k: [a.name for a in pipeline_agents(k)]  # noqa: E731
        assert "FactCheckAgent" in names("guide") and "ResearchAgent" in names("guide")
        assert "StructureAgent" in names("guide")
        assert not {"ResearchAgent", "StructureAgent", "FactCheckAgent"} & set(names("novel"))
        assert "FactCheckAgent" in names("diy") and "ResearchAgent" not in names("diy")
        assert names("novel")[0] == "AnalysisAgent" and "EditorialAgent" in names("novel")

    def test_analysis_keeps_kind_and_story(self, monkeypatch):
        from backend.agents import analysis_agent
        from backend.orchestrator.agent import PipelineContext
        monkeypatch.setattr(analysis_agent, "_analyze_text", lambda *a, **k: {
            "title": "T", "story": {"premise": "p"}, "chapters": [{"title": "c", "introduction": "beat", "sections": []}],
            "conclusion": {}})
        ctx = analysis_agent.AnalysisAgent().run(PipelineContext(job_id="t", text="x", style="m", kind="novel"))
        assert ctx.ebook_dict["kind"] == "novel" and ctx.ebook_dict["story"] == {"premise": "p"}

    def test_qa_does_not_flag_missing_intro_for_fiction(self):
        from backend.agents.qa_agent import _local_checks
        from backend.orchestrator.agent import PipelineContext
        ctx = PipelineContext(job_id="t", text="x", style="m", kind="novel")
        ctx.ebook_dict = {"chapters": [{"title": "I", "introduction": "", "key_takeaway": "",
                                         "sections": [{"heading": "", "content": "Scena."}]}],
                          "conclusion": {"content": "k"}}
        assert _local_checks(ctx) == []
        ctx.kind = "guide"
        assert len(_local_checks(ctx)) == 2

    def test_generate_passes_kind(self, monkeypatch):
        from fastapi.testclient import TestClient

        from backend.main import app
        from backend.routers import jobs
        from backend.routers.auth import require_admin
        queued = []
        monkeypatch.setattr(jobs, "_queue_job", lambda *a, **k: queued.append(k))
        app.dependency_overrides[require_admin] = lambda: None
        try:
            client = TestClient(app)
            client.post("/api/generate", data={"topic": "Buda", "kind": "diy"})
            client.post("/api/generate", data={"topic": "Buda", "kind": "bogus"})
        finally:
            app.dependency_overrides.pop(require_admin, None)
        assert [q["kind"] for q in queued] == ["diy", "bogus"]  # normalised when the job starts

    def test_queue_normalises_kind(self, monkeypatch):
        from backend import worker
        from backend.routers import jobs
        seen = {}

        async def fake_process(ctx):
            seen.update(ctx)

        monkeypatch.setattr(worker, "process_job", fake_process)
        jobs._queue_job("j", "text", "minimal", kind="bogus")
        import time
        for _ in range(50):
            if seen:
                break
            time.sleep(0.05)
        assert seen["kind"] == "guide"


class TestRendering:
    def test_diy_html(self):
        html = build_ebook_html(DIY_BOOK, "minimal", [])
        for needle in ("rb-facts", "Materiały", "&#9744;", "deski &lt;18 mm&gt;", "Uwaga", "rb-steps",
                       "Wskazówka: dwa razy", "Odpowiedź: 2", "kind-diy", "Narysuj plan"):
            assert needle in html, needle
        assert "Najważniejsze" not in html, "DIY shows no key-takeaway box"

    def test_fiction_hides_beats_and_breaks_scenes(self):
        book = {"title": "T", "author": "A", "kind": "novel", "chapters": [{
            "title": "I", "introduction": "BEAT NOTE", "sections": [
                {"heading": "", "content": "Scena 1."}, {"heading": "", "content": "Scena 2."}]}], "conclusion": {}}
        html = build_ebook_html(book, "minimal", [])
        assert "BEAT NOTE" not in html and html.count("* * *") == 1 and "kind-novel" in html

    def test_guide_unchanged(self):
        book = {"title": "T", "chapters": [{"title": "I", "introduction": "Intro", "key_takeaway": "Take",
                                            "sections": [{"heading": "H", "content": "C"}]}], "conclusion": {}}
        html = build_ebook_html(book, "minimal", [])
        assert "Intro" in html and "Take" in html and "* * *" not in html and "rb-" not in html

    def test_epub_with_all_block_types_is_valid(self, tmp_path):
        path = str(tmp_path / "diy.epub")
        build_epub(DIY_BOOK, "minimal", [], path)
        result = validate_epub(path)
        assert result["isValid"], result["errors"]
        if __import__("os").getenv("EPUBCHECK_JAR"):
            assert result["epubcheck"] == "ran" and result["errors"] == [] and result["warnings"] == []

    def test_docx_blocks(self, tmp_path):
        from docx import Document
        path = str(tmp_path / "diy.docx")
        build_docx(DIY_BOOK, "minimal", [], path)
        text = "\n".join(p.text for p in Document(path).paragraphs)
        for needle in ("Czas: 4 h", "☐ deski <18 mm>", "UWAGA: Używaj okularów.", "Kroki", "Odpowiedź: 2"):
            assert needle in text, needle

    def test_interactive_blocks_and_escaping(self):
        from backend.core.interactive import build_interactive_book
        book = json.loads(json.dumps(DIY_BOOK))
        book["chapters"][0]["sections"][0]["heading"] = "Cięcie <b>"
        html = build_interactive_book(book, "minimal", [])
        assert "rb-facts" in html and "rb-steps" in html and "Cięcie &lt;b&gt;" in html


@pytest.mark.parametrize("kind", list(KINDS))
def test_every_kind_renders_an_empty_ish_book(kind):
    book = {"title": "T", "kind": kind, "chapters": [{"title": "C", "sections": [{"heading": "", "content": "x"}]}],
            "conclusion": {}}
    assert "<html" in build_ebook_html(book, "minimal", [])
