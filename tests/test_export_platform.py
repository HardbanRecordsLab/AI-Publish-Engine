"""Regression tests for the audit findings: export_mobi/generate_kdp_package
calling a non-existent export_epub, /api/themes/generate referencing an
unimported THEMES, and ws_manager silently dropping progress broadcasts."""
import asyncio
import os
import sys
import threading
import time
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.export import export_mobi, generate_kdp_package


def _make_fake_epub(path: str) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")


class TestExportMobi:
    def test_missing_source_epub_raises_runtime_error(self, tmp_path):
        with pytest.raises(RuntimeError, match="not found"):
            export_mobi(str(tmp_path / "nope.epub"), str(tmp_path / "out.mobi"))

    def test_real_epub_without_calibre_raises_clean_runtime_error(self, tmp_path):
        """Regardless of whether Calibre is installed on the test machine,
        this must never raise NameError (the original bug)."""
        epub_path = tmp_path / "book.epub"
        _make_fake_epub(str(epub_path))
        try:
            export_mobi(str(epub_path), str(tmp_path / "book.mobi"))
        except RuntimeError:
            pass  # expected if Calibre isn't installed on this machine
        except NameError:
            pytest.fail("export_mobi still references the removed export_epub()")


class TestGenerateKdpPackage:
    def test_copies_existing_epub_and_writes_metadata(self, tmp_path):
        epub_path = tmp_path / "source.epub"
        _make_fake_epub(str(epub_path))
        out_dir = tmp_path / "kdp_out"

        result = generate_kdp_package(
            str(epub_path), "<html><body>content</body></html>", str(out_dir),
            title="MyBook", author="Author Name", trim_size="6x9",
        )

        assert result["epub"] and os.path.exists(result["epub"])
        assert os.path.exists(result["metadata"])

    def test_missing_source_epub_does_not_raise_nameerror(self, tmp_path):
        out_dir = tmp_path / "kdp_out"
        result = generate_kdp_package(
            str(tmp_path / "missing.epub"), "<html></html>", str(out_dir), title="MyBook",
        )
        assert result["epub"] is None


class TestThemeGenerateEndpoint:
    """POST /api/themes/generate used to raise NameError on every call
    (referenced an unimported THEMES). AI call is monkeypatched so this
    test doesn't depend on network access or a real API key."""

    def test_generate_theme_does_not_raise_nameerror(self, monkeypatch):
        import backend.routers.templates as templates_module
        from fastapi.testclient import TestClient
        from backend.main import app

        fake_theme_json = (
            '{"id": "ocean-sunset", "name": "Ocean Sunset", "vibe": "calm",'
            ' "colors": {"background": "#FFFFFF", "text": "#111111", "heading": "#000000",'
            ' "accent": "#3366FF"}, "fonts": {"heading": "Georgia", "body": "Arial"},'
            ' "cover_gradient": "linear-gradient(135deg, #000 0%, #fff 100%)",'
            ' "accent_gradient": "linear-gradient(135deg, #3366FF 0%, #333 100%)"}'
        )
        monkeypatch.setattr(templates_module, "_try_providers", lambda *a, **kw: fake_theme_json)

        client = TestClient(app)
        resp = client.post("/api/themes/generate", params={"description": "a calm ocean sunset theme"})

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["theme"]["id"] == "ocean-sunset"
        assert "--color-accent: #3366FF" in data["css"]


class TestWsManagerProgress:
    def test_update_progress_without_loop_does_not_raise(self):
        from backend import ws_manager
        ws_manager._main_loop = None
        ws_manager.update_progress("job-no-loop", "processing", 1)  # must not raise

    def test_update_progress_broadcasts_via_registered_loop(self):
        from backend import ws_manager

        received = []

        class FakeWS:
            async def accept(self):
                pass

            async def send_json(self, data):
                received.append(data)

        loop = asyncio.new_event_loop()
        t = threading.Thread(target=lambda: (asyncio.set_event_loop(loop), loop.run_forever()), daemon=True)
        t.start()
        try:
            fut = asyncio.run_coroutine_threadsafe(ws_manager.manager.connect("job-x", FakeWS()), loop)
            fut.result(timeout=2)

            ws_manager.set_event_loop(loop)
            ws_manager.update_progress("job-x", "processing", 55, agent="Test")

            deadline = time.time() + 2
            while not received and time.time() < deadline:
                time.sleep(0.05)

            assert len(received) == 1
            assert received[0]["progress"] == 55
            assert received[0]["agent"] == "Test"
        finally:
            loop.call_soon_threadsafe(loop.stop)
            ws_manager._main_loop = None
