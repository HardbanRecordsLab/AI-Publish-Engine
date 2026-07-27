"""Tests for the 20 -> 50 theme expansion and the label/vibe parsing fix
that came with it.

Context: templates/themes/ grew from 20 folders to 50 — the 5 previously
"phantom" themes (modern/wellness/academic/technical/creative, which had
cover-icon entries but no theme.css), the 10 ids referenced by
backend/routers/templates.py's TEMPLATES picker for website/landing-page/
blog-post that silently fell back to "minimal" colors, and 15 new
domains. All 50 share one mechanism (backend/core/tokens.py's
_load_theme(), auto-discovered by backend/themes.py), so this also fixes
color/font variety for website, landing-page, blog-post, and
interactive-book output, not just ebooks — they all call get_theme().
"""
from backend.core.tokens import _split_label_vibe
from backend.routers.templates import STYLE_THEME_PREVIEW_MAP
from backend.themes import _COVER_ICONS, get_theme, list_themes


class TestSplitLabelVibe:
    def test_splits_on_hyphen(self):
        label, vibe = _split_label_vibe("Modern Edge - clean geometric contemporary")
        assert label == "Modern Edge"
        assert vibe == "clean geometric contemporary"

    def test_splits_on_em_dash(self):
        label, vibe = _split_label_vibe("Minimal Pro — clean minimal")
        assert label == "Minimal Pro"
        assert vibe == "clean minimal"

    def test_no_separator_returns_empty_label(self):
        label, vibe = _split_label_vibe("just a vibe phrase")
        assert label == ""
        assert vibe == "just a vibe phrase"


class TestFiftyThemes:
    def test_exactly_fifty_themes_registered(self):
        assert len(list_themes()) == 50

    def test_every_theme_has_a_real_label_not_a_raw_id(self):
        # Regression: themes.py used to derive "name" purely from
        # folder_id.replace("_", " ").title(), which turned the "ai" theme
        # into the display label "Ai" instead of "AI & Tech". Every theme's
        # CSS comment now supplies a proper label via _split_label_vibe().
        for t in list_themes():
            assert t["name"], f"{t['id']} has no display name"
            assert t["name"] != t["id"], f"{t['id']} fell back to a raw id-derived name: {t['name']!r}"

    def test_restored_phantom_themes_resolve_to_themselves(self):
        for theme_id in ("modern", "wellness", "academic", "technical", "creative"):
            theme = get_theme(theme_id)
            assert theme["id"] == theme_id, f"{theme_id} silently fell back to {theme['id']!r}"

    def test_former_picker_only_ids_now_have_real_themes(self):
        # These used to be picker labels in TEMPLATES with no matching
        # templates/themes/<id>/ folder, so get_theme() silently returned
        # "minimal" colors regardless of which one the user picked.
        picker_ids = ("landing", "blog", "docs", "portfolio", "saas",
                      "product", "leadgen", "tutorial", "listicle", "interview")
        for theme_id in picker_ids:
            theme = get_theme(theme_id)
            assert theme["id"] == theme_id, f"{theme_id} silently fell back to {theme['id']!r}"

    def test_every_theme_has_a_cover_icon_entry(self):
        for t in list_themes():
            assert t["id"] in _COVER_ICONS, f"{t['id']} has no _COVER_ICONS entry, falls back to generic mdi:book"


class TestStyleThemePreviewMap:
    def test_only_professional_needs_an_alias(self):
        # Every other id now resolves to a real theme folder of the same
        # name, so a stale preview-map entry would make the live preview
        # diverge from what actual generation produces (the exact bug this
        # map used to paper over for the 10 former picker-only ids).
        assert set(STYLE_THEME_PREVIEW_MAP.keys()) == {"professional"}
        assert STYLE_THEME_PREVIEW_MAP["professional"] == "business"
