"""Design Token System — dynamiczny odczyt 20 theme'ów + daisyUI mapping."""
from __future__ import annotations
import os
import re
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_THEMES_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "themes"

# Map: style name -> daisyUI theme name (from CMLP-DesignSystem-Research)
DAISYUI_MAP = {
    "ai": "cmyk",
    "book": "retro",
    "business": "night",
    "cookbook": "garden",
    "corporate": "corporate",
    "cyberpunk": "synthwave",
    "dark": "dark",
    "education": "aqua",
    "finance": "coffee",
    "future": "cyberpunk",
    "health": "emerald",
    "luxury": "luxury",
    "magazine": "wireframe",
    "minimal": "winter",
    "music": "valentine",
    "real_estate": "business",
    "retro": "retro",
    "startup": "lemonade",
    "story": "fantasy",
    "travel": "forest",
}

# Topic -> recommended theme mapping
TOPIC_MAP: Dict[str, list[str]] = {
    "technology": ["ai", "future", "cyberpunk", "minimal"],
    "business": ["corporate", "business", "startup", "finance"],
    "finance": ["finance", "corporate", "book", "luxury"],
    "health": ["health", "book", "cookbook", "education"],
    "education": ["education", "book", "story", "minimal"],
    "marketing": ["startup", "magazine", "corporate", "business"],
    "psychology": ["book", "story", "retro", "luxury"],
    "survival": ["dark", "retro", "real_estate", "book"],
    "cooking": ["cookbook", "book", "magazine", "travel"],
    "travel": ["travel", "magazine", "story", "book"],
    "music": ["music", "magazine", "story", "cyberpunk"],
    "science": ["ai", "future", "education", "minimal"],
    "fiction": ["story", "book", "retro", "magazine"],
    "general": ["minimal", "book", "corporate", "dark"],
    "art": ["magazine", "luxury", "music", "retro"],
}


def _parse_comment(css: str) -> str:
    m = re.search(r"/\*\s*(.+?)\s*\*/", css)
    return m.group(1).strip() if m else ""


def _parse_var(css: str, name: str) -> str:
    m = re.search(rf"--{name}:\s*(.+?);", css)
    return m.group(1).strip() if m else ""


def _load_theme(name: str) -> Optional[Dict[str, Any]]:
    theme_dir = _THEMES_DIR / name
    css_file = theme_dir / "theme.css"
    if not css_file.exists():
        return None
    try:
        css = css_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        css = css_file.read_text(encoding="cp1252")
    vibe = _parse_comment(css)
    return {
        "theme": name,
        "vibe": vibe,
        "colors": {
            "background": _parse_var(css, "color-bg"),
            "surface": _parse_var(css, "color-surface"),
            "text": _parse_var(css, "color-text"),
            "heading": _parse_var(css, "color-heading"),
            "accent": _parse_var(css, "color-accent"),
            "secondary": _parse_var(css, "color-secondary"),
            "muted": _parse_var(css, "color-muted"),
            "border": _parse_var(css, "color-border"),
            "highlight": _parse_var(css, "color-highlight"),
            "success": _parse_var(css, "color-success"),
            "warning": _parse_var(css, "color-warning"),
            "error": _parse_var(css, "color-error"),
            "info": _parse_var(css, "color-info"),
        },
        "fonts": {
            "heading": _parse_var(css, "font-heading"),
            "body": _parse_var(css, "font-body"),
        },
        "font_sizes": {
            "h1": _parse_var(css, "font-size-h1"),
            "h2": _parse_var(css, "font-size-h2"),
            "h3": _parse_var(css, "font-size-h3"),
            "body": _parse_var(css, "font-size-body"),
        },
        "spacing": {
            "xs": _parse_var(css, "spacing-xs"),
            "sm": _parse_var(css, "spacing-sm"),
            "md": _parse_var(css, "spacing-md"),
            "lg": _parse_var(css, "spacing-lg"),
            "xl": _parse_var(css, "spacing-xl"),
            "2xl": _parse_var(css, "spacing-2xl"),
            "3xl": _parse_var(css, "spacing-3xl"),
        },
        "radii": {
            "sm": _parse_var(css, "radius-sm"),
            "md": _parse_var(css, "radius-md"),
            "lg": _parse_var(css, "radius-lg"),
            "xl": _parse_var(css, "radius-xl"),
        },
        "shadows": {
            "sm": _parse_var(css, "shadow-sm"),
            "md": _parse_var(css, "shadow-md"),
            "lg": _parse_var(css, "shadow-lg"),
        },
        "page": {
            "format": "A4",
            "margin_top": "2cm",
            "margin_right": "2cm",
            "margin_bottom": "2cm",
            "margin_left": "2cm",
            "line_height": _parse_var(css, "line-height"),
            "content_width": _parse_var(css, "content-width"),
            "footer_font_size": "8pt",
        },
        "cover_gradient": _parse_var(css, "cover-gradient"),
        "accent_gradient": _parse_var(css, "accent-gradient"),
        "custom_css": "",
        "daisyui_theme": DAISYUI_MAP.get(name, "winter"),
    }


def generate_design_system(style: str, tone: str = "") -> Dict[str, Any]:
    theme = _load_theme(style)
    if theme:
        return theme
    # Fallback: try to match by tone or topic
    for topic, styles in TOPIC_MAP.items():
        if topic in tone.lower() or tone.lower() in topic:
            theme = _load_theme(styles[0])
            if theme:
                return theme
    return _load_theme("minimal") or {"theme": "minimal"}


def list_themes() -> List[Dict[str, str]]:
    themes = []
    for d in sorted(_THEMES_DIR.iterdir()):
        if d.is_dir():
            css_file = d / "theme.css"
            if css_file.exists():
                try:
                    css = css_file.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    css = css_file.read_text(encoding="cp1252")
                vibe = _parse_comment(css)
                themes.append({
                    "id": d.name,
                    "name": d.name.replace("_", " ").title(),
                    "vibe": vibe,
                    "daisyui_theme": DAISYUI_MAP.get(d.name, "winter"),
                })
    return themes


def get_theme_topics(style: str) -> List[str]:
    return [t for t, s in TOPIC_MAP.items() if style in s]


def get_tokens_for_ai() -> str:
    """Return a condensed token summary for AI agent prompts."""
    lines = ["Available themes and their design tokens:"]
    for theme in list_themes():
        t = _load_theme(theme["id"])
        if not t:
            continue
        colors = t["colors"]
        lines.append(
            f"- {theme['id']}: vibe='{theme['vibe']}', "
            f"bg={colors['background']} text={colors['text']} "
            f"accent={colors['accent']}"
        )
    lines.append("\nTopic-to-theme recommendations:")
    for topic, styles in sorted(TOPIC_MAP.items()):
        lines.append(f"  {topic}: {', '.join(styles)}")
    return "\n".join(lines)
