from backend.core.builder import build_ebook_html


class TestBuilder:
    def test_builds_minimal_html(self, sample_analysis):
        html = build_ebook_html(sample_analysis, "minimal", [])
        assert "<html" in html or "<!DOCTYPE" in html
        assert len(html) > 1000

    def test_builds_all_20_themes(self, sample_analysis):
        themes = ["business", "dark", "ai", "finance", "health", "luxury",
                   "magazine", "corporate", "minimal", "book", "story",
                   "education", "cookbook", "travel", "real_estate", "music",
                   "startup", "cyberpunk", "retro", "future"]
        for theme in themes:
            html = build_ebook_html(sample_analysis, theme, [])
            assert "</html>" in html, f"Failed for theme: {theme}"
            assert len(html) > 1000

    def test_contains_title(self, sample_analysis):
        html = build_ebook_html(sample_analysis, "minimal", [])
        assert sample_analysis["title"] in html or "The AI Revolution" in html

    def test_contains_chapter_titles(self, sample_analysis):
        html = build_ebook_html(sample_analysis, "minimal", [])
        for ch in sample_analysis["chapters"]:
            assert ch["title"] in html

    def test_contains_section_headings(self, sample_analysis):
        html = build_ebook_html(sample_analysis, "minimal", [])
        for ch in sample_analysis["chapters"]:
            for sec in ch["sections"]:
                assert sec["heading"] in html

    def test_contains_conclusion(self, sample_analysis):
        html = build_ebook_html(sample_analysis, "minimal", [])
        assert sample_analysis["conclusion"]["title"] in html

    def test_contains_cover_icon(self, sample_analysis):
        html = build_ebook_html(sample_analysis, "minimal", [])
        assert "cover-icon" in html

    def test_infographics_in_html(self, sample_analysis):
        infographics = [
            {"type": "list", "title": "Test", "data_points": ["A", "B"],
             "chapter_index": 0, "section_index": 0}
        ]
        html = build_ebook_html(sample_analysis, "minimal", infographics)
        assert "infographic-block" in html

    def test_topic_colors_used(self, sample_analysis):
        html = build_ebook_html(sample_analysis, "minimal", [])
        assert "#4A4A4A" in html  # minimal accent

    def test_unknown_theme_falls_back_to_minimal(self, sample_analysis):
        html = build_ebook_html(sample_analysis, "nonexistent_theme", [])
        assert "</html>" in html
