import os
from datetime import datetime

from jinja2 import Environment, FileSystemLoader

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
    cover_html = env.get_template("cover.html").render(
        title=structure.get("title", "Ebook"),
        subtitle=structure.get("subtitle", ""),
        author=structure.get("author", "AI Design Engine"),
        summary=structure.get("summary", ""),
        icon=cover_icon_svg,
        cover_svg=cover_svg,
        cover_image=cover_image,
        date=datetime.now().strftime("%B %d, %Y"),
    )
    pages.append(cover_html)

    # Copyright
    copyright_html = env.get_template("copyright.html").render(
        title=structure.get("title", "Ebook"),
        subtitle=structure.get("subtitle", ""),
        date=datetime.now().strftime("%B %d, %Y"),
    )
    pages.append(copyright_html)

    # Introduction
    if introduction_text:
        intro_html = env.get_template("introduction.html").render(
            title="Introduction",
            content=introduction_text,
        )
        pages.append(intro_html)

    # TOC
    if toc_items:
        toc_html = env.get_template("toc.html").render(items=toc_items)
        pages.append(toc_html)

    # Chapters
    for ci, ch in enumerate(chapters):
        sections = []
        for si, sec in enumerate(ch.get("sections", [])):
            sections.append({
                "heading": sec.get("heading", ""),
                "content": sec.get("content", ""),
            })
            # Insert infographic after this section if exists
            key = f"{ci}_{si}"
            if key in rendered:
                for ig in rendered[key]:
                    ig_html = env.get_template("infographic.html").render(**ig)
                    sections.append({"heading": "", "content": ig_html})

        # Structural elements (summary, faq, checklist)
        if ch.get("chapter_summary"):
            sections.append({
                "heading": "",
                "content": env.get_template("summary.html").render(**ch["chapter_summary"]),
            })
        if ch.get("faq"):
            sections.append({
                "heading": "",
                "content": env.get_template("faq.html").render(items=ch["faq"]),
            })
        if ch.get("checklist"):
            sections.append({
                "heading": "",
                "content": env.get_template("checklist.html").render(**ch["checklist"]),
            })

        ch_ill_svg = ch_ills.get(ci, "")
        ch_html = env.get_template("chapter.html").render(
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
        conc_html = env.get_template("conclusion.html").render(
            title=conclusion.get("title", "Conclusion"),
            content=conclusion.get("content", ""),
        )
        pages.append(conc_html)

    # Author Bio
    if author_bio:
        author_html = env.get_template("author.html").render(bio=author_bio)
        pages.append(author_html)

    # References
    if references_list:
        ref_html = env.get_template("references.html").render(
            title="References & Further Reading",
            items=references_list,
            content="",
        )
        pages.append(ref_html)

    # Glossary
    if glossary_terms:
        gloss_html = env.get_template("glossary.html").render(terms=glossary_terms)
        pages.append(gloss_html)

    # Back Cover
    if back_cover_blurb:
        back_html = env.get_template("back_cover.html").render(
            blurb=back_cover_blurb,
            author=structure.get("author", "AI Design Engine"),
            tagline=back_cover_tagline or "AI-Powered Publishing",
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
            "author": structure.get("author", "AI Design Engine"),
            "date": datetime.now().strftime("%B %d, %Y"),
            "topic": topic,
        },
        "content": "\n".join(pages),
    }

    base = env.get_template("base.html")
    return base.render(**context)
