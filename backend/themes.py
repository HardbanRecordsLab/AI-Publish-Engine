"""Theme registry — 20 professional design themes (auto-loaded from CSS).
Each theme defines complete design tokens for the AI Design Engine."""

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
}
# NOTE: "modern", "academic", "creative", "technical" and "wellness" used to
# have entries here but have no matching templates/themes/<name>/theme.css —
# get_theme() silently falls back to "minimal" for them. Removed rather than
# left dangling; add them back once (if) real theme.css files are authored.

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
                "name": name.replace("_", " ").title(),
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
