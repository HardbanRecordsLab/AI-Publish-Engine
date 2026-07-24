from backend.core.color_engine import detect_topic, get_color_palette, list_topics, TOPIC_PALETTES


class TestDetectTopic:
    def test_detects_technology(self):
        result = detect_topic({"title": "The Innovation Age", "topic": "technology"})
        assert result == "technology"

    def test_detects_finance(self):
        result = detect_topic({"title": "Stock Market", "topic": "finance"})
        assert result == "finance"

    def test_detects_health(self):
        result = detect_topic({"title": "Medical Breakthroughs", "topic": "health"})
        assert result == "health"

    def test_detects_marketing(self):
        result = detect_topic({"title": "SEO Guide", "topic": "marketing"})
        assert result == "marketing"

    def test_detects_education(self):
        result = detect_topic({"title": "Learning Methods", "topic": "education"})
        assert result == "education"

    def test_detects_psychology(self):
        result = detect_topic({"title": "Mind Hacks", "topic": "psychology"})
        assert result == "psychology"

    def test_detects_ai(self):
        result = detect_topic({"title": "GPT and LLMs for Chatbots", "topic": "artificial_intelligence"})
        assert result == "artificial_intelligence"

    def test_detects_survival(self):
        result = detect_topic({"title": "Prepper Guide", "topic": "survival"})
        assert result == "survival"

    def test_detects_business(self):
        result = detect_topic({"title": "Startup Strategy", "topic": "business"})
        assert result == "business"

    def test_fallback_to_general(self):
        result = detect_topic({"title": "Random Topic", "topic": "unknown_xyz"})
        assert result == "general"

    def test_fallback_on_empty(self):
        result = detect_topic({})
        assert result == "general"

    def test_keyword_from_title(self):
        result = detect_topic({"title": "Investing for Retirement", "topic": "general"})
        assert result == "finance"


class TestColorPalette:
    def test_technology_palette(self):
        pal = get_color_palette("technology")
        assert pal["colors"]["accent"] == "#06B6D4"

    def test_finance_palette(self):
        pal = get_color_palette("finance")
        assert pal["colors"]["accent"] == "#B8860B"

    def test_health_palette(self):
        pal = get_color_palette("health")
        assert pal["colors"]["accent"] == "#22C55E"

    def test_marketing_palette(self):
        pal = get_color_palette("marketing")
        assert pal["colors"]["accent"] == "#F97316"

    def test_general_palette(self):
        pal = get_color_palette("nonexistent")
        assert pal["name"] == "Clean Modern"

    def test_all_palettes_have_required_keys(self):
        for topic_id in TOPIC_PALETTES:
            pal = get_color_palette(topic_id)
            assert "name" in pal
            assert "colors" in pal
            assert "accent" in pal["colors"]
            assert "background" in pal["colors"]
            assert "text" in pal["colors"]
            assert "heading" in pal["colors"]
            assert "fonts" in pal


class TestListTopics:
    def test_returns_list(self):
        topics = list_topics()
        assert isinstance(topics, list)

    def test_includes_all_topics(self):
        topics = list_topics()
        ids = [t["id"] for t in topics]
        assert "technology" in ids
        assert "finance" in ids
        assert "general" in ids

    def test_items_have_required_keys(self):
        for t in list_topics():
            assert "id" in t
            assert "name" in t
            assert "colors" in t
            assert "accent" in t["colors"]
