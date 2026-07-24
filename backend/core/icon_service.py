"""Iconify API integration — modular icon service.
Supports 200,000+ open source icons. Zero cost.
API: https://api.iconify.design"""

import urllib.request
import json
import re

ICONIFY_BASE = "https://api.iconify.design"
CACHE = {}


def get_icon_svg(icon_name: str, color: str = "currentColor", width: int = 24, height: int = 24) -> str:
    """Fetch an SVG icon from Iconify. Caches results in memory.
    
    Args:
        icon_name: e.g. "mdi:home", "fa-solid:book", "heroicons:academic-cap"
        color: CSS color string
        width, height: icon dimensions
    Returns:
        SVG string or empty string on failure
    """
    cache_key = f"{icon_name}_{color}_{width}"
    if cache_key in CACHE:
        return CACHE[cache_key]

    # Normalize: if no prefix, try common ones
    if ":" not in icon_name:
        icon_name = f"mdi:{icon_name}"

    url = f"{ICONIFY_BASE}/{icon_name.replace(':', '/')}.svg?width={width}&height={height}"
    
    svg = _fetch_svg(url, color)
    CACHE[cache_key] = svg
    return svg


def _fetch_svg(url: str, color: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AI-Ebook-Builder/1.0"})
        resp = urllib.request.urlopen(req, timeout=5)
        svg = resp.read().decode("utf-8")
        # Inject color
        svg = svg.replace('currentColor', color)
        if 'stroke="currentColor"' in svg:
            svg = svg.replace('stroke="currentColor"', f'stroke="{color}"')
        return svg
    except Exception:
        return ""


def get_cover_icon(topic: str, accent_color: str = "#4A4A4A", size: int = 80) -> str:
    """Get a topic-appropriate cover icon."""
    icon_map = {
        "finance": "mdi:chart-line",
        "technology": "mdi:chip",
        "health": "mdi:heart-pulse",
        "marketing": "mdi:rocket-launch",
        "education": "mdi:book-open-variant",
        "psychology": "mdi:brain",
        "artificial_intelligence": "mdi:robot",
        "survival": "mdi:compass",
        "business": "mdi:briefcase",
        "general": "mdi:book",
    }
    icon = icon_map.get(topic, "mdi:book")
    return get_icon_svg(icon, color=accent_color, width=size, height=size)
