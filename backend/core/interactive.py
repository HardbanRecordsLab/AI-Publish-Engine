"""Interactive Web Book builder — rich, embeddable, reader-focused HTML."""
import math
from datetime import datetime

from jinja2 import Environment, FileSystemLoader

from backend.core.color_engine import detect_topic, get_color_palette
from backend.core.icon_service import get_cover_icon
from backend.themes import get_theme

TEMPLATE_DIR = "templates"
env = Environment(loader=FileSystemLoader([TEMPLATE_DIR]))

STYLE_THEME_MAP = {
    "professional": "business", "minimal": "minimal", "creative": "creative",
    "academic": "academic", "modern": "modern", "dark": "dark",
    "business": "business", "finance": "finance", "technical": "technical",
    "wellness": "wellness",
}


def _est_reading_time(text: str) -> int:
    words = len(text.split())
    return max(1, math.ceil(words / 200))


def _build_quiz_html(chapter_title: str, chapter_index: int) -> str:
    return f"""
    <div class="iq-quiz" data-chapter="{chapter_index}">
      <div class="iq-quiz-title">Test Your Knowledge: {chapter_title}</div>
      <div class="iq-quiz-q">
        <p>What was the main topic of this chapter?</p>
        <label><input type="radio" name="q{chapter_index}" value="a"> I understood the key concepts</label>
        <label><input type="radio" name="q{chapter_index}" value="b"> I need to review this chapter</label>
        <label><input type="radio" name="q{chapter_index}" value="c"> I already knew this material</label>
      </div>
      <button class="iq-btn" onclick="this.parentElement.querySelector('.iq-quiz-feedback').style.display='block'">Check</button>
      <div class="iq-quiz-feedback" style="display:none">Great job! Review your notes to reinforce the material.</div>
    </div>"""


def _build_toc(chapters: list) -> str:
    items = "".join(
        f'<li><a href="#ch-{i+1}" class="iq-toc-link" data-index="{i+1}">'
        f'<span class="iq-toc-num">{i+1}</span>{ch.get("title", f"Chapter {i+1}")}'
        f'<span class="iq-toc-read">{_est_reading_time(ch.get("introduction","") or "")} min</span></a></li>'
        for i, ch in enumerate(chapters)
    )
    return f"<ul>{items}</ul>"


def build_interactive_book(structure: dict, style: str, infographics: list,
                           introduction: str = "", author_bio: str = "",
                           references: list = None, glossary_terms: list = None,
                           back_cover_blurb: str = "", back_cover_tagline: str = "",
                           cover_svg: str = "", cover_image: str = "",
                           chapter_illustrations: list = None,
                           accent_color: str = "", bg_color: str = "",
                           heading_font: str = "", body_font: str = "") -> str:
    topic = detect_topic(structure)
    topic_palette = get_color_palette(topic)
    theme_id = STYLE_THEME_MAP.get(style, style)
    theme = get_theme(theme_id)
    colors = dict(theme["colors"])
    fonts = dict(theme["fonts"])

    if topic != "general":
        colors["accent"] = topic_palette["colors"]["accent"]
        colors["secondary"] = topic_palette["colors"]["secondary"]
        colors["highlight"] = topic_palette["colors"]["highlight"]

    if accent_color and accent_color.startswith("#"):
        colors["accent"] = accent_color
    if bg_color and bg_color.startswith("#"):
        colors["background"] = bg_color
    if heading_font:
        fonts["heading"] = heading_font
    if body_font:
        fonts["body"] = body_font

    title = structure.get("title", "Interactive Book")
    subtitle = structure.get("subtitle", "")
    author = structure.get("author", "AI Design Engine")
    summary = structure.get("summary", "")
    chapters = structure.get("chapters", [])
    conclusion = structure.get("conclusion", {})

    if references is None:
        references = []
    if glossary_terms is None:
        glossary_terms = []
    if chapter_illustrations is None:
        chapter_illustrations = []

    ch_ills = {}
    for ill in (chapter_illustrations or []):
        ch_ills[ill.get("chapter_index")] = ill.get("image_uri") or ill.get("svg", "")

    cover_gradient = theme.get("cover_gradient", f"linear-gradient(135deg, {colors['accent']} 0%, {colors.get('secondary', '#333')} 100%)")
    cover_icon_svg = get_cover_icon(topic, colors["accent"], 60)

    # Build full text for reading time
    full_text = summary + " " + introduction + " " + (conclusion.get("content", "") or "")
    for ch in chapters:
        full_text += (ch.get("introduction", "") or "") + " " + (ch.get("key_takeaway", "") or "")
        for sec in ch.get("sections", []):
            full_text += (sec.get("content", "") or "")
    total_read_time = _est_reading_time(full_text)

    # Chapter HTML
    chapters_html = ""
    for ci, ch in enumerate(chapters):
        sections_html = ""
        for si, sec in enumerate(ch.get("sections", [])):
            sections_html += f"""
            <div class="iq-section">
              <h3 class="iq-sec-heading">{sec.get("heading", "")}</h3>
              <div class="iq-sec-content"><p>{sec.get("content", "")}</p></div>
            </div>"""

        # Infographics
        for ig in infographics:
            if ig.get("chapter_index") == ci:
                from backend.core.infographic_engine import render_infographic
                try:
                    svg = render_infographic(ig, colors)
                    sections_html += f'<div class="iq-infographic animated-infographic">{svg}</div>'
                except Exception:
                    pass

        # Structural elements
        if ch.get("chapter_summary"):
            s = ch["chapter_summary"]
            pts = "".join(f"<li>{p}</li>" for p in s.get("points", []))
            sections_html += f'<div class="iq-summary"><strong>{s.get("title","Summary")}</strong><ul>{pts}</ul></div>'

        if ch.get("faq"):
            faq_html = ""
            for fi, faq_item in enumerate(ch["faq"]):
                faq_html += f"""
                <div class="iq-faq-item">
                  <button class="iq-faq-q" onclick="this.nextElementSibling.classList.toggle('open');this.classList.toggle('open')">
                    {faq_item.get("question","")}
                    <span class="iq-faq-arrow">+</span>
                  </button>
                  <div class="iq-faq-a">{faq_item.get("answer","")}</div>
                </div>"""
            sections_html += f'<div class="iq-faq"><h3>Frequently Asked Questions</h3>{faq_html}</div>'

        if ch.get("checklist"):
            c = ch["checklist"]
            items = "".join(
                f'<label class="iq-check-item"><input type="checkbox" onchange="saveChecklist({ci},this)"> {it.get("text","")}</label>'
                for it in c.get("items", [])
            )
            sections_html += f'<div class="iq-checklist"><h3>{c.get("title","Checklist")}</h3>{items}</div>'

        # Quiz
        sections_html += _build_quiz_html(ch.get("title", f"Chapter {ci+1}"), ci)

        ch_ill = ch_ills.get(ci, "")
        ill_html = f'<div class="iq-chapter-ill">{ch_ill}</div>' if ch_ill else ""

        chapters_html += f"""
        <section id="ch-{ci+1}" class="iq-chapter" data-chapter="{ci+1}">
          <div class="iq-chapter-header">
            <span class="iq-chapter-num">Chapter {ci+1}</span>
            <h2 class="iq-chapter-title">{ch.get("title", f"Chapter {ci+1}")}</h2>
            {f'<p class="iq-chapter-intro">{ch["introduction"]}</p>' if ch.get("introduction") else ""}
            {f'<div class="iq-takeaway">Key Takeaway: {ch["key_takeaway"]}</div>' if ch.get("key_takeaway") else ""}
          </div>
          {ill_html}
          {sections_html}
        </section>"""

    # Conclusion
    conclusion_html = ""
    if conclusion:
        conclusion_html = f"""
        <section id="conclusion" class="iq-chapter">
          <div class="iq-chapter-header">
            <h2 class="iq-chapter-title">{conclusion.get("title","Conclusion")}</h2>
          </div>
          <p>{conclusion.get("content","")}</p>
        </section>"""

    # References
    refs_html = ""
    if references:
        items = "".join(
            f'<li>{"<a href=\"" + r["url"] + "\" target=\"_blank\">" if r.get("url") else ""}{r.get("text") or r.get("title","")}{"</a>" if r.get("url") else ""}</li>'
            for r in references
        )
        refs_html = f'<section id="references" class="iq-chapter"><h2>References</h2><ul>{items}</ul></section>'

    # Glossary
    gloss_html = ""
    if glossary_terms:
        items = "".join(
            f'<div class="iq-glossary-term"><strong>{t.get("term","")}</strong>: {t.get("definition","")}</div>'
            for t in glossary_terms
        )
        gloss_html = f'<section id="glossary" class="iq-chapter"><h2>Glossary</h2>{items}</section>'

    author_html = ""
    if author_bio:
        author_html = f'<section id="author" class="iq-chapter"><h2>About the Author</h2><p>{author_bio}</p></section>'

    back_html = ""
    if back_cover_blurb:
        back_html = f"""
        <section id="back-cover" class="iq-chapter iq-back-cover">
          <p class="iq-back-blurb">{back_cover_blurb}</p>
          {f'<p class="iq-back-tagline">{back_cover_tagline}</p>' if back_cover_tagline else ""}
        </section>"""

    toc_html = _build_toc(chapters)

    color_vars = "".join(f"  --color-{k}: {v};\n" for k, v in colors.items() if not k.startswith("_"))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title} — {author}</title>
<meta name="description" content="{summary[:200]}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{summary[:200]}">
<meta name="twitter:card" content="summary_large_image">
<style>
:root {{
{color_vars}
  --font-heading: {fonts['heading']};
  --font-body: {fonts['body']};
  --cover-gradient: {cover_gradient};
}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:var(--font-body);color:var(--color-text);background:var(--color-background);line-height:1.8;font-size:16px;transition:background .3s,color .3s}}
body.iq-dark{{--color-background:#0B0F1A;--color-surface:#111827;--color-text:#E2E8F0;--color-heading:#F1F5F9;--color-border:#1E293B;--color-muted:#475569;--color-highlight:#1A1F2E}}
.iq-topbar{{position:fixed;top:0;left:0;right:0;z-index:1000;background:var(--color-background);border-bottom:1px solid var(--color-border);display:flex;align-items:center;padding:0 16px;height:48px;gap:8px;backdrop-filter:blur(8px)}}
.iq-topbar-title{{font-size:14px;font-weight:600;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--color-text)}}
.iq-topbar-btn{{background:none;border:1px solid var(--color-border);border-radius:6px;padding:4px 10px;cursor:pointer;font-size:12px;color:var(--color-text);transition:all .15s}}
.iq-topbar-btn:hover{{background:var(--color-highlight)}}
.iq-progress{{position:fixed;top:48px;left:0;right:0;height:3px;z-index:999;background:var(--color-border)}}
.iq-progress-fill{{height:100%;background:var(--color-accent);width:0;transition:width .3s ease}}
.iq-layout{{display:flex;margin-top:51px;min-height:calc(100vh - 51px)}}
.iq-sidebar{{width:280px;flex-shrink:0;border-right:1px solid var(--color-border);padding:16px;overflow-y:auto;position:sticky;top:51px;height:calc(100vh - 51px);display:none;background:var(--color-background)}}
.iq-sidebar.open{{display:block}}
.iq-sidebar h3{{font-family:var(--font-heading);font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--color-muted);margin-bottom:12px}}
.iq-sidebar ul{{list-style:none}}
.iq-sidebar li{{margin-bottom:2px}}
.iq-toc-link{{display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:6px;text-decoration:none;color:var(--color-text);font-size:13px;transition:all .15s}}
.iq-toc-link:hover{{background:var(--color-highlight)}}
.iq-toc-link.active{{background:var(--color-accent);color:#fff;font-weight:600}}
.iq-toc-num{{width:24px;height:24px;border-radius:50%;background:var(--color-border);display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0}}
.iq-toc-link.active .iq-toc-num{{background:rgba(255,255,255,.25);color:#fff}}
.iq-toc-read{{margin-left:auto;font-size:11px;color:var(--color-muted);flex-shrink:0}}
.iq-content{{flex:1;max-width:720px;margin:0 auto;padding:40px 24px 80px}}
.iq-cover{{text-align:center;padding:60px 20px 40px;margin-bottom:40px;border-radius:16px;background:var(--cover-gradient);color:#fff}}
.iq-cover-icon{{margin-bottom:16px;display:inline-block}}
.iq-cover h1{{font-family:var(--font-heading);font-size:2.8em;font-weight:800;letter-spacing:-1px;margin-bottom:8px;line-height:1.2}}
.iq-cover .subtitle{{font-size:1.2em;opacity:.85;margin-bottom:16px}}
.iq-cover .meta{{font-size:.9em;opacity:.7;display:flex;justify-content:center;gap:16px}}
.iq-cover .read-time{{margin-top:20px;font-size:.85em;opacity:.7}}
.iq-section{{margin-bottom:28px;padding:20px;border-radius:10px;background:var(--color-surface);border:1px solid var(--color-border);transition:all .2s}}
.iq-section:hover{{border-color:var(--color-accent);box-shadow:0 2px 12px rgba(0,0,0,.05)}}
.iq-sec-heading{{font-family:var(--font-heading);font-size:1.1em;color:var(--color-heading);margin-bottom:8px;font-weight:700}}
.iq-sec-content p{{margin-bottom:10px;text-align:justify}}
.iq-chapter{{margin-bottom:48px;scroll-margin-top:60px}}
.iq-chapter-header{{margin-bottom:24px;padding-bottom:16px;border-bottom:2px solid var(--color-accent)}}
.iq-chapter-num{{font-size:11px;text-transform:uppercase;letter-spacing:2px;color:var(--color-accent);font-weight:600}}
.iq-chapter-title{{font-family:var(--font-heading);font-size:1.6em;color:var(--color-heading);margin:4px 0 8px;font-weight:700}}
.iq-chapter-intro{{font-style:italic;color:var(--color-muted);font-size:1.05em}}
.iq-takeaway{{background:var(--color-highlight);border-left:3px solid var(--color-accent);padding:12px 16px;border-radius:0 8px 8px 0;margin-top:12px;font-size:.95em}}
.iq-chapter-ill{{margin:16px 0;text-align:center;border-radius:10px;overflow:hidden;border:1px solid var(--color-border)}}
.iq-infographic{{margin:20px 0;text-align:center;border-radius:10px;padding:16px;background:var(--color-surface);border:1px solid var(--color-border)}}
.animated-infographic svg{{max-width:100%;height:auto;animation:fadeIn .5s ease}}
@keyframes fadeIn{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:translateY(0)}}}}
.iq-summary{{background:var(--color-highlight);border-radius:8px;padding:16px 20px;margin:16px 0}}
.iq-summary ul{{margin:8px 0 0 16px}}
.iq-faq{{margin:16px 0}}
.iq-faq-item{{border:1px solid var(--color-border);border-radius:8px;margin-bottom:6px;overflow:hidden}}
.iq-faq-q{{width:100%;padding:12px 16px;text-align:left;background:none;border:none;cursor:pointer;font-size:14px;font-weight:500;color:var(--color-text);display:flex;justify-content:space-between;align-items:center}}
.iq-faq-q:hover{{background:var(--color-highlight)}}
.iq-faq-arrow{{font-size:20px;transition:transform .2s;font-weight:300}}
.iq-faq-q.open .iq-faq-arrow{{transform:rotate(45deg)}}
.iq-faq-a{{padding:0 16px 12px;display:none;font-size:.95em;color:var(--color-muted)}}
.iq-faq-a.open{{display:block}}
.iq-checklist{{background:var(--color-highlight);border-radius:8px;padding:16px;margin:16px 0}}
.iq-check-item{{display:flex;align-items:flex-start;gap:8px;padding:6px 0;cursor:pointer;font-size:.95em}}
.iq-check-item input[type=checkbox]{{margin-top:4px}}
.iq-quiz{{background:var(--color-surface);border:2px solid var(--color-accent);border-radius:10px;padding:20px;margin:20px 0}}
.iq-quiz-title{{font-weight:700;font-size:1.05em;margin-bottom:12px}}
.iq-quiz-q label{{display:block;padding:8px 12px;margin:4px 0;border-radius:6px;border:1px solid var(--color-border);cursor:pointer;font-size:.95em;transition:all .15s}}
.iq-quiz-q label:hover{{border-color:var(--color-accent);background:var(--color-highlight)}}
.iq-btn{{background:var(--color-accent);color:#fff;border:none;padding:8px 24px;border-radius:6px;cursor:pointer;font-size:14px;margin-top:8px;transition:opacity .15s}}
.iq-btn:hover{{opacity:.9}}
.iq-quiz-feedback{{margin-top:12px;padding:12px;background:var(--color-highlight);border-radius:6px;font-size:.95em}}
.iq-glossary-term{{padding:8px 0;border-bottom:1px solid var(--color-border);font-size:.95em}}
.iq-back-cover{{text-align:center;padding:40px}}
.iq-back-blurb{{font-style:italic;font-size:1.1em;max-width:500px;margin:0 auto 12px}}
.iq-back-tagline{{font-size:1.3em;color:var(--color-accent);font-weight:600}}
.iq-footer{{text-align:center;padding:24px;color:var(--color-muted);font-size:.85em;border-top:1px solid var(--color-border);margin-top:40px}}
@media(max-width:768px){{
.iq-sidebar{{position:fixed;left:-280px;top:51px;height:calc(100vh - 51px);z-index:998;transition:left .3s ease;display:block;box-shadow:4px 0 20px rgba(0,0,0,.15)}}
.iq-sidebar.open{{left:0}}
.iq-content{{padding:24px 16px 60px}}
.iq-cover h1{{font-size:1.8em}}
}}
.iq-highlight{{background:rgba(255,255,0,.3);cursor:pointer;border-radius:2px}}
.iq-toast{{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:var(--color-text);color:var(--color-background);padding:10px 20px;border-radius:8px;font-size:13px;z-index:9999;opacity:0;transition:opacity .3s;pointer-events:none}}
.iq-toast.show{{opacity:1}}
</style>
</head>
<body>
<div class="iq-topbar">
  <button class="iq-topbar-btn" onclick="document.querySelector('.iq-sidebar').classList.toggle('open')" title="Table of Contents">☰</button>
  <span class="iq-topbar-title">{title}</span>
  <button class="iq-topbar-btn" onclick="toggleTheme()" id="themeToggle">🌙</button>
  <button class="iq-topbar-btn" onclick="changeFontSize(-1)">A−</button>
  <button class="iq-topbar-btn" onclick="changeFontSize(1)">A+</button>
  <button class="iq-topbar-btn" onclick="shareBook()" title="Share">🔗</button>
</div>
<div class="iq-progress"><div class="iq-progress-fill" id="progressFill"></div></div>
<div class="iq-layout">
<aside class="iq-sidebar" id="tocSidebar">
  <h3>Table of Contents</h3>
  {toc_html}
  <div style="margin-top:12px;border-top:1px solid var(--color-border);padding-top:12px">
    <a href="#conclusion" class="iq-toc-link" onclick="closeToc()"><span class="iq-toc-num">✓</span>Conclusion</a>
    {'<a href="#references" class="iq-toc-link" onclick="closeToc()"><span class="iq-toc-num">R</span>References</a>' if references else ''}
    {'<a href="#glossary" class="iq-toc-link" onclick="closeToc()"><span class="iq-toc-num">G</span>Glossary</a>' if glossary_terms else ''}
    {'<a href="#author" class="iq-toc-link" onclick="closeToc()"><span class="iq-toc-num">A</span>About</a>' if author_bio else ''}
  </div>
</aside>
<main class="iq-content" id="iqContent">
  <div class="iq-cover">
    <div class="iq-cover-icon">{cover_icon_svg}</div>
    <h1>{title}</h1>
    {f'<p class="subtitle">{subtitle}</p>' if subtitle else ''}
    <div class="meta"><span>{author}</span><span>{datetime.now().strftime("%B %d, %Y")}</span></div>
    <div class="read-time">~ {total_read_time} min read</div>
  </div>

  {f'<section class="iq-chapter"><h2>Introduction</h2><p>{introduction}</p></section>' if introduction else ''}

  {chapters_html}

  {conclusion_html}
  {refs_html}
  {gloss_html}
  {author_html}
  {back_html}

  <div class="iq-footer">
    <p>Generated by AI Design Engine • {datetime.now().strftime("%Y")}</p>
  </div>
</main>
</div>
<div class="iq-toast" id="iqToast"></div>
<script>
// Reading progress
document.addEventListener('scroll', function() {{
  var scrollTop = window.scrollY;
  var docHeight = document.documentElement.scrollHeight - window.innerHeight;
  var progress = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
  document.getElementById('progressFill').style.width = progress + '%';
  updateActiveToc();
}});

function updateActiveToc() {{
  var links = document.querySelectorAll('.iq-toc-link');
  var sections = document.querySelectorAll('.iq-chapter');
  var current = 0;
  sections.forEach(function(s, i) {{
    var rect = s.getBoundingClientRect();
    if (rect.top <= 200) current = i + 1;
  }});
  links.forEach(function(l) {{
    l.classList.toggle('active', parseInt(l.dataset.index) === current);
  }});
}}

function closeToc() {{
  document.querySelector('.iq-sidebar').classList.remove('open');
}}

// Theme toggle
var darkMode = localStorage.getItem('iqDark') === 'true';
if (darkMode) document.body.classList.add('iq-dark');
document.getElementById('themeToggle').textContent = darkMode ? '☀️' : '🌙';
function toggleTheme() {{
  darkMode = !darkMode;
  document.body.classList.toggle('iq-dark', darkMode);
  localStorage.setItem('iqDark', darkMode);
  document.getElementById('themeToggle').textContent = darkMode ? '☀️' : '🌙';
}}

// Font size
var fontSize = parseInt(localStorage.getItem('iqFontSize') || '16');
document.body.style.fontSize = fontSize + 'px';
function changeFontSize(delta) {{
  fontSize = Math.max(12, Math.min(28, fontSize + delta));
  document.body.style.fontSize = fontSize + 'px';
  localStorage.setItem('iqFontSize', fontSize);
}}

// Share
function shareBook() {{
  var url = window.location.href;
  if (navigator.share) {{
    navigator.share({{title: '{title}', url: url}});
  }} else {{
    navigator.clipboard.writeText(url).then(function() {{
      showToast('Link copied to clipboard!');
    }});
  }}
}}

function showToast(msg) {{
  var t = document.getElementById('iqToast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(function() {{ t.classList.remove('show'); }}, 2500);
}}

// Checklist persistence
function saveChecklist(chapter, el) {{
  var data = JSON.parse(localStorage.getItem('iqChecklist') || '{{}}');
  if (!data[chapter]) data[chapter] = [];
  var idx = Array.from(el.parentElement.parentElement.querySelectorAll('input[type=checkbox]')).indexOf(el);
  if (el.checked) {{ if (!data[chapter].includes(idx)) data[chapter].push(idx); }}
  else {{ data[chapter] = data[chapter].filter(function(i) {{ return i !== idx; }}); }}
  localStorage.setItem('iqChecklist', JSON.stringify(data));
}}

// Restore checklists
document.addEventListener('DOMContentLoaded', function() {{
  var data = JSON.parse(localStorage.getItem('iqChecklist') || '{{}}');
  Object.keys(data).forEach(function(ch) {{
    data[ch].forEach(function(idx) {{
      var boxes = document.querySelectorAll('.iq-check-item input[type=checkbox]');
      if (boxes[idx]) boxes[idx].checked = true;
    }});
  }});
  // Highlight text selection
  document.addEventListener('mouseup', function() {{
    var sel = window.getSelection();
    if (sel && sel.toString().length > 5) {{
      var range = sel.getRangeAt(0);
      var span = document.createElement('mark');
      span.className = 'iq-highlight';
      range.surroundContents(span);
      sel.removeAllRanges();
      showToast('Text highlighted');
    }}
  }});
}});
</script>
</body>
</html>"""
