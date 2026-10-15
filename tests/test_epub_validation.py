"""EPUB output must pass validation: built-in deep checks always, and the
official W3C EPUBCheck when EPUBCHECK_JAR is set (CI sets it)."""
import os
import zipfile

import pytest

from backend.core.builder import build_ebook_html
from backend.core.export import build_epub
from backend.core.publish_validators import run_epubcheck, validate_epub

# Deliberately hostile prose: raw "<", "&" and tag-like text from the model.
PARA = "Budżet zaczyna się od świadomości & planu <ważne>. Zapisuj wydatki: a < b."
BOOK = {
    "title": "Budżet & dom", "subtitle": "Przewodnik <2026>", "author": "Jan Kowalski", "language": "Polish",
    "topic": "finance",
    "chapters": [{
        "title": "Start & cel", "introduction": "Wstęp <a>.", "key_takeaway": "Zapisuj & licz.",
        "sections": [{"heading": "Mapa <1>", "content": PARA + "\n\n" + PARA}, {"heading": "Plan", "content": PARA}],
        "faq": [{"question": "Ile <czasu>?", "answer": "10 & minut."}],
        "chapter_summary": {"title": "Podsumowanie", "points": ["a<b", "b&c"]},
        "checklist": {"title": "Lista", "items": [{"text": "x<y", "checked": False}]},
    }],
    "conclusion": {"title": "Koniec", "content": PARA},
}
INFOGRAPHICS = [{"type": "list", "chapter_index": 0, "section_index": 0, "title": "Kroki <1>",
                 "description": "d&e", "data_points": ["a<b", "b", "c"]}]


@pytest.fixture
def epub_path(tmp_path):
    path = str(tmp_path / "book.epub")
    build_epub(BOOK, "minimal", INFOGRAPHICS, path, introduction=PARA, author_bio="Bio <x>.",
               glossary_terms=[{"term": "t<", "definition": "d&"}], back_cover_blurb="Blurb <b>",
               back_cover_tagline="Tag")
    return path


def test_generated_epub_passes_builtin_checks(epub_path, monkeypatch):
    monkeypatch.delenv("EPUBCHECK_JAR", raising=False)
    result = validate_epub(epub_path)
    assert result["isValid"], result["errors"]
    assert result["epubcheck"] == "unavailable"


@pytest.mark.skipif(not os.getenv("EPUBCHECK_JAR"), reason="EPUBCHECK_JAR not set (CI downloads it)")
def test_generated_epub_passes_official_epubcheck(epub_path):
    result = run_epubcheck(epub_path)
    assert result is not None, "EPUBCHECK_JAR is set but epubcheck could not run"
    assert result["errors"] == [], result["errors"]
    assert result["warnings"] == [], result["warnings"]


def test_ai_text_is_escaped_in_book_html():
    html = build_ebook_html(BOOK, "minimal", INFOGRAPHICS)
    assert "&lt;ważne&gt;" in html and "<ważne>" not in html
    assert "Start &amp; cel" in html
    assert "<svg" in html  # infographic SVG still rendered as markup, not escaped


def _rewrite(src: str, dst: str, change):
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w") as zout:
        for info in zin.infolist():
            data = change(info.filename, zin.read(info.filename))
            if data is not None:
                zout.writestr(info, data)


class TestDeepChecks:
    def test_block_inside_p(self, epub_path, tmp_path):
        bad = str(tmp_path / "bad.epub")
        _rewrite(epub_path, bad, lambda n, d: d.replace(b"<p>Bud", b"<p><div>x</div>Bud", 1) if n.endswith("intro.xhtml") else d)
        assert any(e["code"] == "E111" for e in validate_epub(bad)["errors"])

    def test_malformed_xhtml(self, epub_path, tmp_path):
        bad = str(tmp_path / "bad.epub")
        _rewrite(epub_path, bad, lambda n, d: d + b"<unclosed>" if n.endswith("ch1.xhtml") else d)
        assert any(e["code"] == "E109" for e in validate_epub(bad)["errors"])

    def test_undeclared_svg(self, epub_path, tmp_path):
        bad = str(tmp_path / "bad.epub")
        _rewrite(epub_path, bad, lambda n, d: d.replace(b' properties="svg"', b"") if n.endswith(".opf") else d)
        assert any(e["code"] == "E110" for e in validate_epub(bad)["errors"])

    def test_missing_manifest_file(self, epub_path, tmp_path):
        bad = str(tmp_path / "bad.epub")
        _rewrite(epub_path, bad, lambda n, d: None if n.endswith("ch1.xhtml") else d)
        assert any(e["code"] == "E108" for e in validate_epub(bad)["errors"])


def test_status_reports_quality(monkeypatch):
    import json

    from fastapi.testclient import TestClient

    from backend.main import app
    from backend.routers import jobs
    params = {"quality": {"qa": {"score": 82, "passed": True, "chapter_reviews": [
        {"chapter": 1, "score": 8, "revised": False}, {"chapter": 2, "score": 6, "revised": True}]},
        "epub": {"isValid": True, "errors": []}}}
    monkeypatch.setattr(jobs, "get_job", lambda jid: {"status": "done", "progress": 100,
                                                       "build_params": json.dumps(params)})
    q = TestClient(app).get("/api/status/x").json()["quality"]
    assert q == {"qa_score": 82, "qa_passed": True, "chapter_scores": [8, 6], "chapters_revised": 1,
                 "epub_valid": True, "epub_errors": []}
