"""Unit tests for the content-generation prompts and chapter writing.

AI calls are replaced with a fake _try_providers so these run offline.
"""
import json

import pytest

from backend.core import ai
from backend.core.builder import paragraphs_html
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
        monkeypatch.setattr(editorial_agent, "REVIEW_ENABLED", False)
        monkeypatch.setattr(editorial_agent.EditorialAgent, "WORKERS", 1)   # one after another: the next chapter is told what was actually written

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


class TestParagraphsHtml:
    def test_one_p_per_paragraph(self):
        assert paragraphs_html("One.\n\nTwo.\n \n\nThree.") == "<p>One.</p><p>Two.</p><p>Three.</p>"

    def test_single_newlines_and_empty(self):
        assert paragraphs_html("One.\nTwo.") == "<p>One.\nTwo.</p>"
        assert paragraphs_html("") == ""
        assert paragraphs_html(None) == ""


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


class TestReviewAndRevise:
    def _run(self, monkeypatch, review, words=600):
        from backend.agents import editorial_agent

        writes = []

        def fake_write(ch, **kwargs):
            writes.append(kwargs.get("revision_notes"))
            text = " ".join(["word"] * words)
            return dict(ch, sections=[{"heading": "h", "content": text}])

        monkeypatch.setattr(editorial_agent, "_write_chapter", fake_write)
        monkeypatch.setattr(editorial_agent, "_review_chapter", lambda ch, **k: review)
        monkeypatch.setattr(editorial_agent, "update_job", lambda *a, **k: None)
        monkeypatch.setattr(editorial_agent, "is_cancelled", lambda job_id: False)
        monkeypatch.setattr(editorial_agent, "REVIEW_ENABLED", True)
        ctx = PipelineContext(job_id="t", text="x", style="m")
        ctx.ebook_dict = {"chapters": [{"title": "One", "sections": [{"heading": "h", "content": "c"}]}],
                          "conclusion": {}}
        ctx = editorial_agent.EditorialAgent().run(ctx)
        return writes, ctx

    def test_good_chapter_is_not_rewritten(self, monkeypatch):
        writes, ctx = self._run(monkeypatch, {"score": 8, "issues": ["minor"]})
        assert writes == [None]
        assert ctx.chapter_reviews == [{"chapter": 1, "words": 600, "revised": False, "score": 8}]

    def test_weak_chapter_is_rewritten_once_with_notes(self, monkeypatch):
        writes, ctx = self._run(monkeypatch, {"score": 4, "issues": ["Section h is generic"]})
        assert writes == [None, ["Section h is generic"]]
        assert ctx.chapter_reviews[0]["revised"] is True

    def test_too_short_chapter_is_rewritten_even_if_scored_well(self, monkeypatch):
        writes, _ = self._run(monkeypatch, {"score": 9, "issues": []}, words=100)
        assert len(writes) == 2 and "far too short" in writes[1][0]

    def test_review_score_is_clamped(self, monkeypatch):
        monkeypatch.setattr(ai, "_writer_json", lambda *a, **k: {"score": "15", "issues": "nope"})
        result = ai.review_chapter({"sections": []}, book={}, chapter_index=0)
        assert result == {"score": 10, "issues": []}


class TestNoFabrication:
    def test_finalization_never_returns_references(self, monkeypatch):
        monkeypatch.setattr(ai, "_writer_json", lambda *a, **k: {
            "introduction": "x", "references": ["Fake, Book, 2020"]})
        assert "references" not in ai.generate_ebook_sections(OUTLINE, "minimal", language="Polish")

    def test_secondary_prompts_carry_the_language(self, monkeypatch):
        prompts = []
        monkeypatch.setattr(ai, "_writer_json", lambda s, u, *a, **k: prompts.append(u) or {})
        monkeypatch.setattr(ai, "_try_providers", lambda s, u, *a, **k: prompts.append(u) or "{}")
        ai.generate_ebook_sections(OUTLINE, "minimal", language="Polish")
        ai.structure_chapter(OUTLINE["chapters"][0], 0, language="Polish")
        ai.plan_infographics(OUTLINE, {}, language="Polish")
        assert len(prompts) == 3
        assert all("Write ALL text values in Polish" in p for p in prompts)


class TestMarketingAndTranslation:
    def test_marketing_uses_writer_and_copy_rules(self, monkeypatch):
        from backend.core import marketing
        seen = []
        monkeypatch.setattr(marketing, "writer_json", lambda s, u, p=None: seen.append(u) or {"ok": 1})
        assert marketing.generate_amazon_listing(OUTLINE) == {"ok": 1}
        assert "Do not invent statistics" in seen[0]
        assert "<<<UNTRUSTED_DATA>>>" in seen[0]

    def test_translation_keeps_non_text_list_items(self, monkeypatch):
        from backend.core import translator
        monkeypatch.setattr(translator, "writer_text", lambda s, u, *a, **k: "T:" + u)
        out = translator.translate_book({"tags": ["a", 3, {"k": "b"}]}, "Polish")
        assert out["tags"] == ["T:a", 3, {"k": "T:b"}]
