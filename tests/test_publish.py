"""Tests for the platform validators/packaging ported from Kiro eBook
Studio (backend/core/publish_validators.py, backend/core/publish_prep.py)
and the /api/publish/validate and /api/publish/prepare endpoints that
expose them."""
import sys
import zipfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.publish_validators import validate_metadata, validate_kdp, validate_apple_books, validate_epub
from backend.core.publish_prep import prepare_kdp, prepare_apple_books, prepare_kobo, prepare_google_play, PREPARERS


def _make_fake_epub(path: str, valid: bool = True) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        if valid:
            zf.writestr(
                "META-INF/container.xml",
                '<?xml version="1.0"?><container><rootfiles>'
                '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
                "</rootfiles></container>",
            )
            zf.writestr(
                "OEBPS/content.opf",
                '<?xml version="1.0"?><package version="3.0"><metadata>'
                "<dc:title>T</dc:title><dc:creator>A</dc:creator>"
                "<dc:language>pl</dc:language><dc:identifier>id1</dc:identifier>"
                '</metadata><manifest><item properties="nav" href="nav.xhtml"/></manifest></package>',
            )


class TestValidateMetadata:
    def test_complete_metadata_is_valid(self):
        result = validate_metadata({
            "title": "T", "author": "A", "description": "x" * 150,
            "language": "pl", "category": "fiction", "keywords": ["a", "b"],
            "isbn": "9781234567897", "publicationDate": "2026-01-01",
            "publisher": "Acme Press", "rights": "All rights reserved",
        })
        assert result["isValid"] is True
        assert result["completeness"] == 100

    def test_missing_title_and_author_are_errors(self):
        result = validate_metadata({})
        assert result["isValid"] is False
        codes = {e["code"] for e in result["errors"]}
        assert "M001" in codes  # missing title
        assert "M003" in codes  # missing author

    def test_bad_isbn_is_an_error(self):
        result = validate_metadata({"title": "T", "author": "A", "isbn": "not-an-isbn"})
        assert any(e["code"] == "M013" for e in result["errors"])

    def test_too_many_keywords_is_a_warning_not_error(self):
        result = validate_metadata({"title": "T", "author": "A", "keywords": list("abcdefgh")})
        assert any(w["code"] == "M011" for w in result["warnings"])


class TestValidateKdp:
    def test_missing_cover_is_an_error(self):
        result = validate_kdp({"title": "T", "author": "A"})
        assert result["isValid"] is False
        assert any(e["code"] == "KDP013" for e in result["errors"])

    def test_oversized_epub_is_an_error(self, tmp_path, monkeypatch):
        epub_path = tmp_path / "book.epub"
        epub_path.write_bytes(b"x")
        monkeypatch.setattr("os.path.getsize", lambda p: 700 * 1024 * 1024)
        result = validate_kdp({"title": "T", "author": "A"}, epub_path=str(epub_path))
        assert any(e["code"] == "KDP021" for e in result["errors"])


class TestValidateAppleBooks:
    def test_missing_required_fields(self):
        result = validate_apple_books({})
        codes = {e["code"] for e in result["errors"]}
        assert {"AB001", "AB002", "AB003", "AB004", "AB005", "AB012"}.issubset(codes)

    def test_complete_metadata_with_cover_is_valid(self, tmp_path):
        cover = tmp_path / "cover.jpg"
        cover.write_bytes(b"fake-jpeg-bytes")
        result = validate_apple_books(
            {"title": "T", "author": "A", "isbn": "9781234567897", "language": "pl", "publicationDate": "2026-01-01"},
            cover_path=str(cover),
        )
        assert result["isValid"] is True


class TestValidateEpub:
    def test_valid_epub_zip_passes(self, tmp_path):
        epub_path = tmp_path / "book.epub"
        _make_fake_epub(str(epub_path), valid=True)
        result = validate_epub(str(epub_path))
        assert result["isValid"] is True, result["errors"]

    def test_missing_file_fails_cleanly(self, tmp_path):
        result = validate_epub(str(tmp_path / "missing.epub"))
        assert result["isValid"] is False
        assert result["errors"][0]["code"] == "E000"

    def test_epub_missing_nav_manifest_property_fails(self, tmp_path):
        epub_path = tmp_path / "book.epub"
        with zipfile.ZipFile(epub_path, "w") as zf:
            zf.writestr("mimetype", "application/epub+zip")
            zf.writestr(
                "META-INF/container.xml",
                '<?xml version="1.0"?><container><rootfiles>'
                '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
                "</rootfiles></container>",
            )
            zf.writestr(
                "OEBPS/content.opf",
                '<?xml version="1.0"?><package version="3.0"><metadata>'
                "<dc:title>T</dc:title><dc:creator>A</dc:creator>"
                "<dc:language>pl</dc:language><dc:identifier>id1</dc:identifier>"
                "</metadata><manifest></manifest></package>",
            )
        result = validate_epub(str(epub_path))
        assert result["isValid"] is False
        assert any(e["code"] == "E106" for e in result["errors"])

    def test_not_a_zip_file_fails_cleanly(self, tmp_path):
        bad = tmp_path / "not-really.epub"
        bad.write_text("this is not a zip")
        result = validate_epub(str(bad))
        assert result["isValid"] is False
        assert any(e["code"] == "E001" for e in result["errors"])


class TestPreparePlatformPackages:
    """Covers the Pillow cover-resize bug caught during development: an
    earlier version passed a 3-tuple (w, h, quality) straight into
    ImageOps.fit(), which silently failed and fell back to copying the
    original, unresized cover."""

    def _make_cover(self, path: str, size=(500, 700)):
        Image.new("RGB", size, (200, 30, 30)).save(path)

    def test_prepare_kdp_resizes_cover_to_1600x2400(self, tmp_path):
        epub_path = tmp_path / "book.epub"
        _make_fake_epub(str(epub_path))
        cover_path = tmp_path / "cover.png"
        self._make_cover(str(cover_path))

        result = prepare_kdp(
            {"title": "My Book", "author": "A"}, str(tmp_path / "out"),
            epub_path=str(epub_path), cover_path=str(cover_path),
        )
        assert Image.open(result["files"]["cover"]).size == (1600, 2400)
        assert result["validation"]["isValid"] is True

    def test_prepare_apple_books_resizes_cover_to_3000x4000(self, tmp_path):
        cover_path = tmp_path / "cover.png"
        self._make_cover(str(cover_path))
        result = prepare_apple_books({"title": "T", "author": "A"}, str(tmp_path / "out"), cover_path=str(cover_path))
        assert Image.open(result["files"]["cover"]).size == (3000, 4000)

    def test_prepare_kobo_resizes_cover_to_1400x2100(self, tmp_path):
        cover_path = tmp_path / "cover.png"
        self._make_cover(str(cover_path))
        result = prepare_kobo({"title": "T", "author": "A"}, str(tmp_path / "out"), cover_path=str(cover_path))
        assert Image.open(result["files"]["cover"]).size == (1400, 2100)

    def test_prepare_google_play_resizes_cover_to_600x800(self, tmp_path):
        cover_path = tmp_path / "cover.png"
        self._make_cover(str(cover_path))
        result = prepare_google_play({"title": "T", "author": "A"}, str(tmp_path / "out"), cover_path=str(cover_path))
        assert Image.open(result["files"]["cover"]).size == (600, 800)

    def test_no_cover_skips_cover_gracefully(self, tmp_path):
        result = prepare_kdp({"title": "T", "author": "A"}, str(tmp_path / "out"))
        assert "cover" not in result["files"]
        assert result["validation"]["isValid"] is False  # KDP requires a cover

    def test_all_four_preparers_registered(self):
        assert set(PREPARERS.keys()) == {"amazon-kdp", "apple-books", "kobo", "google-play"}


class TestPublishEndpoints:
    def _make_done_job(self, tmp_path):
        from backend.core.jobs import create_job, update_job
        job_id = create_job("minimal")
        epub_path = tmp_path / f"{job_id}.epub"
        _make_fake_epub(str(epub_path))
        update_job(job_id, "done", 100, epub_path=str(epub_path), topic="Test Topic",
                   book_data='{"title": "Test Book", "author": "Jane Doe", "summary": "x"}')
        return job_id

    def test_validate_metadata_endpoint(self, tmp_path):
        from fastapi.testclient import TestClient
        from backend.main import app
        from backend.core.jobs import delete_job

        job_id = self._make_done_job(tmp_path)
        try:
            client = TestClient(app)
            resp = client.get(f"/api/publish/validate/{job_id}", params={"platform": "metadata"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["platform"] == "metadata"
            assert data["isValid"] is True  # title+author present via book_data
        finally:
            delete_job(job_id)

    def test_validate_epub_endpoint(self, tmp_path):
        from fastapi.testclient import TestClient
        from backend.main import app
        from backend.core.jobs import delete_job

        job_id = self._make_done_job(tmp_path)
        try:
            client = TestClient(app)
            resp = client.get(f"/api/publish/validate/{job_id}", params={"platform": "epub"})
            assert resp.status_code == 200
            assert resp.json()["isValid"] is True
        finally:
            delete_job(job_id)

    def test_validate_unknown_platform_returns_400(self, tmp_path):
        from fastapi.testclient import TestClient
        from backend.main import app
        from backend.core.jobs import delete_job

        job_id = self._make_done_job(tmp_path)
        try:
            client = TestClient(app)
            resp = client.get(f"/api/publish/validate/{job_id}", params={"platform": "nonexistent"})
            assert resp.status_code == 400
        finally:
            delete_job(job_id)

    def test_prepare_kobo_endpoint(self, tmp_path):
        from fastapi.testclient import TestClient
        from backend.main import app
        from backend.core.jobs import delete_job

        job_id = self._make_done_job(tmp_path)
        try:
            client = TestClient(app)
            resp = client.post(f"/api/publish/prepare/{job_id}", params={"platform": "kobo"})
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["platform"] == "kobo"
            assert data["files"].get("epub")
        finally:
            delete_job(job_id)

    def test_prepare_unknown_platform_returns_400(self, tmp_path):
        from fastapi.testclient import TestClient
        from backend.main import app
        from backend.core.jobs import delete_job

        job_id = self._make_done_job(tmp_path)
        try:
            client = TestClient(app)
            resp = client.post(f"/api/publish/prepare/{job_id}", params={"platform": "nonexistent"})
            assert resp.status_code == 400
        finally:
            delete_job(job_id)

    def test_prepare_job_not_found_returns_404(self):
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)
        resp = client.post("/api/publish/prepare/does-not-exist", params={"platform": "kobo"})
        assert resp.status_code == 404
