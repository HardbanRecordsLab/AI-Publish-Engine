"""Unit tests for the content-generation prompts and chapter writing.

AI calls are replaced with a fake _try_providers so these run offline.
"""
import json

import pytest

from backend.core import ai
from backend.core.builder import paragraph_breaks
from backend.orchestrator.agent import PipelineContext


class _FakeProviders:
    def __init__(self, response: str):
        self.response = response
        self.calls: list[dict] = []

    def __call__(self, system, user, preferred=None, max_tokens=6000, temperature=0.1, timeout=60):
        self.calls.append({"system": system, "user": user, "max_tokens": max_tokens,
                           "temperature": temperature, "timeout": timeout})
        return self.response


OUTLINE = {
    "title": "Budżet domowy",
    "chapters": [{"title": "Start", "introduction": "i", "key_takeaway": "k",
                  "sections": [{"heading": "A", "content": "draft"}]}],
    "conclusion": {"title": "Koniec", "content": "c"},
}


class TestAnalyzeTextBrief:
    def test_form_settings_reach_the_prompt(self, monkeypatch):
        fake = _FakeProviders(json.dumps(OUTLINE))
        monkeypatch.setattr(ai, "_try_providers", fake)
        ai.analyze_text("source text", audience="początkujący", tone="casual",
                        chapters="8", keywords="oszczędzanie, budżet", language="Polish")
        prompt = fake.calls[0]["user"]
        assert "exactly 8 chapters" in prompt
        assert "Write ALL text values in Polish" in prompt
        assert "początkujący" in prompt
        assert "casual" in prompt
        assert "oszczędzanie, budżet" in prompt

    def test_defaults_without_settings(self, monkeypatch):
        fake = _FakeProviders(json.dumps(OUTLINE))
        monkeypatch.setattr(ai, "_try_providers", fake)
        ai.analyze_text("source text")
        prompt = fake.calls[0]["user"]
        assert "4-6 chapters" in prompt
        assert "AUTHOR'S BRIEF" not in prompt
        assert "same language as the source text" in prompt

    def test_chapter_count_is_clamped(self):
        assert ai._parse_chapter_count("50") == 20
        assert ai._parse_chapter_count("0") == 1
        assert ai._parse_chapter_count("") is None
        assert ai._parse_chapter_count("abc") is None


class TestWriteChapter:
    @pytest.fixture(autouse=True)
    def _no_writer_model(self, monkeypatch):
        # Exercise the provider-chain path only; TestWriterModel covers the writer.
        monkeypatch.setattr(ai, "WRITER_PROVIDER", "")

    def test_expands_prose_and_keeps_other_fields(self, monkeypatch):
        written = {"title": "Start", "introduction": "Hook.", "key_takeaway": "KT",
                   "sections": [{"heading": "A", "content": "Para 1.\n\nPara 2."}]}
        fake = _FakeProviders(json.dumps(written))
        monkeypatch.setattr(ai, "_try_providers", fake)
        chapter = dict(OUTLINE["chapters"][0], faq=[{"question": "q", "answer": "a"}])

        result = ai.write_chapter(chapter, book=OUTLINE, chapter_index=0,
                                  previous_summaries=["Ch0 Earlier: covered basics"],
                                  words_per_section=550, language="Polish")

        assert result["sections"][0]["content"] == "Para 1.\n\nPara 2."
        assert result["introduction"] == "Hook."
        assert result["faq"] == chapter["faq"]
        call = fake.calls[0]
        assert call["temperature"] == ai.WRITING_TEMPERATURE
        assert call["timeout"] == ai.WRITING_TIMEOUT
        assert "about 550 words" in call["user"]
        assert "covered basics" in call["user"]

    def test_rejects_response_without_sections(self, monkeypatch):
        monkeypatch.setattr(ai, "_try_providers", _FakeProviders('{"title": "x"}'))
        with pytest.raises(ValueError):
            ai.write_chapter(OUTLINE["chapters"][0], book=OUTLINE, chapter_index=0)

    def test_short_formats_get_shorter_sections(self):
        assert ai.words_per_section("landing-page") < ai.words_per_section("blog-post") < ai.words_per_section("ebook")
        assert ai.words_per_section("unknown") == ai.words_per_section("ebook")


class TestEditorialAgent:
    def test_falls_back_to_draft_and_passes_context_forward(self, monkeypatch):
        from backend.agents import editorial_agent

        calls = []

        def fake_write(ch, **kwargs):
            calls.append(list(kwargs["previous_summaries"]))
            if ch["title"] == "Bad":
                raise ValueError("bad json")
            return dict(ch, key_takeaway="learned " + ch["title"])

        monkeypatch.setattr(editorial_agent, "_write_chapter", fake_write)
        monkeypatch.setattr(editorial_agent, "update_job", lambda *a, **k: None)
        monkeypatch.setattr(editorial_agent, "is_cancelled", lambda job_id: False)

        ctx = PipelineContext(job_id="t", text="x", style="m", language="Polish")
        ctx.ebook_dict = {
            "chapters": [
                {"title": "One", "sections": [{"heading": "h", "content": "c"}]},
                {"title": "Bad", "key_takeaway": "draft kt", "sections": [{"heading": "h", "content": "c"}]},
                {"title": "Three", "sections": [{"heading": "h", "content": "c"}]},
            ],
            "conclusion": {},
        }
        ctx = editorial_agent.EditorialAgent().run(ctx)

        chapters = ctx.ebook_dict["chapters"]
        assert [c["title"] for c in chapters] == ["One", "Bad", "Three"]
        assert chapters[1]["key_takeaway"] == "draft kt"
        assert calls[2] == ["Ch1 One: learned One", "Ch2 Bad: draft kt"]
        assert ctx.progress == 53


class TestParagraphBreaks:
    def test_blank_lines_become_breaks(self):
        assert paragraph_breaks("One.\n\nTwo.\n \n\nThree.") == "One.<br><br>Two.<br><br>Three."

    def test_single_newlines_and_empty_are_untouched(self):
        assert paragraph_breaks("One.\nTwo.") == "One.\nTwo."
        assert paragraph_breaks("") == ""
        assert paragraph_breaks(None) == ""


class TestWriterModel:
    CHAPTER = {"title": "T", "introduction": "I", "key_takeaway": "K",
               "sections": [{"heading": "H", "content": "Full text."}]}

    def test_writer_model_is_tried_first(self, monkeypatch):
        calls = []

        def fake_call(name, messages, **kw):
            calls.append((name, kw.get("model"), kw.get("max_tokens")))
            return json.dumps(self.CHAPTER)

        monkeypatch.setattr(ai, "_call", fake_call)
        monkeypatch.setattr(ai, "_try_providers", lambda *a, **k: pytest.fail("fallback used"))
        ai.write_chapter(OUTLINE["chapters"][0], book=OUTLINE, chapter_index=0)
        assert calls == [(ai.WRITER_PROVIDER, ai.WRITER_MODEL, ai.WRITER_MAX_TOKENS)]

    def test_falls_back_on_error_or_bad_json(self, monkeypatch):
        for writer_result in (RuntimeError("401"), "not json at all", None):
            def fake_call(name, messages, _r=writer_result, **kw):
                if isinstance(_r, Exception):
                    raise _r
                return _r

            fallback = _FakeProviders(json.dumps(self.CHAPTER))
            monkeypatch.setattr(ai, "_call", fake_call)
            monkeypatch.setattr(ai, "_try_providers", fallback)
            result = ai.write_chapter(OUTLINE["chapters"][0], book=OUTLINE, chapter_index=0)
            assert result["sections"][0]["content"] == "Full text."
            assert len(fallback.calls) == 1

    def test_disabled_writer_goes_straight_to_chain(self, monkeypatch):
        monkeypatch.setattr(ai, "WRITER_PROVIDER", "")
        monkeypatch.setattr(ai, "_call", lambda *a, **k: pytest.fail("writer used"))
        fallback = _FakeProviders(json.dumps(self.CHAPTER))
        monkeypatch.setattr(ai, "_try_providers", fallback)
        ai.write_chapter(OUTLINE["chapters"][0], book=OUTLINE, chapter_index=0)
        assert len(fallback.calls) == 1
