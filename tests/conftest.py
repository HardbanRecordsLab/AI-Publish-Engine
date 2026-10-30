import os, sys, json
import pytest

os.environ["GROQ_API_KEY"] = "test-placeholder-key"
os.environ["AI_PROVIDER"] = "mistral"



@pytest.fixture(autouse=True)
def _checkpoints_in_tmp(monkeypatch, tmp_path):
    """Checkpoints (inputs and finished steps of a job) never go into the real jobs/ folder from a test."""
    monkeypatch.setenv("AI_CHECKPOINT_DIR", str(tmp_path / "checkpoints"))


SAMPLE_TEXT = """Artificial intelligence is transforming healthcare, finance, and education.
Machine learning enables pattern recognition and predictive analytics.
Deep learning uses neural networks to solve complex problems.
The future of AI includes autonomous systems and human-AI collaboration."""


@pytest.fixture
def sample_text():
    return SAMPLE_TEXT


@pytest.fixture
def sample_analysis():
    return {
        "title": "The AI Revolution",
        "subtitle": "How Machine Learning Changes Everything",
        "author": "AI Ebook Builder",
        "topic": "technology",
        "tone": "professional",
        "audience": "business professionals",
        "summary": "A comprehensive guide to AI",
        "chapters": [
            {
                "title": "Understanding AI",
                "introduction": "AI is transforming our world.",
                "key_takeaway": "AI is a tool, not a threat.",
                "sections": [
                    {"heading": "What is AI?", "content": "AI refers to machine intelligence."},
                    {"heading": "History of AI", "content": "AI has evolved over decades."},
                    {"heading": "Types of AI", "content": "Narrow vs general AI."},
                ],
            },
            {
                "title": "Machine Learning",
                "introduction": "ML is the engine of modern AI.",
                "key_takeaway": "Data is the fuel for ML.",
                "sections": [
                    {"heading": "Supervised Learning", "content": "Learning from labeled data."},
                    {"heading": "Unsupervised Learning", "content": "Finding patterns in data."},
                ],
            },
            {
                "title": "The Future",
                "introduction": "What lies ahead.",
                "key_takeaway": "AGI is the ultimate goal.",
                "sections": [
                    {"heading": "Challenges", "content": "Safety and alignment."},
                    {"heading": "Opportunities", "content": "AI for good."},
                ],
            },
        ],
        "conclusion": {
            "title": "Conclusion",
            "content": "AI will continue to shape our future.",
        },
    }


@pytest.fixture
def sample_design():
    return {
        "theme": "minimal",
        "colors": {
            "background": "#FFFFFF", "text": "#1A1A1A", "heading": "#000000",
            "accent": "#4A4A4A", "secondary": "#F5F5F5", "muted": "#999999",
            "border": "#E5E5E5", "highlight": "#F0F0F0",
        },
        "fonts": {"heading": "Georgia, serif", "body": "Helvetica, sans-serif"},
        "cover_gradient": "linear-gradient(135deg, #FAFAFA 0%, #FFFFFF 100%)",
        "accent_gradient": "linear-gradient(135deg, #4A4A4A 0%, #6A6A6A 100%)",
        "vibe": "clean minimal professional",
    }


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Per-endpoint limits (e.g. 10/min on /api/generate) are process-wide;
    without a reset, the number of tests that hit an endpoint decides whether
    a later one gets 429."""
    from backend.limiter import limiter
    limiter.reset()
    yield
