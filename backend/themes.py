"""Theme registry — 50 professional design themes (auto-loaded from CSS).
Each theme defines complete design tokens for the AI Design Engine.

Covers ebook styling directly (backend/core/builder.py) and, via the same
get_theme(style) lookup, the color/font tokens for website/landing-page/
blog-post output (backend/core/website.py) and interactive-book output
(backend/core/interactive.py) — one shared palette pool, five content
types. Palettes are adapted from established MIT-licensed open-source
color systems (Open Color, Nord, Catppuccin, Dracula, Solarized, GitHub
Primer) paired with OFL-licensed Google Fonts — not copied verbatim HTML/
CSS, since none of those upstream projects ship ebook page templates.
"""

from pathlib import Path

from backend.core.tokens import _load_theme

_COVER_ICONS = {
    "business": "mdi:briefcase", "dark": "mdi:weather-night", "ai": "mdi:robot",
    "finance": "mdi:chart-line", "health": "mdi:heart-pulse", "luxury": "mdi:diamond",
    "magazine": "mdi:fire", "corporate": "mdi:office-building", "minimal": "mdi:book",
    "book": "mdi:book-open-page-variant", "story": "mdi:feather", "education": "mdi:school",
    "cookbook": "mdi:silverware-fork-knife", "travel": "mdi:compass", "real_estate": "mdi:home-city",
    "music": "mdi:music-note", "startup": "mdi:rocket-launch", "cyberpunk": "mdi:lightning-bolt",
    "retro": "mdi:record-player", "future": "mdi:wave",
    # Restored phantom themes (previously listed here with no matching
    # theme.css — see git history) plus the 25 new themes added alongside.
    "modern": "mdi:shape-outline", "wellness": "mdi:spa", "academic": "mdi:school-outline",
    "technical": "mdi:code-braces", "creative": "mdi:palette",
    "landing": "mdi:rocket", "blog": "mdi:pencil", "docs": "mdi:file-document-outline",
    "portfolio": "mdi:image-multiple", "saas": "mdi:cloud-outline", "product": "mdi:package-variant",
    "leadgen": "mdi:bullhorn", "tutorial": "mdi:compass-outline", "listicle": "mdi:format-list-numbered",
    "interview": "mdi:microphone-outline",
    "legal": "mdi:scale-balance", "medical": "mdi:medical-bag", "nonprofit": "mdi:hand-heart",
    "kids": "mdi:teddy-bear", "fantasy": "mdi:sword-cross", "scifi": "mdi:rocket-launch-outline",
    "wedding": "mdi:ring", "fitness": "mdi:dumbbell", "fashion": "mdi:hanger",
    "architecture": "mdi:office-building-outline", "podcast": "mdi:podcast", "newsletter": "mdi:email-newsletter",
    "agency": "mdi:domain", "government": "mdi:bank", "nature_eco": "mdi:leaf",
}

_THEMES = {}
_SPACING = {}
_RADII = {}
_SHADOWS = {}
_PAGE = {}

# Auto-load all themes from CSS files
_THEMES_DIR = Path(__file__).resolve().parent.parent / "templates" / "themes"
for d in sorted(_THEMES_DIR.iterdir()):
    if d.is_dir() and (d / "theme.css").exists():
        name = d.name
        t = _load_theme(name)
        if t:
            _THEMES[name] = {
                "id": name,
                "name": t.get("label") or name.replace("_", " ").title(),
                "vibe": t.get("vibe", ""),
                "colors": t["colors"],
                "fonts": t["fonts"],
                "font_sizes": t.get("font_sizes", {}),
                "cover_gradient": t.get("cover_gradient", ""),
                "accent_gradient": t.get("accent_gradient", ""),
                "cover_icon": _COVER_ICONS.get(name, "mdi:book"),
            }

THEMES = _THEMES  # backward compatibility alias

# Shared design tokens (all themes)
SPACING = {
    "xs": "0.25rem", "sm": "0.5rem", "md": "1rem", "lg": "1.5rem",
    "xl": "2rem", "2xl": "3rem", "3xl": "4rem",
}
RADII = {"sm": "4px", "md": "8px", "lg": "12px", "xl": "16px"}
SHADOWS = {"sm": "0 1px 2px rgba(0,0,0,0.05)", "md": "0 4px 6px rgba(0,0,0,0.07)", "lg": "0 10px 15px rgba(0,0,0,0.1)"}
PAGE = {
    "format": "A4", "margin_top": "2.2cm", "margin_bottom": "2.5cm",
    "margin_left": "2cm", "margin_right": "2cm",
    "footer_font_size": "7pt", "line_height": 1.75,
    "content_width": "14cm",
}


def get_theme(theme_id: str) -> dict:
    """Get complete theme with defaults applied."""
    base = _THEMES.get(theme_id, _THEMES.get("minimal", {}))
    return {
        **base,
        "spacing": SPACING,
        "radii": RADII,
        "shadows": SHADOWS,
        "page": PAGE,
        "custom_css": "",
    }


def list_themes() -> list[dict]:
    """List all themes for frontend display."""
    return [
        {"id": t["id"], "name": t["name"], "vibe": t["vibe"],
         "colors": t["colors"], "cover_icon": t["cover_icon"]}
        for t in _THEMES.values()
    ]


def generate_theme_css(theme_id: str) -> str:
    """Generate complete CSS with design tokens for a theme."""
    t = get_theme(theme_id)
    cols = t["colors"]
    return f"""/* {t['name']} — {t['vibe']} */
:root {{
  --color-bg: {cols['background']};
  --color-surface: {cols['surface']};
  --color-text: {cols['text']};
  --color-heading: {cols['heading']};
  --color-accent: {cols['accent']};
  --color-secondary: {cols['secondary']};
  --color-muted: {cols['muted']};
  --color-border: {cols['border']};
  --color-highlight: {cols['highlight']};
  --color-success: {cols['success']};
  --color-warning: {cols['warning']};
  --color-error: {cols['error']};
  --color-info: {cols['info']};
  --font-heading: {t['fonts']['heading']};
  --font-body: {t['fonts']['body']};
  --font-size-h1: {t['font_sizes']['h1']};
  --font-size-h2: {t['font_sizes']['h2']};
  --font-size-h3: {t['font_sizes']['h3']};
  --font-size-body: {t['font_sizes']['body']};
  --cover-gradient: {t['cover_gradient']};
  --accent-gradient: {t['accent_gradient']};
}}"""
