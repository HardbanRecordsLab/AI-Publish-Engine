from backend.core.prompt_safety import INJECTION_GUARD, fence, sanitize_text


class TestSanitizeText:
    def test_empty_stays_empty(self):
        assert sanitize_text("") == ""
        assert sanitize_text(None) == ""

    def test_strips_control_characters(self):
        assert sanitize_text("hello\x00\x07world") == "helloworld"

    def test_keeps_newlines_and_tabs(self):
        assert sanitize_text("line1\nline2\tindented") == "line1\nline2\tindented"

    def test_caps_length(self):
        result = sanitize_text("x" * 100, max_chars=10)
        assert result == "x" * 10

    def test_default_cap_is_generous(self):
        result = sanitize_text("x" * 25000)
        assert len(result) == 20000


class TestFence:
    def test_wraps_with_markers(self):
        result = fence("hello")
        assert result.startswith("<<<UNTRUSTED_DATA>>>")
        assert result.endswith("<<<END_UNTRUSTED_DATA>>>")
        assert "hello" in result

    def test_sanitizes_before_wrapping(self):
        result = fence("bad\x00text", max_chars=100)
        assert "\x00" not in result
        assert "badtext" in result

    def test_caps_the_wrapped_content(self):
        result = fence("x" * 100, max_chars=10)
        inner = result.split("\n")[1]
        assert inner == "x" * 10


def test_injection_guard_names_the_delimiters():
    assert "<<<UNTRUSTED_DATA>>>" in INJECTION_GUARD
    assert "<<<END_UNTRUSTED_DATA>>>" in INJECTION_GUARD
