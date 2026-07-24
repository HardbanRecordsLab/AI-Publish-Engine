"""Tests for builder, export, and website modules."""
import os
import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Sample structure used across tests
SAMPLE_STRUCTURE = {
    "title": "Test Ebook",
    "subtitle": "A Test",
    "author": "Test Author",
    "summary": "A test ebook summary.",
    "chapters": [
        {
            "title": "Introduction",
            "introduction": "Welcome to the test.",
            "key_takeaway": "Testing is good.",
            "sections": [
                {"heading": "Section 1", "content": "Content of section 1."},
            ],
            "chapter_summary": {"title": "Summary", "points": ["Point 1"]},
            "faq": [{"question": "What?", "answer": "This."}],
            "checklist": {"title": "Checklist", "items": [{"text": "Do this"}]},
        }
    ],
    "conclusion": {"title": "Conclusion", "content": "Final thoughts."},
}

SAMPLE_INFOGRAPHICS = [
    {
        "type": "bar",
        "title": "Test Chart",
        "description": "A test chart.",
        "chapter_index": 0,
        "section_index": 0,
        "data": {"labels": ["A", "B"], "values": [10, 20]},
    }
]


def test_build_ebook_html_basic():
    from backend.core.builder import build_ebook_html
    html = build_ebook_html(SAMPLE_STRUCTURE, "minimal", SAMPLE_INFOGRAPHICS)
    assert "<!DOCTYPE html>" in html or "<html" in html
    assert "Test Ebook" in html
    assert "Test Author" in html
    assert "Section 1" in html
    assert "Key Takeaway" in html
    assert len(html) > 500


def test_build_ebook_html_with_customizations():
    from backend.core.builder import build_ebook_html
    html = build_ebook_html(
        SAMPLE_STRUCTURE, "modern", SAMPLE_INFOGRAPHICS,
        introduction="Custom intro text.",
        author_bio="About the author.",
        references=[{"title": "Ref 1", "url": "https://example.com"}],
        glossary_terms=[{"term": "AI", "definition": "Artificial Intelligence"}],
        back_cover_blurb="Back cover text.",
        back_cover_tagline="Tagline!",
        accent_color="#FF0000",
        bg_color="#FFFFFF",
        heading_font="Georgia",
        body_font="Arial",
    )
    assert "Custom intro text." in html
    assert "About the author." in html
    assert "Artificial Intelligence" in html
    assert "Back cover text." in html
    assert "Tagline!" in html


def test_build_ebook_html_all_styles():
    from backend.core.builder import build_ebook_html, STYLE_THEME_MAP
    for style in STYLE_THEME_MAP:
        html = build_ebook_html(SAMPLE_STRUCTURE, style, [])
        assert "Test Ebook" in html
        assert len(html) > 400


def test_build_ebook_html_empty():
    from backend.core.builder import build_ebook_html
    html = build_ebook_html(
        {"title": "Empty", "chapters": []}, "dark", []
    )
    assert "Empty" in html


def test_build_ebook_html_cover_image():
    from backend.core.builder import build_ebook_html
    html = build_ebook_html(
        SAMPLE_STRUCTURE, "business", [],
        cover_image="data:image/svg+xml,<svg></svg>",
        chapter_illustrations=[
            {"chapter_index": 0, "image_uri": "data:image/svg+xml,<svg></svg>"}
        ],
    )
    assert "Test Ebook" in html


def test_build_epub_basic():
    from backend.core.export import build_epub
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.epub")
        result = build_epub(
            SAMPLE_STRUCTURE, "minimal", SAMPLE_INFOGRAPHICS,
            output_path=path,
            introduction="Intro", author_bio="Bio",
            references=[], glossary_terms=[],
            back_cover_blurb="Blurb", back_cover_tagline="Tag",
            cover_svg="", cover_image="", chapter_illustrations=[],
        )
        assert result == path
        assert os.path.getsize(path) > 100


def test_build_docx_basic():
    from backend.core.export import build_docx
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.docx")
        result = build_docx(
            SAMPLE_STRUCTURE, "minimal", SAMPLE_INFOGRAPHICS,
            output_path=path,
            introduction="Intro", author_bio="Bio",
            references=[], glossary_terms=[],
            back_cover_blurb="Blurb", back_cover_tagline="Tag",
            cover_svg="", cover_image="", chapter_illustrations=[],
        )
        assert result == path
        assert os.path.getsize(path) > 100


def test_website_build_landing():
    from backend.core.website import build_website
    html = build_website(SAMPLE_STRUCTURE, "minimal", [], content_type="landing-page")
    assert "Test Ebook" in html
    assert "og:title" in html
    assert "twitter:card" in html


def test_website_build_blog():
    from backend.core.website import build_website
    html = build_website(SAMPLE_STRUCTURE, "modern", [], content_type="blog-post")
    assert "Test Ebook" in html
    assert "og:title" in html


def test_website_build_generic():
    from backend.core.website import build_website
    html = build_website(SAMPLE_STRUCTURE, "dark", [], content_type="website")
    assert "Test Ebook" in html
    assert "og:title" in html


def test_website_with_customizations():
    from backend.core.website import build_website
    html = build_website(
        SAMPLE_STRUCTURE, "creative", [],
        content_type="landing-page",
        accent_color="#FF5733", bg_color="#F0F0F0",
        heading_font="Georgia", body_font="Arial",
    )
    assert "#FF5733" in html
    assert "Test Ebook" in html


def test_website_all_modes():
    from backend.core.website import build_website
    for mode in ["landing-page", "blog-post", "website"]:
        html = build_website(SAMPLE_STRUCTURE, "business", [], content_type=mode)
        assert len(html) > 200


def test_website_empty_structure():
    from backend.core.website import build_website
    html = build_website({"title": "Minimal", "chapters": []}, "minimal", [], content_type="landing-page")
    assert "Minimal" in html


if __name__ == "__main__":
    test_build_ebook_html_basic()
    print("OK test_build_ebook_html_basic")
    test_build_ebook_html_with_customizations()
    print("OK test_build_ebook_html_with_customizations")
    test_build_ebook_html_all_styles()
    print("OK test_build_ebook_html_all_styles")
    test_build_ebook_html_empty()
    print("OK test_build_ebook_html_empty")
    test_build_ebook_html_cover_image()
    print("OK test_build_ebook_html_cover_image")
    test_build_epub_basic()
    print("OK test_build_epub_basic")
    test_build_docx_basic()
    print("OK test_build_docx_basic")
    test_website_build_landing()
    print("OK test_website_build_landing")
    test_website_build_blog()
    print("OK test_website_build_blog")
    test_website_build_generic()
    print("OK test_website_build_generic")
    test_website_with_customizations()
    print("OK test_website_with_customizations")
    test_website_all_modes()
    print("OK test_website_all_modes")
    test_website_empty_structure()
    print("OK test_website_empty_structure")
    print("\nAll core module tests passed")
