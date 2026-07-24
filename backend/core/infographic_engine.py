import re


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _wrap(text, max_len=35):
    text = _esc(text)
    if len(text) <= max_len:
        return [text]
    words = text.split()
    lines = []
    current = ""
    for w in words:
        if len(current) + len(w) + 1 <= max_len:
            current = (current + " " + w).strip()
        else:
            lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines


def _text_block(lines, x, y, font_size, color, line_height=1.4):
    svg = ""
    for i, line in enumerate(lines):
        svg += f'<text x="{x}" y="{y + i * font_size * line_height}" font-size="{font_size}" fill="{color}" font-family="system-ui">{line}</text>'
    return svg


def render_process(plan, colors):
    steps = plan.get("data_points", [])
    accent = colors.get("accent", "#2563EB")
    text_color = colors.get("text", "#1A1A1A")
    bg = colors.get("secondary", "#F5F5F5")

    n = len(steps)
    if n == 0:
        return ""
    w = 720
    h = 180
    box_w = min(140, (w - 80) // n)
    box_h = 60
    gap = min(30, (w - n * box_w) // (n + 1))
    start_x = (w - (n * box_w + (n - 1) * gap)) // 2

    svg = f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">'
    svg += f'<rect width="{w}" height="{h}" rx="12" fill="{bg}" opacity="0.5"/>'
    for i, step in enumerate(steps):
        x = start_x + i * (box_w + gap)
        y = 55
        svg += f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="8" fill="{accent}" opacity="0.12"/>'
        svg += f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="8" fill="none" stroke="{accent}" stroke-width="1.5"/>'
        lines = _wrap(step, 22)
        for li, line in enumerate(lines):
            svg += f'<text x="{x + box_w // 2}" y="{y + box_h // 2 + (li - len(lines)//2) * 14 + 4}" text-anchor="middle" fill="{text_color}" font-size="10" font-family="system-ui" font-weight="500">{line}</text>'
        if i < n - 1:
            ax = x + box_w + 2
            ay = y + box_h // 2
            svg += f'<line x1="{ax}" y1="{ay}" x2="{ax + gap - 6}" y2="{ay}" stroke="{accent}" stroke-width="1.5" stroke-dasharray="4,3"/>'
            svg += f'<polygon points="{ax + gap - 3},{ay - 4} {ax + gap - 3},{ay + 4} {ax + gap},{ay}" fill="{accent}"/>'
    svg += f'<text x="{w//2}" y="30" text-anchor="middle" font-size="11" fill="{accent}" font-family="system-ui" font-weight="600" letter-spacing="1">{_esc(plan.get("title", ""))}</text>'
    svg += "</svg>"
    return svg


def render_timeline(plan, colors):
    points = plan.get("data_points", [])
    accent = colors.get("accent", "#2563EB")
    text_color = colors.get("text", "#1A1A1A")
    bg = colors.get("secondary", "#F5F5F5")

    n = len(points)
    if n == 0:
        return ""
    w = 720
    h = 50 + n * 60

    svg = f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">'
    svg += f'<rect width="{w}" height="{h}" rx="12" fill="{bg}" opacity="0.5"/>'
    line_x = 50
    svg += f'<line x1="{line_x}" y1="45" x2="{line_x}" y2="{h - 20}" stroke="{accent}" stroke-width="2.5" stroke-linecap="round"/>'
    for i, pt in enumerate(points):
        y = 55 + i * 60
        svg += f'<circle cx="{line_x}" cy="{y}" r="7" fill="{accent}" opacity="0.3"/>'
        svg += f'<circle cx="{line_x}" cy="{y}" r="4" fill="{accent}"/>'
        lines = _wrap(pt, 50)
        for li, line in enumerate(lines):
            svg += f'<text x="{line_x + 18}" y="{y + li * 16 - 4}" fill="{text_color}" font-size="11" font-family="system-ui">{line}</text>'
    svg += f'<text x="{w//2}" y="28" text-anchor="middle" font-size="11" fill="{accent}" font-family="system-ui" font-weight="600" letter-spacing="1">{_esc(plan.get("title", ""))}</text>'
    svg += "</svg>"
    return svg


def render_comparison(plan, colors):
    points = plan.get("data_points", [])
    accent = colors.get("accent", "#2563EB")
    text_color = colors.get("text", "#1A1A1A")
    bg = colors.get("secondary", "#F5F5F5")
    colors.get("heading", "#000")

    pairs = []
    for i in range(0, len(points) - 1, 2):
        pairs.append((points[i], points[i + 1]))
    if len(points) % 2 == 1 and pairs:
        pairs.append((points[-1], ""))

    n = len(pairs)
    if n == 0:
        return ""
    w = 720
    h = 50 + n * 45
    col_w = (w - 80) // 2

    svg = f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">'
    svg += f'<rect width="{w}" height="{h}" rx="12" fill="{bg}" opacity="0.5"/>'

    hdr_y = 38
    svg += f'<rect x="15" y="{hdr_y - 16}" width="{col_w}" height="26" rx="4" fill="{accent}" opacity="0.15"/>'
    svg += f'<text x="20" y="{hdr_y}" fill="{accent}" font-size="10" font-family="system-ui" font-weight="700" letter-spacing="1">FEATURE A</text>'
    svg += f'<rect x="{col_w + 25}" y="{hdr_y - 16}" width="{col_w}" height="26" rx="4" fill="{accent}" opacity="0.08"/>'
    svg += f'<text x="{col_w + 30}" y="{hdr_y}" fill="{accent}" font-size="10" font-family="system-ui" font-weight="700" letter-spacing="1">FEATURE B</text>'
    for i, (a, b) in enumerate(pairs):
        y = 50 + i * 45
        row_bg = "transparent" if i % 2 == 0 else "rgba(0,0,0,0.03)"
        svg += f'<rect x="15" y="{y}" width="{col_w}" height="34" rx="4" fill="{row_bg}"/>'
        svg += f'<text x="20" y="{y + 22}" fill="{text_color}" font-size="10" font-family="system-ui">{_esc(a)}</text>'
        svg += f'<rect x="{col_w + 25}" y="{y}" width="{col_w}" height="34" rx="4" fill="{row_bg}"/>'
        if b:
            svg += f'<text x="{col_w + 30}" y="{y + 22}" fill="{text_color}" font-size="10" font-family="system-ui">{_esc(b)}</text>'
    svg += f'<text x="{w//2}" y="22" text-anchor="middle" font-size="11" fill="{accent}" font-family="system-ui" font-weight="600" letter-spacing="1">{_esc(plan.get("title", ""))}</text>'
    svg += "</svg>"
    return svg


def render_list(plan, colors):
    points = plan.get("data_points", [])
    accent = colors.get("accent", "#2563EB")
    text_color = colors.get("text", "#1A1A1A")
    bg = colors.get("secondary", "#F5F5F5")

    n = len(points)
    if n == 0:
        return ""
    w = 720
    h = 40 + n * 40

    svg = f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">'
    svg += f'<rect width="{w}" height="{h}" rx="12" fill="{bg}" opacity="0.5"/>'
    for i, pt in enumerate(points):
        y = 32 + i * 40
        num = i + 1
        svg += f'<circle cx="28" cy="{y + 4}" r="10" fill="{accent}" opacity="0.15"/>'
        svg += f'<text x="28" y="{y + 8}" text-anchor="middle" fill="{accent}" font-size="9" font-family="system-ui" font-weight="700">{num}</text>'
        lines = _wrap(pt, 60)
        for li, line in enumerate(lines):
            svg += f'<text x="48" y="{y + li * 15}" fill="{text_color}" font-size="10" font-family="system-ui">{line}</text>'
    svg += f'<text x="{w//2}" y="20" text-anchor="middle" font-size="11" fill="{accent}" font-family="system-ui" font-weight="600" letter-spacing="1">{_esc(plan.get("title", ""))}</text>'
    svg += "</svg>"
    return svg


def render_hierarchy(plan, colors):
    points = plan.get("data_points", [])
    accent = colors.get("accent", "#2563EB")
    colors.get("text", "#1A1A1A")
    bg = colors.get("secondary", "#F5F5F5")

    n = min(len(points), 5)
    if n == 0:
        return ""
    w = 720
    h = 60 + n * 70

    svg = f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">'
    svg += f'<rect width="{w}" height="{h}" rx="12" fill="{bg}" opacity="0.5"/>'
    for i in range(n):
        y = 40 + i * 70
        box_w = max(120, w - i * 100)
        x = (w - box_w) // 2
        alpha = max(0.25, 1.0 - i * 0.18)
        n - i
        svg += f'<rect x="{x}" y="{y}" width="{box_w}" height="42" rx="8" fill="{accent}" opacity="{alpha}"/>'
        lines = _wrap(points[i], int(box_w / 7))
        for li, line in enumerate(lines):
            svg += f'<text x="{x + box_w // 2}" y="{y + 42 // 2 + (li - len(lines)//2) * 14}" text-anchor="middle" fill="#fff" font-size="11" font-family="system-ui" font-weight="500">{line}</text>'
        if i < n - 1:
            cx = w // 2
            svg += f'<line x1="{cx}" y1="{y + 42}" x2="{cx}" y2="{y + 56}" stroke="{accent}" stroke-width="1.5" opacity="0.5"/>'
            svg += f'<polygon points="{cx-4},{y+54} {cx+4},{y+54} {cx},{y+60}" fill="{accent}" opacity="0.5"/>'
    svg += f'<text x="{w//2}" y="26" text-anchor="middle" font-size="11" fill="{accent}" font-family="system-ui" font-weight="600" letter-spacing="1">{_esc(plan.get("title", ""))}</text>'
    svg += "</svg>"
    return svg


def render_cycle(plan, colors):
    points = plan.get("data_points", [])
    accent = colors.get("accent", "#2563EB")
    text_color = colors.get("text", "#1A1A1A")
    bg = colors.get("secondary", "#F5F5F5")

    n = len(points)
    if n == 0:
        return ""
    w = 720
    h = 250

    center_x = w // 2
    center_y = h // 2
    radius = 140

    svg = f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">'
    svg += f'<rect width="{w}" height="{h}" rx="12" fill="{bg}" opacity="0.5"/>'
    for i, item in enumerate(points):
        angle = (2 * 3.14159 * i) / n
        x = center_x + radius * 1.4 * (3.14159 / 2 - angle) if angle <= 3.14159 else center_x + radius * 1.4 * (angle - 3.14159)
        y = center_y - radius * 1.4 * abs(3.14159 / 2 - angle)
        center_x + radius * 0.9 * (3.14159 / 2 - angle) if angle <= 3.14159 else center_x + radius * 0.9 * (angle - 3.14159)
        center_y - radius * 0.9 * abs(3.14159 / 2 - angle)

        if angle < 3.14159:
            x = center_x + radius * 1.4 * (angle - 3.14159)
        else:
            x = center_x + radius * 1.4 * (3.14159 - angle)
        y = center_y + abs(x - center_x) * 0.8
        line_x = x
        line_y = y

        text_anchor = 'middle'
        if abs(1 - abs(angle / 3.14159)) < 0.2:
            dx = -80 if (angle < 3.14159 and 1 - angle / 3.14159 > 0.8) or (angle > 3.14159 and (angle - 3.14159) < 0.8) else 80
        else:
            dx = 0

        svg += f'<line x1="{center_x}" y1="{center_y}" x2="{line_x + dx}" y2="{line_y}" stroke="{accent}" stroke-width="2" stroke-dasharray="8,4"/>'
        svg += f'<circle cx="{line_x + dx}" cy="{line_y}" r="6" fill="{accent}" opacity="0.8"/>'
        lines = _wrap(item, 15)
        for li, line in enumerate(lines):
            dy = li * 16 - len(lines) * 8
            svg += f'<text x="{line_x + dx}" y="{line_y + dy}" text-anchor="{text_anchor}" fill="{text_color}" font-size="11" font-family="system-ui">{line}</text>'

    svg += f'<circle cx="{center_x}" cy="{center_y}" r="16" fill="{accent}" opacity="0.3"/>'
    svg += f'<text x="{center_x}" y="{center_y}" text-anchor="middle" fill="{accent}" font-size="12" font-family="system-ui" font-weight="700">START</text>'

    lines = _wrap(plan.get("title", ""), 30)
    for li, line in enumerate(lines):
        svg += f'<text x="{w // 2}" y="30 + {li * 18}" text-anchor="middle" font-size="11" fill="{accent}" font-family="system-ui" font-weight="600">{line}</text>'

    svg += "</svg>"
    return svg


def render_pyramid(plan, colors):
    points = plan.get("data_points", [])
    accent = colors.get("accent", "#2563EB")
    text_color = colors.get("text", "#1A1A1A")
    bg = colors.get("secondary", "#F5F5F5")

    n = len(points)
    if n == 0:
        return ""

    max_chars = max(len(p) for p in points) if points else 20
    char_width = 8
    cell_w = max(120, max_chars * char_width)

    max_level_items = n
    level_spacing = 90
    cell_w * max_level_items

    w = 720
    h = 60 + max_level_items * level_spacing

    svg = f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">'
    svg += f'<rect width="{w}" height="{h}" rx="12" fill="{bg}" opacity="0.5"/>'

    for y in range(max_level_items):
        indent = (max_level_items - 1 - y) * cell_w // 2
        shape_y = 60 + y * level_spacing
        line_y = shape_y + 20

        lines = _wrap(points[y] if y < n else "", cell_w // 3)
        for li, line in enumerate(lines):
            svg += f'<text x="{indent}" y="{shape_y + li * 16}" text-anchor="middle" fill="{text_color}" font-size="11" font-family="system-ui">{line}</text>'

        if y < max_level_items - 1:
            for lvl in range(y + 1, max_level_items):
                next_indent = (max_level_items - 1 - lvl) * cell_w // 2
                svg += f'<line x1="{indent + cell_w // 2}" y1="{line_y + 4}" x2="{next_indent + cell_w // 2}" y2="{lvl * level_spacing - 8}" stroke="{accent}" stroke-width="1.5" opacity="0.7"/>'
                svg += f'<polygon points="{next_indent + cell_w // 2 - 4},{lvl * level_spacing - 8} {next_indent + cell_w // 2 + 4},{lvl * level_spacing - 8} {next_indent + cell_w // 2},{lvl * level_spacing - 2}" fill="{accent}" opacity="0.7"/>'

    if n > 0:
        lines = _wrap(points[0], cell_w // 3)
        for li, line in enumerate(lines):
            svg += f'<text x="{w // 2}" y="{h - 20}" text-anchor="middle" fill="{accent}" font-size="12" font-family="system-ui" font-weight="700">{line}</text>'

    lines = _wrap(plan.get("title", ""), 30)
    for li, line in enumerate(lines):
        svg += f'<text x="{w // 2}" y="22 + {li * 18}" text-anchor="middle" font-size="11" fill="{accent}" font-family="system-ui" font-weight="600">{line}</text>'

    svg += "</svg>"
    return svg


def render_stats(plan, colors):
    points = plan.get("data_points", [])
    accent = colors.get("accent", "#2563EB")
    text_color = colors.get("text", "#1A1A1A")
    bg = colors.get("secondary", "#F5F5F5")

    n = len(points)
    if n == 0:
        return ""

    w = 720
    h = 300

    cell_h = 60
    cell_w = 180
    bar_max = 180

    svg = f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">'
    svg += f'<rect width="{w}" height="{h}" rx="12" fill="{bg}" opacity="0.5"/>'

    for i, item in enumerate(points):
        y = 50 + i * cell_h
        lines = _wrap(item, 20)
        for li, line in enumerate(lines):
            svg += f'<text x="20" y="{y + li * 16}" fill="{text_color}" font-size="11" font-family="system-ui">{line}</text>'

        value = 60 + (i * 30) % bar_max
        bar_width = (value / bar_max) * cell_w
        bar_x = 240
        bar_y = y - 8

        svg += f'<rect x="{bar_x}" y="{bar_y}" width="{bar_width}" height="16" rx="4" fill="{accent}" opacity="0.8"/>'
        svg += f'<text x="{bar_x + bar_width + 8}" y="{bar_y + 12}" fill="{text_color}" font-size="11" font-family="system-ui">{value}</text>'

    lines = _wrap(plan.get("title", ""), 30)
    for li, line in enumerate(lines):
        svg += f'<text x="{w // 2}" y="20 + {li * 18}" text-anchor="middle" font-size="11" fill="{accent}" font-family="system-ui" font-weight="600">{line}</text>'

    legend_x = 500
    legend_y = h - 30

    lines = _wrap("Value Range: 0 - 250", 20)
    for li, line in enumerate(lines):
        svg += f'<text x="{legend_x}" y="{legend_y + li * 16}" fill="{text_color}" font-size="10" font-family="system-ui">{line}</text>'

    svg += "</svg>"
    return svg


def render_roadmap(plan, colors):
    points = plan.get("data_points", [])
    accent = colors.get("accent", "#2563EB")
    text_color = colors.get("text", "#1A1A1A")
    bg = colors.get("secondary", "#F5F5F5")

    n = len(points)
    if n == 0:
        return ""

    w = 720
    h = 300

    phase_h = 60
    phase_width = 180

    svg = f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">'
    svg += f'<rect width="{w}" height="{h}" rx="12" fill="{bg}" opacity="0.5"/>'

    for i in range(n):
        y = 60 + i * (h - 120) // (n - 1) if n > 1 else 90
        phase_x = 200 + i * phase_width

        svg += f'<rect x="{phase_x}" y="{y}" width="{phase_width}" height="{phase_h}" rx="8" fill="{accent}" opacity="0.15"/>'
        svg += f'<rect x="{phase_x}" y="{y}" width="{phase_width}" height="{phase_h}" rx="8" fill="none" stroke="{accent}" stroke-width="2"/>'

        lines = _wrap(points[i], 25)
        for li, line in enumerate(lines):
            svg += f'<text x="{phase_x + phase_width // 2}" y="{y + 20 + li * 16}" text-anchor="middle" fill="{text_color}" font-size="11" font-family="system-ui">{line}</text>'

    if n > 0:
        milestone_x = 350
        svg += f'<line x1="{milestone_x}" y1="50" x2="{milestone_x}" y2="{h - 50}" stroke="{accent}" stroke-width="3" stroke-dasharray="8,4"/>'
        svg += f'<circle cx="{milestone_x}" cy="50" r="6" fill="{accent}" opacity="0.8"/>'
        svg += f'<text x="{milestone_x}" y="150" text-anchor="middle" fill="{accent}" font-size="14" font-family="system-ui" font-weight="700">PHASE 1</text>'

    lines = _wrap(plan.get("title", ""), 30)
    for li, line in enumerate(lines):
        svg += f'<text x="{w // 2}" y="20 + {li * 18}" text-anchor="middle" font-size="11" fill="{accent}" font-family="system-ui" font-weight="600">{line}</text>'

    svg += "</svg>"
    return svg


def render_funnel(plan, colors):
    points = plan.get("data_points", [])
    accent = colors.get("accent", "#2563EB")
    text_color = colors.get("text", "#1A1A1A")
    bg = colors.get("secondary", "#F5F5F5")

    n = len(points)
    if n == 0:
        return ""

    w = 720
    h = 400

    funnel_width_start = 500
    funnel_width_end = 80
    funnel_h = 380

    svg = f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">'
    svg += f'<rect width="{w}" height="{h}" rx="12" fill="{bg}" opacity="0.5"/>'

    x_left_start = (w - funnel_width_start) // 2
    x_left_start + funnel_width_start

    funnel_points = []
    for i in range(n):
        ratio = i / (n - 1)
        width = funnel_width_start - ratio * (funnel_width_start - funnel_width_end)
        x1 = (w - width) // 2
        x2 = x1 + width
        y = h - 40 - i * (funnel_h / n)
        funnel_points.append((x1, x2, y))

    for i, (x1, x2, y) in enumerate(funnel_points):
        svg += f'<rect x="{x1}" y="{y}" width="{x2 - x1}" height="40" rx="6" fill="{accent}" opacity="0.15"/>'
        svg += f'<rect x="{x1}" y="{y}" width="{x2 - x1}" height="40" rx="6" fill="none" stroke="{accent}" stroke-width="2"/>'

        lines = _wrap(points[i], 25)
        for li, line in enumerate(lines):
            text_x = (x1 + x2) // 2
            svg += f'<text x="{text_x}" y="{y + 20 + li * 16}" text-anchor="middle" fill="{text_color}" font-size="11" font-family="system-ui">{line}</text>'

    lines = _wrap(plan.get("title", ""), 30)
    for li, line in enumerate(lines):
        svg += f'<text x="{w // 2}" y="30 + {li * 18}" text-anchor="middle" font-size="11" fill="{accent}" font-family="system-ui" font-weight="600">{line}</text>'

    pct_loss = (len(points) - 1) / len(points) * 100 if len(points) > 1 else 0
    conversion_text = f"Conversion: {pct_loss:.1f}% loss"
    lines = _wrap(conversion_text, 20)
    for li, line in enumerate(lines):
        svg += f'<text x="{w // 2}" y="h - 20 + {li * 16}" text-anchor="middle" fill="{accent}" font-size="10" font-family="system-ui" font-style="italic">{line}</text>'

    svg += "</svg>"
    return svg


RENDERERS = {
    "process": render_process,
    "timeline": render_timeline,
    "comparison": render_comparison,
    "list": render_list,
    "hierarchy": render_hierarchy,
    "cycle": render_cycle,
    "pyramid": render_pyramid,
    "stats": render_stats,
    "roadmap": render_roadmap,
    "funnel": render_funnel,
}


def render_infographic(plan, colors):
    t = plan.get("type", "list")
    renderer = RENDERERS.get(t, render_list)
    return renderer(plan, colors)
