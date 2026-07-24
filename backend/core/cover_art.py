"""SVG cover art and chapter illustrations — zero-cost AI-generated graphics."""
import math
import random
from datetime import datetime


def _pattern_geometric(w, h, colors):
    """Geometric polygon background pattern."""
    accent, secondary = colors["accent"], colors.get("secondary", "#1E293B")
    bg = colors.get("background", "#0F172A")
    svg = f'<rect width="{w}" height="{h}" fill="{bg}"/>'
    # Triangles
    for i in range(6):
        x = random.randint(0, w)
        y = random.randint(0, int(h * 0.6))
        s = random.randint(60, 160)
        rot = random.randint(0, 360)
        fill = accent if i % 2 == 0 else secondary
        opacity = round(random.uniform(0.05, 0.2), 2)
        svg += f'<polygon points="{x},{y} {x+s},{y} {x+s//2},{y-int(s*0.866)}" fill="{fill}" opacity="{opacity}" transform="rotate({rot},{x+s//2},{y})"/>'
    # Large circle
    svg += f'<circle cx="{w*0.85}" cy="{h*0.3}" r="{w*0.35}" fill="{accent}" opacity="0.04"/>'
    svg += f'<circle cx="{w*0.15}" cy="{h*0.7}" r="{w*0.25}" fill="{secondary}" opacity="0.06"/>'
    return svg


def _pattern_waves(w, h, colors):
    """Smooth wave patterns."""
    accent = colors["accent"]
    bg = colors.get("background", "#0F172A")
    svg = f'<rect width="{w}" height="{h}" fill="{bg}"/>'
    for i in range(3):
        amp = 30 + i * 15
        freq = 0.01 + i * 0.005
        phase = i * 1.5
        opacity = round(0.04 + i * 0.03, 2)
        points = []
        for x in range(0, w + 5, 5):
            y = h - 40 - i * 60 + math.sin(x * freq + phase) * amp
            points.append(f"{x},{y}")
        svg += f'<polyline points="{" ".join(points)}" fill="none" stroke="{accent}" stroke-width="2" opacity="{opacity}"/>'
    return svg


def _pattern_dots(w, h, colors):
    """Dot grid pattern."""
    accent = colors["accent"]
    bg = colors.get("background", "#0F172A")
    svg = f'<rect width="{w}" height="{h}" fill="{bg}"/>'
    spacing = 30
    for x in range(0, w + spacing, spacing):
        for y in range(0, h + spacing, spacing):
            r = 1 + math.sin(x * 0.05 + y * 0.05) * 1
            opacity = round(0.03 + math.sin(x * 0.03 + y * 0.03) * 0.03, 3)
            svg += f'<circle cx="{x}" cy="{y}" r="{abs(r)}" fill="{accent}" opacity="{abs(opacity)}"/>'
    # Accent blob
    svg += f'<circle cx="{w*0.5}" cy="{h*0.4}" r="{w*0.3}" fill="{accent}" opacity="0.05"/>'
    return svg


def _pattern_circles(w, h, colors):
    """Concentric overlapping circles."""
    accent, secondary = colors["accent"], colors.get("secondary", "#1E293B")
    bg = colors.get("background", "#0F172A")
    svg = f'<rect width="{w}" height="{h}" fill="{bg}"/>'
    centers = [(w * 0.2, h * 0.7), (w * 0.8, h * 0.3), (w * 0.5, h * 0.8)]
    for cx, cy in centers:
        for r in range(int(max(w, h) * 0.1), int(max(w, h) * 0.6), 20):
            opacity = round(0.02 + r * 0.0003, 3)
            color = accent if (r // 20) % 2 == 0 else secondary
            svg += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="1" opacity="{min(opacity, 0.1)}"/>'
    return svg


def _pattern_grid(w, h, colors):
    """Isometric grid pattern."""
    accent = colors["accent"]
    bg = colors.get("background", "#0F172A")
    svg = f'<rect width="{w}" height="{h}" fill="{bg}"/>'
    spacing = 40
    for x in range(-spacing, w + spacing, spacing):
        points = []
        for y in range(-spacing, h + spacing, spacing):
            px = x + (y / spacing % 2) * (spacing / 2)
            points.append(f"{px},{y}")
        svg += f'<polyline points="{" ".join(points)}" fill="none" stroke="{accent}" stroke-width="0.5" opacity="0.06"/>'
    for y in range(-spacing, h + spacing, spacing):
        points = []
        for x in range(-spacing, w + spacing, spacing):
            px = x + (y / spacing % 2) * (spacing / 2)
            points.append(f"{px},{y}")
        svg += f'<polyline points="{" ".join(points)}" fill="none" stroke="{accent}" stroke-width="0.5" opacity="0.04"/>'
    return svg


PATTERNS = [_pattern_geometric, _pattern_waves, _pattern_dots, _pattern_circles, _pattern_grid]
_used_patterns = {}


def _pick_pattern(topic, colors):
    """Deterministic pattern picker based on topic hash."""
    idx = hash(topic) % len(PATTERNS)
    return PATTERNS[idx]


def generate_cover_svg(title, subtitle, author, topic, colors, fonts, date=None):
    """Generate a full A4 cover SVG with art."""
    w, h = 595, 842  # A4 at 72dpi
    pattern = _pick_pattern(topic, colors)
    background = pattern(w, h, colors)

    title_font = fonts.get("heading", "'Georgia', serif")
    body_font = fonts.get("body", "'Inter', sans-serif")
    accent = colors["accent"]
    text_color = colors.get("heading", "#FFFFFF")
    muted = colors.get("muted", "#94A3B8")
    date = date or datetime.now().strftime("%B %d, %Y")

    # Title block with decorative line
    title_svg = f'''
    <text x="{w/2}" y="{h*0.48}" font-family="{title_font}" font-size="36" font-weight="800"
          fill="{text_color}" text-anchor="middle" letter-spacing="-1">{_esc(title)}</text>
    '''
    if subtitle:
        title_svg += f'''
    <text x="{w/2}" y="{h*0.48 + 22}" font-family="{body_font}" font-size="14"
          fill="{muted}" text-anchor="middle" opacity="0.8">{_esc(subtitle)}</text>
        '''
    # Decorative divider
    title_svg += f'''
    <line x1="{w/2 - 40}" y1="{h*0.48 + 38}" x2="{w/2 + 40}" y2="{h*0.48 + 38}"
          stroke="{accent}" stroke-width="2" opacity="0.6"/>
    <text x="{w/2}" y="{h*0.48 + 60}" font-family="{body_font}" font-size="10"
          fill="{muted}" text-anchor="middle" letter-spacing="2" opacity="0.7">{_esc(author)}</text>
    '''

    # Bottom info
    bottom_svg = f'''
    <text x="{w/2}" y="{h - 60}" font-family="{body_font}" font-size="9"
          fill="{muted}" text-anchor="middle" opacity="0.5">{_esc(date)}</text>
    '''

    # Topic icon hint (simple decorative mark)
    icon_size = 50
    icon_svg = f'''
    <circle cx="{w/2}" cy="{h*0.35}" r="{icon_size}" fill="none" stroke="{accent}" stroke-width="1" opacity="0.15"/>
    <circle cx="{w/2}" cy="{h*0.35}" r="{icon_size - 10}" fill="none" stroke="{accent}" stroke-width="1" opacity="0.1"/>
    '''

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" height="100%">
  <defs>
    <linearGradient id="coverAccent" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.1"/>
      <stop offset="100%" stop-color="{accent}" stop-opacity="0.02"/>
    </linearGradient>
    <rect id="coverBg" width="{w}" height="{h}" fill="url(#coverAccent)"/>
  </defs>
  {background}
  {icon_svg}
  {title_svg}
  {bottom_svg}
</svg>'''


def generate_illustration(topic, chapter_title, chapter_index, colors):
    """Generate a chapter illustration SVG."""
    w, h = 800, 200
    accent = colors["accent"]
    secondary = colors.get("secondary", "#1E293B")
    bg = colors.get("surface", "#1E293B")
    muted = colors.get("muted", "#64748B")

    # Deterministic shapes based on chapter index
    shapes = []
    for i in range(5):
        x = 80 + i * 170
        y = 100 + math.sin(chapter_index * 2 + i) * 30
        r = 20 + math.sin(i * 3) * 10
        opacity = round(0.1 + i * 0.04, 2)
        color = accent if i % 2 == 0 else secondary
        shapes.append(f'<circle cx="{x}" cy="{y}" r="{abs(r)}" fill="{color}" opacity="{abs(opacity)}"/>')

    # Connecting lines
    lines = []
    for i in range(4):
        x1 = 80 + i * 170 + 20
        y1 = 100 + math.sin(chapter_index * 2 + i) * 30
        x2 = 80 + (i + 1) * 170 - 20
        y2 = 100 + math.sin(chapter_index * 2 + i + 1) * 30
        lines.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{accent}" stroke-width="1" opacity="0.15"/>')

    chapter_label = f"Chapter {chapter_index + 1}"

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" height="100%">
  <rect width="{w}" height="{h}" fill="{bg}" rx="12"/>
  {"".join(lines)}
  {"".join(shapes)}
  <text x="{w/2}" y="{h - 30}" font-family="'Inter', sans-serif" font-size="11"
        fill="{muted}" text-anchor="middle" letter-spacing="2" opacity="0.5">{_esc(chapter_label)}</text>
</svg>'''


def _esc(text):
    """Escape text for SVG."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
