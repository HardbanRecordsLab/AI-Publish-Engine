"""Generate theme.css + cover-icon.svg for all 20 themes."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.themes import THEMES, SPACING, RADII, SHADOWS, PAGE

THEMES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates", "themes")

ICON_SVGS = {
    "mdi:briefcase": '<svg viewBox="0 0 24 24" width="{size}" height="{size}"><path fill="{color}" d="M10 2h4a2 2 0 0 1 2 2v2h4a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4V4a2 2 0 0 1 2-2m0 2v2h4V4h-4m-4 7v2h12v-2H6m0 4v2h8v-2H6Z"/></svg>',
    "mdi:weather-night": '<svg viewBox="0 0 24 24" width="{size}" height="{size}"><path fill="{color}" d="M17.75 4.09L15.22 6.03l1.06 1.06 2.63-1.77L17.75 4.09M20 20a7.5 7.5 0 1 1-5.73-12.3A7.5 7.5 0 0 0 20 20Z"/></svg>',
    "mdi:robot": '<svg viewBox="0 0 24 24" width="{size}" height="{size}"><path fill="{color}" d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1v1a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-1H2a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2M9.5 13A1.5 1.5 0 0 0 8 14.5a1.5 1.5 0 0 0 1.5 1.5 1.5 1.5 0 0 0 1.5-1.5A1.5 1.5 0 0 0 9.5 13m5 0a1.5 1.5 0 0 0-1.5 1.5 1.5 1.5 0 0 0 1.5 1.5 1.5 1.5 0 0 0 1.5-1.5 1.5 1.5 0 0 0-1.5-1.5M12 15l-2 2h4l-2-2Z"/></svg>',
    "mdi:chart-line": '<svg viewBox="0 0 24 24" width="{size}" height="{size}"><path fill="{color}" d="M3 3h18v2H5v12h14v-7l4 4v9H3V3m17 5.5V7l-4 4-3-3-4 4-3-3 1.5-1.5L10 11l3-3 3 3 4-4.5Z"/></svg>',
    "mdi:heart-pulse": '<svg viewBox="0 0 24 24" width="{size}" height="{size}"><path fill="{color}" d="M7.5 4A5.5 5.5 0 0 0 2 9.5c0 .5.09 1 .22 1.5H6.3l1.27-3.37c.3-.8 1.48-.88 1.86 0L11.5 13l.9-2.3c.15-.38.54-.7 1-.7H22c.13-.5.22-1 .22-1.5A5.5 5.5 0 0 0 16.5 4c-1.86 0-3.5.93-4.5 2.34C11 4.93 9.36 4 7.5 4M3 12.5a1 1 0 0 0-1 1 1 1 0 0 0 1 1h2.44L11 20c.5.6 1.5.6 2 0l3.56-4.5H21a1 1 0 0 0 1-1 1 1 0 0 0-1-1h-5.56l-.9 2.3c-.15.38-.54.7-1 .7H11.5l-.9-2.3c-.15-.38-.54-.7-1-.7H3Z"/></svg>',
    "mdi:diamond": '<svg viewBox="0 0 24 24" width="{size}" height="{size}"><path fill="{color}" d="M6 2L2 8l10 14L22 8l-4-6H6m.67 2h5.66l-2 6H5.83l.84-6M9.53 12l2-6h2.6l1.94 6h-6.54Z"/></svg>',
    "mdi:fire": '<svg viewBox="0 0 24 24" width="{size}" height="{size}"><path fill="{color}" d="M17.55 11.2c-1.21-2.07-2.33-3.49-2.21-5.34 0-.13-.08-.22-.2-.19-1.7.4-2.76 1.9-3.46 3.23-1.02 1.96-1.37 3.84-2.88 5.08 0 0-.68-1.62.04-3.61.1-.27-.16-.48-.38-.35-1.13.67-2.43 2.02-3.16 3.51C4.3 14.87 4.3 17 5.39 18.56 6.96 20.74 9.57 22 12.26 22c3.12 0 6.22-1.68 6.95-5.02.7-3.17-.87-6.3-1.66-5.78Z"/></svg>',
    "mdi:office-building": '<svg viewBox="0 0 24 24" width="{size}" height="{size}"><path fill="{color}" d="M5 3v18h6v-3.5h2V21h6V3H5m2 4h2v2H7V7m4 0h2v2h-2V7m4 0h2v2h-2V7M7 11h2v2H7v-2m4 0h2v2h-2v-2m4 0h2v2h-2v-2M7 15h2v2H7v-2m4 0h2v2h-2v-2m4 0h2v2h-2v-2Z"/></svg>',
    "mdi:book": '<svg viewBox="0 0 24 24" width="{size}" height="{size}"><path fill="{color}" d="M18 2a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h12m-6 2v5l2.5-1.5L17 9V4h-5Z"/></svg>',
    "mdi:book-open-page-variant": '<svg viewBox="0 0 24 24" width="{size}" height="{size}"><path fill="{color}" d="M19 2l-5 4.5v11l5-4.5V2M6.5 5C4.55 5 2.45 5.12 2 5.25v15.5c.45-.13 2.55-.25 4.5-.25 2.2 0 4.73.27 6 .75V6.5c-1.27-.48-3.8-.75-6-.75m11.5 2.2v11c0 .61.35 1.14.5 1.3v.08c-.77-.18-2.11-.36-3.5-.46L17 9.2M13 6.5v12.5c1.27.48 3.8.75 6 .75 1.95 0 4.05-.12 4.5-.25V3.75c-.45.13-2.55.25-4.5.25-2.2 0-4.73-.27-6-.75Z"/></svg>',
    "mdi:feather": '<svg viewBox="0 0 24 24" width="{size}" height="{size}"><path fill="{color}" d="M22 2s-7.64 3.64-6.34 9.58c0 0-1.59-2.58-4.36-2.58-1.58 0-2.76.76-3.53 1.57 0 0-2.04-1.57-4.57-.07 0 0 2.42 4.25 6 4.25 0 0-6.04 3.23-5.58 6.25 0 0 5.43-2 8.92-5.66 0 0 0 1.81-.58 2.79 0 0 2.89 1.42 5.28-.53 0 0 1.65 1.59 2.93 1.59.82 0 1.47-.74 2.04-1.46 0 0 2.08.46 2.93-.54.78-.92 1.76-3.82.63-7.16C20.63 5 22 2 22 2Z"/></svg>',
    "mdi:school": '<svg viewBox="0 0 24 24" width="{size}" height="{size}"><path fill="{color}" d="M12 3L1 9l4 2.18v6L12 21l7-3.82v-6l2-1.09V17h2V9L12 3m6.82 6L12 12.72 5.18 9 12 5.28 18.82 9M17 16l-5 2.72L7 16v-3.73L12 15l5-2.73V16Z"/></svg>',
    "mdi:silverware-fork-knife": '<svg viewBox="0 0 24 24" width="{size}" height="{size}"><path fill="{color}" d="M11 9H9V2H7v7H5V2H3v7c0 2.12 1.66 3.84 3.75 3.97V22h2.5v-9.03C11.34 12.84 13 11.12 13 9V2h-2v7m5-3v8h2.5v8H21V2c-2.76 0-5 2.24-5 4Z"/></svg>',
    "mdi:compass": '<svg viewBox="0 0 24 24" width="{size}" height="{size}"><path fill="{color}" d="M12 2A10 10 0 0 0 2 12a10 10 0 0 0 10 10 10 10 0 0 0 10-10A10 10 0 0 0 12 2m0 2a8 8 0 0 1 8 8 8 8 0 0 1-8 8 8 8 0 0 1-8-8 8 8 0 0 1 8-8m-1 7.5v5l5-3-5-2Z"/></svg>',
    "mdi:home-city": '<svg viewBox="0 0 24 24" width="{size}" height="{size}"><path fill="{color}" d="M10 2L2 9v2h2v9h4v-6h4v6h4v-9h2V9L10 2m0 2.5l5 4.5H5l5-4.5M20 11v9h-2v-7h-2v7h-2v-9h6Z"/></svg>',
    "mdi:music-note": '<svg viewBox="0 0 24 24" width="{size}" height="{size}"><path fill="{color}" d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6Z"/></svg>',
    "mdi:rocket-launch": '<svg viewBox="0 0 24 24" width="{size}" height="{size}"><path fill="{color}" d="M13.13 22.19l-1.63-3.83c1.57-.58 3.04-1.36 4.4-2.27l-2.77 6.1M5.64 12.5l-3.83-1.63 6.1-2.77c-.91 1.36-1.69 2.83-2.27 4.4M21.61 2.39S17.64 1.06 12.7 3.9C9 6.04 5.82 9.5 5.82 9.5S4.74 12.3 4.74 13.5c0 .47.08.89.22 1.17 1.07 2.08 3.81 3.39 3.81 3.39s6.09 4.11 8.16 4.11c.48 0 1-.2 1.46-.77.23-.28 1.36-4.08 1.36-4.08s2.14-3.19 3.53-5.94c1.99-4.33.33-8.22.33-8.22M7 14.5c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5Z"/></svg>',
    "mdi:lightning-bolt": '<svg viewBox="0 0 24 24" width="{size}" height="{size}"><path fill="{color}" d="M11 15H6l7-14v8h5l-7 14v-8Z"/></svg>',
    "mdi:record-player": '<svg viewBox="0 0 24 24" width="{size}" height="{size}"><path fill="{color}" d="M5 17a2 2 0 0 1-2 2H2v-2h1l1-7.77A3.96 3.96 0 0 1 8 5.34c2.07.19 3.5 2.16 3.18 4.17L10.7 12h1.04l1.44-1.42c.68-.69 1.28-1.42 1.28-2.58 0-1.34-.84-3.63-3.22-4.08C11.16 2.1 11.6 2 12 2a10 10 0 1 1-7 17.09V17m-1-5.39c0 .77.62 1.39 1.39 1.39h.42c.77 0 1.39-.62 1.39-1.39 0-.59-.36-1.08-.87-1.3.2.37.32.8.32 1.26 0 1.4-1.14 2.54-2.54 2.54h-.4A2.54 2.54 0 0 1 4 12.54v-1.3c.19.26.5.42.85.42h1.5c.38 0 .69-.31.69-.69s-.31-.69-.69-.69H5.77l.23-1.69h.46c.77 0 1.39-.62 1.39-1.39 0-.76-.62-1.38-1.39-1.38H4v2.15m2 10.39H5v4h1v-4m2 0H7v4h1v-4m2 0H9v4h1v-4Z"/></svg>',
    "mdi:wave": '<svg viewBox="0 0 24 24" width="{size}" height="{size}"><path fill="{color}" d="M20 12c0 1.5-.67 3-2 4.5-1.33-1.5-2-3-2-4.5 0-1.5.67-3 2-4.5 1.33 1.5 2 3 2 4.5m-9 0c0 1.5-.67 3-2 4.5-1.33-1.5-2-3-2-4.5 0-1.5.67-3 2-4.5 1.33 1.5 2 3 2 4.5m-7 0c0 1.5-.67 3-2 4.5C.67 15 0 13.5 0 12c0-1.5.67-3 2-4.5 1.33 1.5 2 3 2 4.5Z"/></svg>',
}


def generate():
    for theme_id, tdata in THEMES.items():
        dir_path = os.path.join(THEMES_DIR, theme_id)

        # theme.css
        cols = tdata["colors"]
        css = f"""/* {tdata['name']} — {tdata['vibe']} */
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
  --font-heading: {tdata['fonts']['heading']};
  --font-body: {tdata['fonts']['body']};
  --font-size-h1: {tdata['font_sizes']['h1']};
  --font-size-h2: {tdata['font_sizes']['h2']};
  --font-size-h3: {tdata['font_sizes']['h3']};
  --font-size-body: {tdata['font_sizes']['body']};
  --spacing-xs: {SPACING['xs']};
  --spacing-sm: {SPACING['sm']};
  --spacing-md: {SPACING['md']};
  --spacing-lg: {SPACING['lg']};
  --spacing-xl: {SPACING['xl']};
  --spacing-2xl: {SPACING['2xl']};
  --spacing-3xl: {SPACING['3xl']};
  --radius-sm: {RADII['sm']};
  --radius-md: {RADII['md']};
  --radius-lg: {RADII['lg']};
  --radius-xl: {RADII['xl']};
  --shadow-sm: {SHADOWS['sm']};
  --shadow-md: {SHADOWS['md']};
  --shadow-lg: {SHADOWS['lg']};
  --line-height: {PAGE['line_height']};
  --cover-gradient: {tdata['cover_gradient']};
  --accent-gradient: {tdata['accent_gradient']};
  --content-width: {PAGE['content_width']};
}}
"""
        with open(os.path.join(dir_path, "theme.css"), "w") as f:
            f.write(css)

        # cover-icon.svg
        icon_name = tdata["cover_icon"]
        svg_template = ICON_SVGS.get(icon_name, ICON_SVGS["mdi:book"])
        svg = svg_template.format(color=tdata["colors"]["accent"], size=80)
        # Add svg namespace if missing
        if "xmlns" not in svg:
            svg = svg.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ')
        with open(os.path.join(dir_path, "cover-icon.svg"), "w") as f:
            f.write(svg)

    print(f"Generated {len(THEMES)} themes: CSS + icons")


if __name__ == "__main__":
    generate()
