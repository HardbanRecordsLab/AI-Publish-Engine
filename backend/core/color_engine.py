"""Topic-based color palette engine.
Modular — add/remove topics and palettes freely."""

TOPIC_PALETTES = {
    "finance": {
        "name": "Financial",
        "colors": {
            "background": "#FDFBF7", "text": "#1C1C1C", "heading": "#1A1A2E",
            "accent": "#B8860B", "secondary": "#F5F0E8", "muted": "#8B7355",
            "border": "#D4C5A9", "highlight": "#FAF6EF",
        },
        "fonts": {"heading": "Georgia, serif", "body": "'Inter', sans-serif"},
        "cover_gradient": "linear-gradient(135deg, #1A1A2E 0%, #2D2D44 50%, #B8860B 100%)",
        "accent_gradient": "linear-gradient(135deg, #B8860B 0%, #DAA520 100%)",
        "vibe": "premium authoritative",
    },
    "technology": {
        "name": "Technology",
        "colors": {
            "background": "#F8FAFC", "text": "#0F172A", "heading": "#020617",
            "accent": "#06B6D4", "secondary": "#ECFEFF", "muted": "#64748B",
            "border": "#CBD5E1", "highlight": "#F0F9FF",
        },
        "fonts": {"heading": "'Inter', sans-serif", "body": "'Inter', sans-serif"},
        "cover_gradient": "linear-gradient(135deg, #020617 0%, #0F172A 50%, #06B6D4 100%)",
        "accent_gradient": "linear-gradient(135deg, #06B6D4 0%, #3B82F6 100%)",
        "vibe": "modern innovative",
    },
    "health": {
        "name": "Health & Wellness",
        "colors": {
            "background": "#F8FAF5", "text": "#1A2E1A", "heading": "#0F1F0F",
            "accent": "#22C55E", "secondary": "#F0FDF4", "muted": "#6B8E6B",
            "border": "#BBE8BB", "highlight": "#F0FFF4",
        },
        "fonts": {"heading": "Georgia, serif", "body": "'Inter', sans-serif"},
        "cover_gradient": "linear-gradient(135deg, #0F1F0F 0%, #1A3A1A 50%, #22C55E 100%)",
        "accent_gradient": "linear-gradient(135deg, #22C55E 0%, #16A34A 100%)",
        "vibe": "fresh natural",
    },
    "marketing": {
        "name": "Marketing",
        "colors": {
            "background": "#FFFCF5", "text": "#1C1917", "heading": "#0C0A09",
            "accent": "#F97316", "secondary": "#FFF7ED", "muted": "#A8A29E",
            "border": "#E7E5E4", "highlight": "#FFF9F0",
        },
        "fonts": {"heading": "'Poppins', sans-serif", "body": "'Inter', sans-serif"},
        "cover_gradient": "linear-gradient(135deg, #0C0A09 0%, #292524 50%, #F97316 100%)",
        "accent_gradient": "linear-gradient(135deg, #F97316 0%, #EA580C 100%)",
        "vibe": "energetic bold",
    },
    "education": {
        "name": "Education",
        "colors": {
            "background": "#FAFAFA", "text": "#1E293B", "heading": "#0F172A",
            "accent": "#6366F1", "secondary": "#EEF2FF", "muted": "#94A3B8",
            "border": "#C7D2FE", "highlight": "#F0F0FF",
        },
        "fonts": {"heading": "Georgia, serif", "body": "'Inter', sans-serif"},
        "cover_gradient": "linear-gradient(135deg, #0F172A 0%, #312E81 50%, #6366F1 100%)",
        "accent_gradient": "linear-gradient(135deg, #6366F1 0%, #818CF8 100%)",
        "vibe": "trustworthy academic",
    },
    "psychology": {
        "name": "Psychology",
        "colors": {
            "background": "#F8FAFF", "text": "#1E1B4B", "heading": "#0F0A3A",
            "accent": "#3B82F6", "secondary": "#EFF6FF", "muted": "#6B7280",
            "border": "#BFDBFE", "highlight": "#F0F5FF",
        },
        "fonts": {"heading": "'Merriweather', serif", "body": "'Inter', sans-serif"},
        "cover_gradient": "linear-gradient(135deg, #0F0A3A 0%, #1E1B4B 50%, #3B82F6 100%)",
        "accent_gradient": "linear-gradient(135deg, #3B82F6 0%, #60A5FA 100%)",
        "vibe": "calm insightful",
    },
    "artificial_intelligence": {
        "name": "AI & Tech",
        "colors": {
            "background": "#F5F3FF", "text": "#1A1A2E", "heading": "#0B0F1A",
            "accent": "#7C4DFF", "secondary": "#F3E8FF", "muted": "#6B7280",
            "border": "#DDD6FE", "highlight": "#FAF5FF",
        },
        "fonts": {"heading": "'Inter', sans-serif", "body": "'Inter', sans-serif"},
        "cover_gradient": "linear-gradient(135deg, #0B0F1A 0%, #1A1A2E 50%, #7C4DFF 100%)",
        "accent_gradient": "linear-gradient(135deg, #7C4DFF 0%, #A855F7 100%)",
        "vibe": "futuristic innovative",
    },
    "survival": {
        "name": "Survival & Outdoors",
        "colors": {
            "background": "#FAF8F0", "text": "#2D2D1A", "heading": "#1A1A0F",
            "accent": "#4A7C3F", "secondary": "#F0F5EB", "muted": "#8B8B5A",
            "border": "#C4D4B8", "highlight": "#F5FAF0",
        },
        "fonts": {"heading": "'Inter', sans-serif", "body": "'Inter', sans-serif"},
        "cover_gradient": "linear-gradient(135deg, #1A1A0F 0%, #2D2D1A 50%, #4A7C3F 100%)",
        "accent_gradient": "linear-gradient(135deg, #4A7C3F 0%, #5C9A4E 100%)",
        "vibe": "rugged natural",
    },
    "business": {
        "name": "Business",
        "colors": {
            "background": "#FFFFFF", "text": "#1E2A3A", "heading": "#0F172A",
            "accent": "#2563EB", "secondary": "#F0F4FF", "muted": "#64748B",
            "border": "#CBD5E1", "highlight": "#EFF6FF",
        },
        "fonts": {"heading": "Georgia, serif", "body": "'Inter', sans-serif"},
        "cover_gradient": "linear-gradient(135deg, #0F172A 0%, #1E40AF 50%, #2563EB 100%)",
        "accent_gradient": "linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)",
        "vibe": "professional structured",
    },
    "general": {
        "name": "Clean Modern",
        "colors": {
            "background": "#FFFFFF", "text": "#1A1A1A", "heading": "#000000",
            "accent": "#4A4A4A", "secondary": "#F5F5F5", "muted": "#999999",
            "border": "#E5E5E5", "highlight": "#F0F0F0",
        },
        "fonts": {"heading": "Georgia, serif", "body": "'Inter', sans-serif"},
        "cover_gradient": "linear-gradient(135deg, #FAFAFA 0%, #FFFFFF 100%)",
        "accent_gradient": "linear-gradient(135deg, #4A4A4A 0%, #6A6A6A 100%)",
        "vibe": "clean minimal",
    },
}

# Topic keyword matching
TOPIC_KEYWORDS = {
    "finance": ["finance", "money", "invest", "bank", "financial", "economy", "stock", "wealth", "budget", "saving", "crypto", "trading", "market"],
    "technology": ["technology", "tech", "software", "digital", "computer", "code", "programming", "AI", "data", "web", "app", "startup", "innovation"],
    "health": ["health", "wellness", "fitness", "medical", "nutrition", "diet", "exercise", "mental", "therapy", "healing", "sleep", "yoga"],
    "marketing": ["marketing", "brand", "social media", "seo", "advertising", "sales", "content", "audience", "campaign", "growth", "conversion"],
    "education": ["education", "learn", "teaching", "course", "study", "training", "skill", "knowledge", "academic", "school", "student", "lesson"],
    "psychology": ["psychology", "mind", "behavior", "habit", "emotion", "brain", "cognitive", "mental health", "personality", "motivation"],
    "artificial_intelligence": ["artificial intelligence", "machine learning", "deep learning", "neural", "GPT", "LLM", "AI", "automation", "robot", "chatbot"],
    "survival": ["survival", "outdoor", "prepper", "wilderness", "emergency", "camping", "hiking", "bushcraft", "self-reliance", "shelter"],
    "business": ["business", "entrepreneur", "management", "leadership", "strategy", "corporate", "startup", "executive", "organization", "team"],
}


def detect_topic(analysis: dict) -> str:
    """Detect ebook topic from AI analysis + keywords. Returns a topic key."""
    topic_field = (analysis.get("topic") or "").lower()
    title = (analysis.get("title") or "").lower()
    combined = f"{topic_field} {title}"

    # Also check chapter titles
    for ch in analysis.get("chapters", []):
        combined += " " + (ch.get("title") or "").lower()

    best_topic = "general"
    best_score = 0
    for topic, keywords in TOPIC_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in combined)
        if score > best_score:
            best_score = score
            best_topic = topic

    return best_topic


def get_color_palette(topic: str) -> dict:
    """Get full color palette for a topic. Falls back to 'general'."""
    return TOPIC_PALETTES.get(topic, TOPIC_PALETTES["general"])


def list_topics() -> list:
    """List all available topic palettes for frontend display."""
    return [{"id": k, "name": v["name"], "colors": v["colors"], "vibe": v["vibe"]} for k, v in TOPIC_PALETTES.items()]
