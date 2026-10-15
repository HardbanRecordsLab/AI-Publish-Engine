"""Book chrome in the book's language, valid paragraph markup, brand toggle,
and the background whole-book translation flow."""
import json
import zipfile

import pytest

from backend.core.book_labels import book_labels, language_code
from backend.core.builder import build_ebook_html

BOOK = {
    "title": "Budżet domowy", "author": "Jan Kowalski", "language": "Polish",
    "chapters": [{"title": "Start", "introduction": "Wstęp rozdziału.", "key_takeaway": "Oszczędzaj.",
                  "sections": [{"heading": "Plan", "content": "Akapit pierwszy.\n\nAkapit drugi."}],
                  "faq": [{"question": "Q?", "answer": "A."}]}],
    "conclusion": {"title": "", "content": "Koniec."},
}


class TestLanguageCode:
    @pytest.mark.parametrize("value,code", [
        ("Polish", "pl"), ("polski", "pl"), ("pl", "pl"), ("German", "de"),
        ("it", "it"), ("", "en"), (None, "en"), ("Klingon", "en"),
    ])
    def test_codes(self, value, code):
        assert language_code(value) == code

    def test_unknown_labels_fall_back_to_english(self):
        assert book_labels("it")["chapter"] == "Chapter"
        assert book_labels("Polish")["chapter"] == "Rozdział"

    def test_every_language_has_every_label(self):
        from backend.core.book_labels import LABELS
        keys = set(LABELS["en"])
        assert all(set(v) == keys for v in LABELS.values())


class TestLocalizedEbook:
    def test_polish_book_has_polish_chrome_and_lang(self):
        html = build_ebook_html(BOOK, "minimal", [], introduction="Intro.", glossary_terms=[
            {"term": "t", "definition": "d"}])
        assert '<html lang="pl"' in html
        for label in ("Rozdział 1", "Najważniejsze", "Najczęściej zadawane pytania", "Słowniczek",
                      "Spis treści", "Wstęp", "Wszelkie prawa zastrzeżone"):
            assert label in html, label
        assert "Chapter 1" not in html and "Key Takeaway" not in html

    def test_paragraphs_are_not_nested_in_p(self):
        html = build_ebook_html(BOOK, "minimal", [])
        assert "<p>Akapit pierwszy.</p><p>Akapit drugi.</p>" in html
        assert '<div class="section-body"' in html

    def test_book_without_language_stays_english(self):
        html = build_ebook_html({**BOOK, "language": ""}, "minimal", [])
        assert '<html lang="en"' in html and "Chapter 1" in html

    def test_brand_is_printed_and_can_be_turned_off(self, monkeypatch):
        from backend.core import builder
        html = build_ebook_html(BOOK, "minimal", [], back_cover_blurb="Blurb")
        assert "Stworzono w" in html and builder.BOOK_BRAND in html
        monkeypatch.setitem(builder.env.globals, "book_brand", "")
        html = build_ebook_html(BOOK, "minimal", [], back_cover_blurb="Blurb")
        assert "Stworzono w" not in html
        assert "Wydawca Jan Kowalski" in html


class TestLocalizedExports:
    def test_epub_language_and_labels(self, tmp_path):
        from backend.core.export import build_epub
        path = str(tmp_path / "b.epub")
        build_epub(BOOK, "minimal", [], path, introduction="Intro.")
        with zipfile.ZipFile(path) as z:
            opf = next(z.read(n).decode() for n in z.namelist() if n.endswith(".opf"))
            chapter = next(z.read(n).decode() for n in z.namelist() if n.endswith("ch1.xhtml"))
        assert "<dc:language>pl</dc:language>" in opf
        assert "Rozdział 1" in chapter
        assert "<p>Akapit pierwszy.</p>" in chapter

    def test_docx_labels(self, tmp_path):
        from docx import Document

        from backend.core.export import build_docx
        path = str(tmp_path / "b.docx")
        build_docx(BOOK, "minimal", [], path, introduction="Intro.")
        text = "\n".join(p.text for p in Document(path).paragraphs)
        assert "Spis treści" in text and "Wstęp" in text and "Table of Contents" not in text

    def test_web_formats(self):
        from backend.core.website import build_website
        for kind in ("website", "landing-page", "blog-post"):
            html = build_website(BOOK, "minimal", [], content_type=kind)
            assert 'lang="pl"' in html
            assert "Join thousands" not in html


class TestWholeBookTranslation:
    def test_translates_chapters_and_extras(self, monkeypatch):
        from backend.core import translator
        calls = []

        def fake_writer_json(system, user, provider=None, **kw):
            calls.append(user)
            data = json.loads(user[user.index("{"):user.rindex("}") + 1])["data"]
            tr = lambda v: "DE:" + v if isinstance(v, str) else v  # noqa: E731
            if "sections" in data:
                return {"data": {**data, "title": tr(data["title"])}}
            return {"data": {k: (tr(v) if isinstance(v, str) else v) for k, v in data.items()}}

        monkeypatch.setattr(translator, "writer_json", fake_writer_json)
        params = {"introduction": "Intro", "infographics": [{"type": "list", "title": "IG", "chapter_index": 0}]}
        book, out_params = translator.translate_full_book(BOOK, params, "de")
        assert len(calls) == 2  # one chapter + front/back matter
        assert "German" in calls[0]
        assert book["chapters"][0]["title"] == "DE:Start"
        assert book["title"] == "DE:Budżet domowy"
        assert book["language"] == "de"
        assert out_params["introduction"] == "DE:Intro"
        assert out_params["infographics"][0]["type"] == "list"

    def test_lost_structure_raises(self, monkeypatch):
        from backend.core import translator
        monkeypatch.setattr(translator, "writer_json", lambda *a, **k: {"title": "x"})
        with pytest.raises(ValueError):
            translator.translate_full_book(BOOK, {}, "de")


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from backend.main import app
    return TestClient(app)


class TestTranslationEndpoint:
    def test_background_flow(self, client, monkeypatch, tmp_path):
        from backend.routers import publishing
        monkeypatch.setattr(publishing, "OUTPUT_DIR", str(tmp_path))
        monkeypatch.setattr(publishing, "get_job", lambda jid: {
            "status": "done", "book_data": json.dumps(BOOK), "build_params": json.dumps({"style": "minimal"})})
        monkeypatch.setattr(publishing, "translate_full_book",
                            lambda b, p, lang: ({**b, "language": lang, "title": "T-" + lang}, p))

        monkeypatch.setattr(publishing, "_start_background", lambda fn, *args: fn(*args))
        from backend.routers.auth import require_admin
        client.app.dependency_overrides[require_admin] = lambda: None
        try:
            r = client.post("/api/translate/job1", json={"languages": ["de", "fr"]})
        finally:
            client.app.dependency_overrides.pop(require_admin, None)
        assert r.status_code == 200, r.text

        status = client.get("/api/translate/job1").json()["translations"]
        assert {t["language"]: t["status"] for t in status} == {"de": "done", "fr": "done"}
        dl = client.get(status[0]["downloads"]["epub"])
        assert dl.status_code == 200 and dl.content[:2] == b"PK"
        assert client.get("/api/translate/job1/de/exe").status_code == 404

    def test_rejects_job_without_book(self, client, monkeypatch):
        from backend.routers import publishing
        from backend.routers.auth import require_admin
        monkeypatch.setattr(publishing, "get_job", lambda jid: {"status": "done", "book_data": None})
        client.app.dependency_overrides[require_admin] = lambda: None
        try:
            r = client.post("/api/translate/job1?languages=de")
        finally:
            client.app.dependency_overrides.pop(require_admin, None)
        assert r.status_code == 400
