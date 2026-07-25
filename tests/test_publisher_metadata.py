"""Tests for backend/core/publisher.py's platform metadata generators,
specifically the AI-content disclosure field added alongside the basic
content-moderation work — every book from this pipeline is AI-generated,
and Amazon KDP requires disclosing that in its Content Rights step."""
from backend.core.publisher import (
    AI_CONTENT_DISCLOSURE,
    generate_google_play_metadata,
    generate_kdp_metadata,
    generate_polish_metadata,
)

EBOOK = {"title": "Test Book", "author": "Jane Doe", "summary": "A book about testing."}


class TestAiContentDisclosure:
    def test_kdp_metadata_includes_disclosure(self):
        meta = generate_kdp_metadata(EBOOK)
        assert meta["ai_content_disclosure"] == AI_CONTENT_DISCLOSURE
        assert "KDP" in meta["ai_content_disclosure"]

    def test_google_play_metadata_includes_disclosure(self):
        meta = generate_google_play_metadata(EBOOK)
        assert meta["ai_content_disclosure"] == AI_CONTENT_DISCLOSURE

    def test_polish_metadata_includes_disclosure(self):
        meta = generate_polish_metadata(EBOOK)
        assert meta["ujawnienie_tresci_ai"] == AI_CONTENT_DISCLOSURE

    def test_kdp_metadata_still_has_core_fields(self):
        meta = generate_kdp_metadata(EBOOK)
        assert meta["title"] == "Test Book"
        assert meta["author"] == "Jane Doe"
        assert "description" in meta
