import os
import re
from datetime import datetime

from jinja2 import Environment, FileSystemLoader

from backend.core.book_labels import LABELS, book_labels, language_code
from backend.core.color_engine import detect_topic, get_color_palette
from backend.core.icon_service import get_cover_icon
from backend.core.infographic_engine import render_infographic
from backend.themes import get_theme

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "templates")
env = Environment(loader=FileSystemLoader([
    TEMPLATE_DIR,
    os.path.join(TEMPLATE_DIR, "blocks"),
    os.path.join(TEMPLATE_DIR, "themes"),
]))
# Defaults for templates rendered without a book language (e.g. previews).
env.globals.update(labels=LABELS["en"], lang="en")
# Optional tool brand printed in generated books (publisher line, copyright
# page, back cover). Off by default: books are published under the author's
# name. Set BOOK_BRAND="..." to print one (e.g. a free-tier watermark).
BOOK_BRAND = os.getenv("BOOK_BRAND", "")
env.globals["book_brand"] = BOOK_BRAND


def paragraphs_html(text: str) -> str:
    """AI-written prose (paragraphs separated by blank lines) as one <p> per
    paragraph. Templates wrap it in a <div>, never a <p>: block content
    inside <p> is invalid HTML and fails EPUB validation."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
    return "".join(f"<p>{p}</p>" for p in paras)


# Style → theme mapping for display names that differ from theme IDs
STYLE_THEME_MAP = {
    "professional": "business",
    "minimal": "minimal",
    "creative": "creative",
    "academic": "academic",
    "modern": "modern",
    "dark": "dark",
    "business": "business",
    "finance": "finance",
    "technical": "technical",
    "wellness": "wellness",
}


def build_ebook_html(structure: dict, style: str, infographics: list,
                     introduction: str = "", author_bio: str = "",
                     references: list = None, glossary_terms: list = None,
                     back_cover_blurb: str = "", back_cover_tagline: str = "",
                     cover_svg: str = "", cover_image: str = "",
                     chapter_illustrations: list = None,
                     accent_color: str = "", bg_color: str = "",
                     heading_font: str = "", body_font: str = "") -> str:
    labels = book_labels(structure.get("language"))
    lang = language_code(structure.get("language"))

    def _render(template: str, **kwargs) -> str:
        return env.get_template(template).render(labels=labels, lang=lang, **kwargs)

    # 1. Detect topic → color palette
    topic = detect_topic(structure)
    topic_palette = get_color_palette(topic)

    # 2. Get theme (map display name to theme ID if needed)
    theme_id = STYLE_THEME_MAP.get(style, style)
    theme = get_theme(theme_id)
    colors = theme["colors"]
    fonts = theme["fonts"]

    # Override topic accent into theme
    if topic != "general":
        colors["accent"] = topic_palette["colors"]["accent"]
        colors["secondary"] = topic_palette["colors"]["secondary"]
        colors["highlight"] = topic_palette["colors"]["highlight"]

    # 3. Render infographics
    rendered = {}
    for ig in infographics:
        ci = ig.get("chapter_index", 0)
        si = ig.get("section_index", 0)
        key = f"{ci}_{si}"
        if key not in rendered:
            rendered[key] = []
        try:
            svg = render_infographic(ig, colors)
            rendered[key].append({
                "svg": svg,
                "title": ig.get("title", "Diagram"),
                "description": ig.get("description", ""),
            })
        except Exception:
            pass

    # 4. Cover icon
    cover_icon_svg = get_cover_icon(topic, colors["accent"], 80)

    # 5. Build page blocks
    chapters = structure.get("chapters", [])
    toc_items = [
        {"number": i + 1, "title": ch.get("title", f"Chapter {i+1}"),
         "sections": len(ch.get("sections", []))}
        for i, ch in enumerate(chapters)
    ]
    conclusion = structure.get("conclusion", {})

    # 6. Render pages
    pages = []
    if references is None:
        references = []
    if glossary_terms is None:
        glossary_terms = []
    if chapter_illustrations is None:
        chapter_illustrations = []
    # Build chapter illustration lookup
    ch_ills = {}
    for ill in chapter_illustrations:
        ch_ills[ill.get("chapter_index")] = ill.get("image_uri") or ill.get("svg", "")
    introduction_text = introduction
    references_list = references
    cover_html = _render("cover.html",
        title=structure.get("title", "Ebook"),
        subtitle=structure.get("subtitle", ""),
        author=structure.get("author", ""),
        summary=structure.get("summary", ""),
        icon=cover_icon_svg,
        cover_svg=cover_svg,
        cover_image=cover_image,
        date=datetime.now().strftime("%B %d, %Y"),
    )
    pages.append(cover_html)

    # Copyright
    copyright_html = _render("copyright.html",
        title=structure.get("title", "Ebook"),
        subtitle=structure.get("subtitle", ""),
        author=structure.get("author", ""),
        year=datetime.now().year,
    )
    pages.append(copyright_html)

    # Introduction
    if introduction_text:
        intro_html = _render("introduction.html",
            title=labels["introduction"],
            content=paragraphs_html(introduction_text),
        )
        pages.append(intro_html)

    # TOC
    if toc_items:
        toc_html = _render("toc.html", items=toc_items)
        pages.append(toc_html)

    # Chapters
    for ci, ch in enumerate(chapters):
        sections = []
        for si, sec in enumerate(ch.get("sections", [])):
            sections.append({
                "heading": sec.get("heading", ""),
                "content": paragraphs_html(sec.get("content", "")),
            })
            # Insert infographic after this section if exists
            key = f"{ci}_{si}"
            if key in rendered:
                for ig in rendered[key]:
                    ig_html = _render("infographic.html", **ig)
                    sections.append({"heading": "", "content": ig_html})

        # Structural elements (summary, faq, checklist)
        if ch.get("chapter_summary"):
            sections.append({
                "heading": "",
                "content": _render("summary.html", **ch["chapter_summary"]),
            })
        if ch.get("faq"):
            sections.append({
                "heading": "",
                "content": _render("faq.html", items=ch["faq"]),
            })
        if ch.get("checklist"):
            sections.append({
                "heading": "",
                "content": _render("checklist.html", **ch["checklist"]),
            })

        ch_ill_svg = ch_ills.get(ci, "")
        ch_html = _render("chapter.html",
            number=ci + 1,
            title=ch.get("title", f"Chapter {ci+1}"),
            introduction=ch.get("introduction", ""),
            key_takeaway=ch.get("key_takeaway", ""),
            sections=sections,
            illustration=ch_ill_svg,
        )
        pages.append(ch_html)

    # Conclusion
    if conclusion:
        conc_html = _render("conclusion.html",
            title=conclusion.get("title", "Conclusion"),
            content=paragraphs_html(conclusion.get("content", "")),
        )
        pages.append(conc_html)

    # Author Bio
    if author_bio:
        author_html = _render("author.html", bio=author_bio)
        pages.append(author_html)

    # References
    if references_list:
        ref_html = _render("references.html",
            title=labels["references"],
            items=references_list,
            content="",
        )
        pages.append(ref_html)

    # Glossary
    if glossary_terms:
        gloss_html = _render("glossary.html", terms=glossary_terms)
        pages.append(gloss_html)

    # Back Cover
    if back_cover_blurb:
        back_html = _render("back_cover.html",
            blurb=back_cover_blurb,
            author=structure.get("author", ""),
            tagline=back_cover_tagline,
            icon="📖",
        )
        pages.append(back_html)

    # Apply custom overrides
    if accent_color and accent_color.startswith("#"):
        colors["accent"] = accent_color
    if bg_color and bg_color.startswith("#"):
        colors["background"] = bg_color
    if heading_font:
        fonts["heading"] = heading_font
    if body_font:
        fonts["body"] = body_font
    # Rebuild theme with overrides
    theme["colors"] = colors
    theme["fonts"] = fonts

    # 7. Wrap in base template
    context = {
        "theme": theme,
        "meta": {
            "title": structure.get("title", "Ebook"),
            "author": structure.get("author", ""),
            "date": datetime.now().strftime("%B %d, %Y"),
            "topic": topic,
        },
        "content": "\n".join(pages),
    }

    base = env.get_template("base.html")
    return base.render(lang=lang, labels=labels, **context)
