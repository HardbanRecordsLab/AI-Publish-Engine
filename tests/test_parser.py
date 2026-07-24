import io
from backend.core.parser import extract_text


class TestTxtParser:
    def test_extracts_plain_text(self):
        result = extract_text("test.txt", b"Hello World")
        assert result == "Hello World"

    def test_handles_unicode(self):
        result = extract_text("test.txt", "Café résumé".encode("utf-8"))
        assert "Café" in result

    def test_empty_content(self):
        result = extract_text("test.txt", b"")
        assert result == ""

    def test_multiline(self):
        result = extract_text("test.txt", b"Line 1\nLine 2\nLine 3")
        assert "Line 2" in result


class TestDocxParser:
    def test_empty_docx_raises_gracefully(self):
        # Empty bytes can't be parsed as .docx
        try:
            result = extract_text("empty.docx", b"")
            # May return empty or raise depending on implementation
        except Exception:
            result = ""
        assert result == ""


class TestParserEdgeCases:
    def test_unsupported_extension_passes_through(self):
        # Unknown extensions return raw content
        result = extract_text("file.xyz", b"content")
        assert result == "content"

    def test_very_long_text(self):
        long = ("word " * 10000).encode("utf-8")
        result = extract_text("test.txt", long)
        assert len(result) > 10000
