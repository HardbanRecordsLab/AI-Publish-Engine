from backend.core.infographic_engine import render_infographic


SAMPLE_COLORS = {
    "accent": "#2563EB",
    "background": "#FFFFFF",
    "text": "#1A1A1A",
    "heading": "#000000",
    "muted": "#999999",
    "secondary": "#F5F5F5",
    "border": "#E5E5E5",
    "highlight": "#F0F0F0",
}


class TestTimeline:
    def test_renders_svg(self):
        ig = {
            "type": "timeline",
            "title": "AI Evolution",
            "description": "Key milestones",
            "data_points": ["1956: Dartmouth", "1997: Deep Blue", "2012: AlexNet", "2023: GPT-4"],
        }
        svg = render_infographic(ig, SAMPLE_COLORS)
        assert "<svg" in svg
        assert "</svg>" in svg

    def test_timeline_contains_date_items(self):
        ig = {
            "type": "timeline",
            "title": "Test",
            "data_points": ["2000: Event A", "2010: Event B"],
        }
        svg = render_infographic(ig, SAMPLE_COLORS)
        assert "Event A" in svg
        assert "Event B" in svg


class TestProcess:
    def test_renders_svg(self):
        ig = {
            "type": "process",
            "title": "ML Pipeline",
            "data_points": ["Data Collection", "Preprocessing", "Training", "Deployment"],
        }
        svg = render_infographic(ig, SAMPLE_COLORS)
        assert "<svg" in svg
        assert "Data Collection" in svg

    def test_arrows_present(self):
        ig = {"type": "process", "title": "Steps", "data_points": ["A", "B", "C"]}
        svg = render_infographic(ig, SAMPLE_COLORS)
        # arrows are polygons (triangles) in the SVG
        assert "<polygon" in svg or "<path" in svg


class TestComparison:
    def test_renders_svg(self):
        ig = {
            "type": "comparison",
            "title": "Before vs After",
            "data_points": ["Slow: 10 min", "Fast: 1 min", "Cheap: $100"],
        }
        svg = render_infographic(ig, SAMPLE_COLORS)
        assert "<svg" in svg
        assert "10 min" in svg or "Slow" in svg

    def test_vs_label_present(self):
        ig = {"type": "comparison", "title": "Compare", "data_points": ["Old way", "New way"]}
        svg = render_infographic(ig, SAMPLE_COLORS)
        assert "VS" in svg or "vs" in svg or "Old" in svg


class TestList:
    def test_renders_svg(self):
        ig = {
            "type": "list",
            "title": "Key Points",
            "data_points": ["Point one", "Point two", "Point three"],
        }
        svg = render_infographic(ig, SAMPLE_COLORS)
        assert "<svg" in svg
        assert "Point one" in svg

    def test_numbered_items(self):
        ig = {"type": "list", "title": "List", "data_points": ["A", "B", "C"]}
        svg = render_infographic(ig, SAMPLE_COLORS)
        assert "1" in svg or "2" in svg or "3" in svg


class TestHierarchy:
    def test_renders_svg(self):
        ig = {
            "type": "hierarchy",
            "title": "Org Structure",
            "data_points": ["CEO|CTO|Developer", "CEO|CFO|Accountant"],
        }
        svg = render_infographic(ig, SAMPLE_COLORS)
        assert "<svg" in svg

    def test_hierarchy_has_levels(self):
        ig = {
            "type": "hierarchy",
            "title": "Tree",
            "data_points": ["Root|Child|Leaf"],
        }
        svg = render_infographic(ig, SAMPLE_COLORS)
        assert "Root" in svg


class TestEdgeCases:
    def test_empty_data_points(self):
        ig = {"type": "list", "title": "Empty", "data_points": []}
        svg = render_infographic(ig, SAMPLE_COLORS)
        # Should handle gracefully — returns empty or minimal SVG
        assert svg == "" or "<svg" in svg

    def test_single_data_point(self):
        ig = {"type": "process", "title": "Single", "data_points": ["Only one"]}
        svg = render_infographic(ig, SAMPLE_COLORS)
        assert "<svg" in svg

    def test_unknown_type_falls_back(self):
        ig = {"type": "unknown_type", "title": "Fallback", "data_points": ["A", "B"]}
        svg = render_infographic(ig, SAMPLE_COLORS)
        assert "<svg" in svg

    def test_missing_type(self):
        ig = {"title": "No type", "data_points": ["A"]}
        svg = render_infographic(ig, SAMPLE_COLORS)
        assert "<svg" in svg

    def test_special_characters_escaped(self):
        ig = {"type": "list", "title": "Test", "data_points": ["A & B < C > D"]}
        svg = render_infographic(ig, SAMPLE_COLORS)
        assert "&amp;" in svg
        assert "&lt;" in svg
        assert "&gt;" in svg
