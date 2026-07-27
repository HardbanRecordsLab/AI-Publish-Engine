import json
import os
from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from backend.config import settings
from backend.core.ai import _try_providers
from backend.core.color_engine import list_topics
from backend.limiter import limiter
from backend.themes import generate_theme_css, get_theme, list_themes

router = APIRouter()

TEMPLATES = {
    "ebook": [
        {"id": "minimal", "theme": "minimal", "name": "Minimal", "desc": "Clean, minimalistic layout with ample white space", "color": "#1a1a2e", "icon": "\U0001f4c4"},
        {"id": "professional", "theme": "professional", "name": "Professional", "desc": "Corporate-grade design for business content", "color": "#0f3460", "icon": "\U0001f4bc"},
        {"id": "creative", "theme": "creative", "name": "Creative", "desc": "Bold, artistic layout for creative works", "color": "#533483", "icon": "\U0001f3a8"},
        {"id": "academic", "theme": "academic", "name": "Academic", "desc": "Formal structure for research and papers", "color": "#2d4059", "icon": "\U0001f393"},
        {"id": "modern", "theme": "modern", "name": "Modern", "desc": "Contemporary design with clean typography", "color": "#16213e", "icon": "\u2728"},
        {"id": "dark", "theme": "dark", "name": "Dark Premium", "desc": "Dark-themed premium layout", "color": "#0B0F1A", "icon": "\U0001f319"},
        {"id": "business", "theme": "business", "name": "Business Pro", "desc": "Professional authoritative layout", "color": "#1D4ED8", "icon": "\U0001f4bc"},
        {"id": "finance", "theme": "finance", "name": "Financial", "desc": "Premium financial layout", "color": "#B8860B", "icon": "\U0001f4ca"},
        {"id": "technical", "theme": "technical", "name": "Technical", "desc": "Clean technical documentation", "color": "#0EA5E9", "icon": "\u2699\ufe0f"},
        {"id": "wellness", "theme": "wellness", "name": "Wellness", "desc": "Calm wellness-centered design", "color": "#22C55E", "icon": "\U0001f33f"},
    ],
    "website": [
        {"id": "landing", "name": "Landing Page", "desc": "High-conversion single-page layout", "color": "#1a1a2e", "icon": "\U0001f680"},
        {"id": "blog", "name": "Blog", "desc": "Content-focused blog layout", "color": "#0f3460", "icon": "\u270d\ufe0f"},
        {"id": "docs", "name": "Documentation", "desc": "Technical documentation layout", "color": "#2d4059", "icon": "\U0001f4da"},
        {"id": "portfolio", "name": "Portfolio", "desc": "Showcase portfolio for creators", "color": "#533483", "icon": "\U0001f5bc\ufe0f"},
    ],
    "landing-page": [
        {"id": "startup", "name": "Startup", "desc": "Modern startup launch page", "color": "#0f3460", "icon": "\u26a1"},
        {"id": "saas", "name": "SaaS", "desc": "Software product landing page", "color": "#1a1a2e", "icon": "\u2601\ufe0f"},
        {"id": "product", "name": "Product Launch", "desc": "Product reveal with countdown", "color": "#533483", "icon": "\U0001f3af"},
        {"id": "leadgen", "name": "Lead Gen", "desc": "Lead capture optimized layout", "color": "#2d4059", "icon": "\U0001f4cb"},
    ],
    "blog-post": [
        {"id": "story", "name": "Story", "desc": "Narrative-driven longform layout", "color": "#1a1a2e", "icon": "\U0001f4d6"},
        {"id": "tutorial", "name": "Tutorial", "desc": "Step-by-step guide layout", "color": "#0f3460", "icon": "\U0001f527"},
        {"id": "listicle", "name": "Listicle", "desc": "List-style engaging content", "color": "#533483", "icon": "\U0001f4cb"},
        {"id": "interview", "name": "Interview", "desc": "Q&A interview format", "color": "#16213e", "icon": "\U0001f399\ufe0f"},
    ],
}

# "professional" is the only style id with no matching templates/themes/
# folder — builder.py's own STYLE_THEME_MAP aliases it to "business" for
# real generation, so the preview does the same here. Every other id below
# now has a real templates/themes/<id>/theme.css (see git history), so the
# preview endpoint's default `.get(style, style)` fallback resolves them
# correctly without needing an entry — a stale entry here would silently
# make the live preview show a different theme than actual generation
# produces, which is exactly the bug this map used to paper over.
STYLE_THEME_PREVIEW_MAP = {
    "professional": "business",
}


@router.get("/api/templates")
@limiter.limit("60/minute")
def get_templates(request: Request):
    return TEMPLATES


@router.get("/api/template-preview/{style}")
@limiter.limit("60/minute")
def template_preview(request: Request, style: str):
    theme_id = STYLE_THEME_PREVIEW_MAP.get(style, style)
    theme = get_theme(theme_id)
    if not theme:
        theme = get_theme("minimal")
        theme_id = "minimal"
    css = generate_theme_css(theme_id)
    topic_colors = {
        "accent": theme["colors"]["accent"],
        "secondary": theme["colors"]["secondary"],
        "highlight": theme["colors"]["highlight"],
    }
    html = f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<style>{css}
body{{font-family:var(--font-body);background:var(--color-bg);color:var(--color-text);margin:0;padding:20px;}}
.preview{{max-width:400px;margin:0 auto;border-radius:12px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,.15);}}
.preview-cover{{background:{theme['cover_gradient']};padding:30px 24px;text-align:center;color:#fff;}}
.preview-cover h1{{font-family:var(--font-heading);font-size:20px;margin:0 0 6px;font-weight:800;letter-spacing:-.5px;}}
.preview-cover p{{font-size:11px;opacity:.8;margin:0;}}
.preview-chapter{{padding:16px 20px;background:var(--color-surface);}}
.preview-chapter .num{{font-size:9px;text-transform:uppercase;letter-spacing:2px;color:var(--color-accent);font-weight:600;}}
.preview-chapter h2{{font-family:var(--font-heading);font-size:15px;color:var(--color-heading);margin:4px 0 8px;font-weight:700;}}
.preview-chapter p{{font-size:11px;line-height:1.5;color:var(--color-muted);margin:0;}}
.preview-footer{{background:var(--color-surface);border-top:1px solid var(--color-border);padding:10px 20px;display:flex;justify-content:space-between;font-size:9px;color:var(--color-muted);}}
.preview-divider{{height:4px;background:linear-gradient(90deg,{topic_colors['accent']},{topic_colors['secondary']});}}
</style></head><body>
<div class="preview">
<div class="preview-cover"><h1>The Future of AI</h1><p>A Comprehensive Guide</p></div>
<div class="preview-divider"></div>
<div class="preview-chapter">
<div class="num">Chapter 1</div><h2>Understanding Intelligence</h2>
<p>Artificial intelligence has transformed how we interact with technology. This chapter explores the fundamental concepts that drive modern AI systems...</p>
</div>
<div class="preview-divider"></div>
<div class="preview-chapter">
<div class="num">Chapter 2</div><h2>Machine Learning</h2>
<p>Discover how machines learn from data, recognize patterns, and make decisions with increasing accuracy...</p>
</div>
<div class="preview-footer"><span>{theme['name']}</span><span>{theme['vibe']}</span></div>
</div></body></html>"""
    return HTMLResponse(content=html, media_type="text/html")


@router.get("/api/themes")
@limiter.limit("60/minute")
def get_themes(request: Request):
    return list_themes()


@router.get("/api/topics")
@limiter.limit("60/minute")
def get_topics(request: Request):
    return list_topics()


@router.post("/api/themes/generate")
@limiter.limit("10/minute")  # calls an AI provider — same ceiling as other AI-cost endpoints
def generate_theme_from_description(request: Request, description: str):
    if not description or len(description) < 3:
        return JSONResponse({"error": "Description too short"}, status_code=400)
    existing_ids = ", ".join(f'"{t["id"]}"' for t in list_themes())
    system = "You are a professional UI designer. Return only valid JSON."
    user = f"""Generate a complete ebook design theme based on this description: "{description}"

Return a JSON object with these fields:
- id: a short kebab-case id (e.g. "ocean-sunset")
- name: a display name (e.g. "Ocean Sunset")
- vibe: a short vibe description (e.g. "calm sunset warm")
- colors: object with keys: background, surface, text, heading, accent, secondary, muted, border, highlight, success, warning, error, info (all hex colors)
- fonts: object with keys: heading (CSS font-family), body (CSS font-family)
- cover_gradient: a CSS linear-gradient or radial-gradient for the cover
- accent_gradient: a CSS linear-gradient with two stops
- cover_icon: a Material Design icon name (e.g. "mdi:palette")

Existing theme IDs: {existing_ids}

Make the id unique (not in the existing list). All colors must be valid hex codes."""
    try:
        raw = _try_providers(system, user, preferred=settings.ai_provider)
        theme = json.loads(raw)
        required = ["id", "name", "colors", "fonts", "cover_gradient", "accent_gradient"]
        for key in required:
            if key not in theme:
                return JSONResponse({"error": f"AI response missing '{key}'"}, status_code=500)
        c = theme["colors"]
        f = theme["fonts"]
        fs = theme.get("font_sizes", {"h1": "40pt", "h2": "24pt", "h3": "16pt", "body": "10.5pt"})
        css = f""":root {{
  --color-bg: {c['background']};
  --color-surface: {c.get('surface', c['background'])};
  --color-text: {c['text']};
  --color-heading: {c['heading']};
  --color-accent: {c['accent']};
  --color-secondary: {c.get('secondary', '#F5F5F5')};
  --color-muted: {c.get('muted', '#999999')};
  --color-border: {c.get('border', '#E5E5E5')};
  --color-highlight: {c.get('highlight', '#F0F0F0')};
  --font-heading: {f['heading']};
  --font-body: {f['body']};
  --font-size-h1: {fs['h1']};
  --font-size-h2: {fs['h2']};
  --font-size-h3: {fs['h3']};
  --font-size-body: {fs['body']};
  --cover-gradient: {theme['cover_gradient']};
  --accent-gradient: {theme.get('accent_gradient', f"linear-gradient(135deg, {c['accent']} 0%, {c.get('secondary', '#333')} 100%)")};
}}"""
        return {"theme": theme, "css": css}
    except json.JSONDecodeError:
        return JSONResponse({"error": "AI returned invalid JSON"}, status_code=500)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


CUSTOM_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates" / "custom"
os.makedirs(str(CUSTOM_TEMPLATES_DIR), exist_ok=True)


@router.post("/api/templates/upload")
@limiter.limit("20/minute")
async def upload_custom_template(request: Request, file: UploadFile = File(...), name: str = Form("")):
    if not file.filename.lower().endswith(".html"):
        return JSONResponse({"error": "Only .html files allowed"}, status_code=400)
    content = await file.read()
    text = content.decode("utf-8")
    if "{{title}}" not in text and "{{content}}" not in text:
        return JSONResponse({"error": "Template must contain {{title}} or {{content}} placeholder"}, status_code=400)
    safe_name = name or file.filename.rsplit(".", 1)[0]
    filepath = CUSTOM_TEMPLATES_DIR / f"{safe_name}.html"
    filepath.write_text(text, encoding="utf-8")
    return {"name": safe_name, "path": str(filepath)}


@router.get("/api/templates/custom")
@limiter.limit("60/minute")
def list_custom_templates(request: Request):
    if not CUSTOM_TEMPLATES_DIR.exists():
        return []
    templates = []
    for f in sorted(CUSTOM_TEMPLATES_DIR.glob("*.html")):
        templates.append({
            "id": f.stem,
            "name": f.stem.replace("_", " ").replace("-", " ").title(),
            "path": str(f),
        })
    return templates


@router.get("/api/embed/{job_id}")
@limiter.limit("60/minute")
def embed_book(request: Request, job_id: str):
    """Return an embeddable iframe snippet for an interactive book."""
    from backend.core.jobs import get_job
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job["status"] != "done":
        return JSONResponse({"error": "Job not ready"}, status_code=400)
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Embed — {job.get("topic", "Book")}</title>
<style>body{{margin:0;padding:0;overflow:hidden;background:#fff}}iframe{{width:100vw;height:100vh;border:none}}</style>
</head>
<body>
<iframe src="/api/preview/{job_id}" width="100%" height="100%" allowfullscreen></iframe>
</body>
</html>""")


@router.get("/api/guide")
@limiter.limit("60/minute")
def get_guide(request: Request):
    guide_path = Path(__file__).parent.parent.parent / "GUIDE.md"
    if guide_path.exists():
        return HTMLResponse(content=guide_path.read_text(encoding="utf-8"), media_type="text/markdown")
    return JSONResponse({"error": "Guide not found"}, status_code=404)
