from backend.core.icon_service import get_cover_icon


class TestGetCoverIcon:
    def test_returns_svg_string(self):
        icon = get_cover_icon("technology", "#2563EB", 80)
        assert isinstance(icon, str)
        assert len(icon) > 50

    def test_contains_svg_tag(self):
        icon = get_cover_icon("technology", "#2563EB", 80)
        assert "<svg" in icon
        assert "</svg>" in icon

    def test_uses_accent_color(self):
        icon = get_cover_icon("technology", "#FF0000", 80)
        assert "#FF0000" in icon

    def test_topic_without_icon_falls_back(self):
        icon = get_cover_icon("nonexistent_topic", "#2563EB", 80)
        assert icon is not None
        assert len(icon) > 50

    def test_cache_returns_same_object(self):
        a = get_cover_icon("technology", "#2563EB", 80)
        b = get_cover_icon("technology", "#2563EB", 80)
        assert a is b

    def test_all_topic_icons_exist(self):
        from backend.core.color_engine import TOPIC_PALETTES
        for topic in TOPIC_PALETTES:
            icon = get_cover_icon(topic, "#000000", 40)
            assert icon is not None
            assert "<svg" in icon
