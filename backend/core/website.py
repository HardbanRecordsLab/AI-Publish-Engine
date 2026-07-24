"""Website HTML builder — landing pages, blogs, documentation with SEO.
Supports both classic CSS themes and Tailwind/daisyUI output."""
from datetime import datetime

from jinja2 import Environment, FileSystemLoader

from backend.core.color_engine import detect_topic, get_color_palette
from backend.core.icon_service import get_cover_icon
from backend.core.tokens import DAISYUI_MAP
from backend.themes import get_theme

TEMPLATE_DIR = "templates"
env = Environment(loader=FileSystemLoader([TEMPLATE_DIR]))


def _seo_meta(title, description, author, url="", image="") -> str:
    safe_desc = description.replace('"', "'")[:200]
    return f"""
    <meta name="description" content="{safe_desc}">
    <meta name="author" content="{author}">
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{safe_desc}">
    <meta property="og:type" content="website">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{title}">
    <meta name="twitter:description" content="{safe_desc}">
    """


def build_website(structure: dict, style: str, infographics: list,
                  content_type: str = "website",
                  accent_color: str = "", bg_color: str = "",
                  heading_font: str = "", body_font: str = "") -> str:
    topic = detect_topic(structure)
    topic_palette = get_color_palette(topic)
    theme = get_theme(style or "landing")
    colors = theme["colors"].copy()
    colors["cover_gradient"] = theme.get("cover_gradient", "linear-gradient(135deg, #0F172A 0%, #1E3A5F 50%, #1D4ED8 100%)")
    fonts = theme["fonts"]

    if topic != "general":
        colors["accent"] = topic_palette["colors"]["accent"]
        colors["secondary"] = topic_palette["colors"]["secondary"]

    if accent_color and accent_color.startswith("#"):
        colors["accent"] = accent_color
    if bg_color and bg_color.startswith("#"):
        colors["background"] = bg_color
    if heading_font:
        fonts["heading"] = heading_font
    if body_font:
        fonts["body"] = body_font

    title = structure.get("title", "Page")
    subtitle = structure.get("subtitle", "")
    author = structure.get("author", "AI Design Engine")
    summary = structure.get("summary", "")
    chapters = structure.get("chapters", [])

    seo = _seo_meta(title, summary or subtitle, author)
    icon_svg = get_cover_icon(topic, colors["accent"], 40)

    if content_type == "landing-page":
        return _build_landing_page(title, subtitle, author, summary, chapters,
                                   colors, fonts, seo, icon_svg, structure)
    elif content_type == "blog-post":
        return _build_blog_post(title, subtitle, author, summary, chapters,
                                colors, fonts, seo, icon_svg, structure)
    else:
        return _build_website_generic(title, subtitle, author, summary, chapters,
                                      colors, fonts, seo, icon_svg, structure)


def _build_website_generic(title, subtitle, author, summary, chapters,
                            colors, fonts, seo, icon_svg, structure) -> str:
    sections_html = ""
    for ch in chapters:
        sections_html += f"""
        <section class="section">
            <h2>{ch.get('title', '')}</h2>
            {ch.get('introduction', '') and f'<p class="lead">{ch["introduction"]}</p>' or ''}
            {''.join(f'<div class="content-block"><h3>{s.get("heading", "")}</h3><p>{s.get("content", "")}</p></div>'
                     for s in ch.get('sections', []))}
        </section>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title} — {author}</title>
{seo}
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:{fonts['body']};color:{colors['text']};background:{colors['background']};line-height:1.7}}
.container{{max-width:800px;margin:0 auto;padding:20px}}
header{{text-align:center;padding:60px 20px 40px;background:{colors['cover_gradient']};color:#fff;margin-bottom:40px}}
header h1{{font-family:{fonts['heading']};font-size:2.8em;font-weight:700;margin-bottom:10px}}
header .subtitle{{font-size:1.2em;opacity:.85;margin-bottom:20px}}
header .meta{{font-size:.85em;opacity:.7}}
.section{{margin-bottom:40px;padding-bottom:30px;border-bottom:1px solid {colors['border']}}}
.section h2{{font-family:{fonts['heading']};color:{colors['heading']};font-size:1.6em;margin-bottom:15px}}
.section .lead{{font-size:1.05em;color:{colors['muted']};font-style:italic;margin-bottom:20px}}
.content-block{{margin-bottom:20px}}
.content-block h3{{font-family:{fonts['heading']};color:{colors['accent']};font-size:1.2em;margin-bottom:8px}}
.content-block p{{margin-bottom:10px}}
footer{{text-align:center;padding:30px;color:{colors['muted']};font-size:.85em;border-top:1px solid {colors['border']}}}
@media(max-width:600px){{header{{padding:30px 15px}}header h1{{font-size:1.8em}}}}
</style>
</head>
<body>
<header>
    <h1>{title}</h1>
    {subtitle and f'<div class="subtitle">{subtitle}</div>' or ''}
    {summary and f'<p>{summary}</p>' or ''}
    <div class="meta">{author}</div>
</header>
<main class="container">
    {sections_html}
</main>
<footer><p>© {datetime.now().year} {author}. All rights reserved.</p></footer>
</body>
</html>"""


def _build_landing_page(title, subtitle, author, summary, chapters,
                         colors, fonts, seo, icon_svg, structure) -> str:
    features_html = ""
    for i, ch in enumerate(chapters[:4]):
        features_html += f"""
        <div class="feature-card">
            <div class="feature-icon">{"🚀🎯⚡💡📊🔧🎨📈"[i % 8]}</div>
            <h3>{ch.get('title', f'Feature {i+1}')}</h3>
            <p>{ch.get('introduction', ch.get('sections', [{}])[0].get('content', ''))[:120]}</p>
        </div>"""

    cta_section = structure.get("conclusion", {})
    cta_text = cta_section.get("content", "Get started today!") if cta_section else "Get started today!"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title} — {author}</title>
{seo}
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:{fonts['body']};color:{colors['text']};background:{colors['background']};line-height:1.6}}
.hero{{text-align:center;padding:100px 20px 80px;background:linear-gradient(135deg,{colors['heading']},{colors['accent']});color:#fff;position:relative;overflow:hidden}}
.hero::before{{content:'';position:absolute;top:-50%;left:-50%;width:200%;height:200%;background:repeating-linear-gradient(45deg,transparent,transparent 40px,rgba(255,255,255,.02) 40px,rgba(255,255,255,.02) 80px)}}
.hero h1{{font-family:{fonts['heading']};font-size:3.2em;font-weight:800;margin-bottom:15px;position:relative;letter-spacing:-1px}}
.hero .subtitle{{font-size:1.3em;opacity:.9;margin-bottom:30px;position:relative}}
.hero .cta-btn{{display:inline-block;padding:14px 40px;font-size:1.1em;font-weight:700;color:{colors['heading']};background:#fff;border-radius:50px;text-decoration:none;transition:transform .2s;position:relative}}
.hero .cta-btn:hover{{transform:translateY(-2px)}}
.features{{max-width:1100px;margin:0 auto;padding:80px 20px}}
.features h2{{text-align:center;font-family:{fonts['heading']};font-size:2em;color:{colors['heading']};margin-bottom:50px}}
.feature-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:30px}}
.feature-card{{background:{colors['surface']};border:1px solid {colors['border']};border-radius:12px;padding:30px;text-align:center;transition:transform .2s,box-shadow .2s}}
.feature-card:hover{{transform:translateY(-3px);box-shadow:0 8px 30px rgba(0,0,0,.1)}}
.feature-icon{{font-size:2.5em;margin-bottom:15px}}
.feature-card h3{{font-family:{fonts['heading']};font-size:1.2em;color:{colors['heading']};margin-bottom:10px}}
.feature-card p{{font-size:.95em;color:{colors['muted']};line-height:1.5}}
.cta{{text-align:center;padding:80px 20px;background:{colors['secondary']}}}
.cta h2{{font-family:{fonts['heading']};font-size:2em;color:{colors['heading']};margin-bottom:15px}}
.cta p{{font-size:1.1em;color:{colors['muted']};margin-bottom:30px;max-width:600px;margin-left:auto;margin-right:auto}}
.cta .cta-btn{{display:inline-block;padding:14px 40px;font-size:1.1em;font-weight:700;color:#fff;background:{colors['accent']};border-radius:50px;text-decoration:none;transition:transform .2s}}
.cta .cta-btn:hover{{transform:translateY(-2px)}}
footer{{text-align:center;padding:30px;color:{colors['muted']};font-size:.85em;border-top:1px solid {colors['border']}}}
@media(max-width:600px){{.hero h1{{font-size:2em}}.hero{{padding:60px 15px}}.feature-grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<section class="hero">
    <h1>{title}</h1>
    {subtitle and f'<div class="subtitle">{subtitle}</div>' or ''}
    {summary and f'<p style="opacity:.85;margin-bottom:30px;max-width:600px;margin-left:auto;margin-right:auto;position:relative">{summary}</p>' or ''}
    <a href="#features" class="cta-btn">{cta_text}</a>
</section>
<section class="features" id="features">
    <h2>Key Features</h2>
    <div class="feature-grid">{features_html}</div>
</section>
<section class="cta">
    <h2>Ready to Get Started?</h2>
    <p>Join thousands of users who are already transforming their workflow.</p>
    <a href="#" class="cta-btn">Get Started Free</a>
</section>
<footer><p>© {datetime.now().year} {author}. All rights reserved.</p></footer>
</body>
</html>"""


def _build_blog_post(title, subtitle, author, summary, chapters,
                      colors, fonts, seo, icon_svg, structure) -> str:
    date = datetime.now().strftime("%B %d, %Y")

    content_html = ""
    for ch in chapters:
        for s in ch.get("sections", []):
            content_html += f"""
            <h2>{s.get('heading', '')}</h2>
            <p>{s.get('content', '')}</p>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title} — {author}</title>
{seo}
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:{fonts['body']};color:{colors['text']};background:{colors['background']};line-height:1.8}}
.article{{max-width:720px;margin:0 auto;padding:40px 20px}}
.article header{{margin-bottom:40px;text-align:center}}
.article h1{{font-family:{fonts['heading']};font-size:2.4em;color:{colors['heading']};margin-bottom:10px;line-height:1.2}}
.article .meta{{font-size:.9em;color:{colors['muted']};margin-bottom:20px}}
.article .summary{{font-size:1.1em;color:{colors['muted']};font-style:italic;margin-bottom:30px;padding:15px;border-left:3px solid {colors['accent']};background:{colors['highlight']};border-radius:0 8px 8px 0}}
.article h2{{font-family:{fonts['heading']};font-size:1.5em;color:{colors['heading']};margin:30px 0 15px}}
.article p{{margin-bottom:20px}}
.article p:first-of-type::first-letter{{font-size:3em;font-weight:700;color:{colors['accent']};float:left;line-height:1;margin-right:8px;font-family:{fonts['heading']}}}
.article blockquote{{border-left:3px solid {colors['accent']};padding:10px 20px;margin:20px 0;background:{colors['highlight']};font-style:italic;color:{colors['muted']};border-radius:0 8px 8px 0}}
.article .tags{{margin:30px 0;display:flex;gap:8px;flex-wrap:wrap}}
.article .tags span{{padding:4px 12px;background:{colors['surface']};border:1px solid {colors['border']};border-radius:100px;font-size:.85em;color:{colors['muted']}}}
.article footer{{margin-top:50px;padding-top:30px;border-top:1px solid {colors['border']};text-align:center;color:{colors['muted']};font-size:.9em}}
@media(max-width:600px){{.article h1{{font-size:1.6em}}.article{{padding:20px 15px}}}}
</style>
</head>
<body>
<article class="article">
    <header>
        <h1>{title}</h1>
        {subtitle and f'<p style="font-size:1.1em;color:{colors["muted"]}">{subtitle}</p>' or ''}
        <div class="meta">By <strong>{author}</strong> · {date}</div>
        {summary and f'<div class="summary">{summary}</div>' or ''}
    </header>
    {content_html}
    <div class="tags"><span>{structure.get("topic", "General")}</span></div>
    <footer><p>© {datetime.now().year} {author}. All rights reserved.</p></footer>
</article>
</body>
</html>"""


def build_tailwind_website(structure: dict, style: str = "minimal",
                           content_type: str = "landing-page") -> str:
    """Build a website using Tailwind + daisyUI components (from CMLP patterns)."""
    title = structure.get("title", "Page")
    subtitle = structure.get("subtitle", "")
    author = structure.get("author", "AI Design Engine")
    summary = structure.get("summary", "")
    chapters = structure.get("chapters", [])
    conclusion = structure.get("conclusion", {})
    daisyui = DAISYUI_MAP.get(style, "winter")

    features_html = ""
    for i, ch in enumerate(chapters[:6]):
        features_html += f"""
    <div class="card bg-base-200/50 shadow-sm hover:shadow-md transition-shadow duration-300">
      <div class="card-body items-center text-center">
        <div class="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-2 text-3xl">{"🚀🎯⚡💡📊🔧🎨📈🌟🔥💎🎯"[i % 12]}</div>
        <h3 class="card-title text-lg">{ch.get("title", f"Feature {i+1}")}</h3>
        <p class="text-sm text-base-content/70">{ch.get("introduction", ch.get("sections", [{}])[0].get("content", ""))[:120]}</p>
      </div>
    </div>"""

    toc_html = ""
    for i, ch in enumerate(chapters[:10]):
        toc_html += f"""
    <li class="list-row">
      <span class="text-primary font-mono text-sm">0{i+1}</span>
      <span class="flex-1">{ch.get("title", f"Chapter {i+1}")}</span>
      <span class="badge badge-ghost badge-sm">{len(ch.get("sections", []))} sections</span>
    </li>"""

    content_html = ""
    for ch in chapters:
        sections_html = ""
        for s in ch.get("sections", []):
            sections_html += f"""
        <div class="prose max-w-none">
          <h3 id="{s.get('heading', '').lower().replace(' ', '-')}" class="text-lg font-semibold mt-6 mb-2">{s.get("heading", "")}</h3>
          <p class="text-base-content/80 leading-relaxed">{s.get("content", "")}</p>
        </div>"""
        content_html += f"""
    <section id="ch-{chapters.index(ch)}" class="py-12 scroll-mt-20">
      <div class="flex items-center gap-4 mb-8">
        <span class="text-4xl text-primary/30 font-bold font-mono">0{chapters.index(ch)+1}</span>
        <div>
          <h2 class="text-2xl font-bold">{ch.get("title", "")}</h2>
          {ch.get("introduction", "") and f'<p class="text-base-content/60 italic">{ch["introduction"]}</p>' or ''}
        </div>
      </div>
      {sections_html}
    </section>"""

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="{daisyui}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title} — {author}</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://cdn.jsdelivr.net/npm/daisyui@4/dist/full.min.css" rel="stylesheet">
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
</head>
<body class="min-h-screen bg-base-100 text-base-content">
<nav class="navbar sticky top-0 z-50 bg-base-100/80 backdrop-blur-sm border-b border-base-200">
  <div class="navbar-start">
    <div class="dropdown">
      <div tabindex="0" role="button" class="btn btn-ghost lg:hidden">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h8m-8 6h16" /></svg>
      </div>
      <ul tabindex="0" class="menu menu-sm dropdown-content mt-3 z-10 p-2 shadow bg-base-100 rounded-box w-52">
        <li><a href="#features">Features</a></li>
        <li><a href="#content">Content</a></li>
        <li><a href="#cta">Get Started</a></li>
      </ul>
    </div>
    <a class="btn btn-ghost text-xl">{title}</a>
  </div>
  <div class="navbar-center hidden lg:flex">
    <ul class="menu menu-horizontal px-1">
      <li><a href="#features">Features</a></li>
      <li><a href="#content">Content</a></li>
      <li><a href="#cta">Get Started</a></li>
    </ul>
  </div>
  <div class="navbar-end">
    <a href="#cta" class="btn btn-primary btn-sm">{conclusion.get("title", "Get Started")}</a>
  </div>
</nav>

<section class="hero min-h-[70vh] bg-gradient-to-br from-primary via-primary/80 to-base-100">
  <div class="hero-content text-center">
    <div class="max-w-3xl">
      <h1 class="text-5xl md:text-7xl font-bold mb-6 text-primary-content">{title}</h1>
      {subtitle and f'<p class="text-xl text-primary-content/80 mb-8">{subtitle}</p>' or ''}
      {summary and f'<p class="text-lg text-primary-content/70 mb-8 max-w-2xl mx-auto">{summary}</p>' or ''}
      <div class="flex gap-4 justify-center">
        <a href="#content" class="btn btn-secondary btn-lg">Start Reading</a>
        <a href="#cta" class="btn btn-outline btn-lg text-primary-content border-primary-content/30 hover:bg-primary-content/10">Learn More</a>
      </div>
    </div>
  </div>
</section>

<section id="features" class="py-20 px-4 max-w-6xl mx-auto">
  <div class="text-center mb-12">
    <h2 class="text-3xl font-bold mb-3">Key Features</h2>
    <p class="text-base-content/60 max-w-xl mx-auto">Discover what makes this content unique and valuable</p>
  </div>
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
    {features_html}
  </div>
</section>

<section id="content" class="py-20 bg-base-200/50">
  <div class="max-w-4xl mx-auto px-4">
    <div class="text-center mb-12">
      <h2 class="text-3xl font-bold mb-3">Table of Contents</h2>
    </div>
    <ul class="list bg-base-100 rounded-box shadow-sm mb-12">
      {toc_html}
    </ul>
    {content_html}
  </div>
</section>

<section id="cta" class="py-20 px-4">
  <div class="max-w-2xl mx-auto text-center">
    <h2 class="text-3xl font-bold mb-4">{conclusion.get("title", "Ready to Dive In?")}</h2>
    <p class="text-lg text-base-content/70 mb-8">{conclusion.get("content", "Start exploring this content today.")[:200]}</p>
    <a href="#" class="btn btn-primary btn-lg">Get Full Access</a>
  </div>
</section>

<footer class="footer footer-center p-10 bg-base-200 text-base-content">
  <nav class="grid grid-flow-col gap-4">
    <a class="link link-hover">About</a>
    <a class="link link-hover">Privacy</a>
    <a class="link link-hover">Terms</a>
    <a class="link link-hover">Contact</a>
  </nav>
  <aside>
    <p>© {datetime.now().year} {author}. All rights reserved.</p>
  </aside>
</footer>
</body>
</html>"""
