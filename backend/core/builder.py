import os
import re
from datetime import datetime

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup, escape

from backend.core.book_kinds import get_kind, normalize_blocks
from backend.core.book_labels import LABELS, book_labels, language_code
from backend.core.color_engine import detect_topic, get_color_palette
from backend.core.icon_service import get_cover_icon
from backend.core.infographic_engine import render_infographic
from backend.core.pdf import PRINT_MARGINS
from backend.themes import get_theme

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "templates")
_BLOCK_TEMPLATES = frozenset(os.listdir(os.path.join(TEMPLATE_DIR, "blocks")))
env = Environment(
    loader=FileSystemLoader([
        TEMPLATE_DIR,
        os.path.join(TEMPLATE_DIR, "blocks"),
        os.path.join(TEMPLATE_DIR, "themes"),
    ]),
    # Block templates print AI-written text: escape it, or a stray "<" or
    # "&" in the prose breaks the page (and fails EPUB validation). Values
    # that are deliberately HTML are passed as Markup. base.html and the
    # theme templates stay unescaped: they interpolate CSS (font stacks with
    # quotes) that escaping would corrupt.
    autoescape=lambda name: name in _BLOCK_TEMPLATES,
)
# Defaults for templates rendered without a book language (e.g. previews).
env.globals.update(labels=LABELS["en"], lang="en")
# Optional tool brand printed in generated books (publisher line, copyright
# page, back cover). Off by default: books are published under the author's
# name. Set BOOK_BRAND="..." to print one (e.g. a free-tier watermark).
BOOK_BRAND = os.getenv("BOOK_BRAND", "")
env.globals["book_brand"] = BOOK_BRAND


def chapter_blocks(ch: dict) -> tuple[list, list]:
    """A chapter's own blocks split into (before the sections, after them):
    quizzes and exercises close a chapter; facts, materials, warnings open it."""
    blocks = normalize_blocks(ch.get("blocks"))
    return ([b for b in blocks if b["type"] not in ("quiz", "exercise")],
            [b for b in blocks if b["type"] in ("quiz", "exercise")])


def _css_string(text: str) -> str:
    """Escape text for a CSS string literal (content: "…")."""
    return (text or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


_HYPHEN_DICTS: dict = {}
_LONG_WORD = re.compile(r"\w{7,}")


def hyphenate(text: str, lang: str) -> str:
    """Insert soft hyphens (U+00AD) so justified print text can break long
    words instead of stretching word gaps. Text unchanged if pyphen has no
    dictionary for the language."""
    if lang not in _HYPHEN_DICTS:
        try:
            import pyphen
            _HYPHEN_DICTS[lang] = pyphen.Pyphen(lang=lang) if pyphen.language_fallback(lang) else None
        except ImportError:
            _HYPHEN_DICTS[lang] = None
    dic = _HYPHEN_DICTS[lang]
    if not dic or not text:
        return text
    return _LONG_WORD.sub(lambda m: dic.inserted(m.group(0), hyphen="\u00ad"), text)


def paragraphs_html(text: str) -> str:
    """AI-written prose (paragraphs separated by blank lines) as one <p> per
    paragraph. Templates wrap it in a <div>, never a <p>: block content
    inside <p> is invalid HTML and fails EPUB validation."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
    return Markup("".join(f"<p>{escape(p)}</p>" for p in paras))


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
                     heading_font: str = "", body_font: str = "",
                     print_trim: dict | None = None, isbn: str = "",
                     recto_blanks: set | None = None, page_markers: bool = False) -> str:
    """Full book HTML. With print_trim ({"width": in, "height": in}) it is a
    print interior instead: that trim size, mirrored margins, running heads,
    a title page, white paper, hyphenated text, and no front/back cover (KDP
    and printers take the cover as a separate file). recto_blanks /
    page_markers serve backend.core.print_book's two-pass recto layout."""
    labels = book_labels(structure.get("language"))
    lang = language_code(structure.get("language"))

    def _render(template: str, **kwargs) -> Markup:
        return Markup(env.get_template(template).render(labels=labels, lang=lang, **kwargs))

    def _prose(text: str) -> str:
        return paragraphs_html(hyphenate(text, lang) if print_trim else text)

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
            svg = Markup(render_infographic(ig, colors))
            rendered[key].append({
                "svg": svg,
                "title": ig.get("title", "Diagram"),
                "description": ig.get("description", ""),
            })
        except Exception:
            pass

    # 4. Cover icon
    cover_icon_svg = Markup(get_cover_icon(topic, colors["accent"], 80))

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
        cover_svg=Markup(cover_svg or ""),
        cover_image=cover_image,
        date=datetime.now().strftime("%B %d, %Y"),
    )
    if print_trim:
        pages.append(_render("title_page.html",
                             title=structure.get("title", ""),
                             subtitle=structure.get("subtitle", ""),
                             author=structure.get("author", "")))
    else:
        pages.append(cover_html)

    # Copyright
    copyright_html = _render("copyright.html",
        title=structure.get("title", "Ebook"),
        subtitle=structure.get("subtitle", ""),
        author=structure.get("author", ""),
        year=datetime.now().year,
        isbn=isbn,
    )
    pages.append(copyright_html)

    # Introduction
    if introduction_text:
        intro_html = _render("introduction.html",
            title=labels["introduction"],
            content=_prose(introduction_text),
        )
        pages.append(intro_html)

    # TOC
    if toc_items:
        toc_html = _render("toc.html", items=toc_items)
        pages.append(toc_html)

    # Chapters
    spec = get_kind(structure.get("kind"))

    def _rich(blocks: list) -> Markup:
        return _render("rich.html", blocks=blocks) if blocks else Markup("")

    for ci, ch in enumerate(chapters):
        sections = []
        start_blocks, end_blocks = chapter_blocks(ch)
        if start_blocks:
            sections.append({"heading": "", "content": _rich(start_blocks)})
        for si, sec in enumerate(ch.get("sections", [])):
            sections.append({
                "heading": sec.get("heading", ""),
                "content": _prose(sec.get("content", "")) + _rich(normalize_blocks(sec.get("blocks"))),
            })
            # Insert infographic after this section if exists
            key = f"{ci}_{si}"
            if key in rendered:
                for ig in rendered[key]:
                    ig_html = _render("infographic.html", **ig)
                    sections.append({"heading": "", "content": ig_html})

        if end_blocks:
            sections.append({"heading": "", "content": _rich(end_blocks)})

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

        ch_ill_svg = Markup(ch_ills.get(ci, ""))
        if recto_blanks and ci in recto_blanks:
            # Keeps this chapter opening on a right-hand page.
            pages.append('<div class="blank-page page" style="page: front; height: 1px;"></div>')
        ch_html = _render("chapter.html",
            number=ci + 1,
            title=ch.get("title", f"Chapter {ci+1}"),
            introduction=ch.get("introduction", "") if spec.show_intro else "",
            key_takeaway=ch.get("key_takeaway", "") if spec.show_takeaway else "",
            sections=sections,
            scene_breaks=spec.scene_breaks,
            illustration=ch_ill_svg,
            page_marker=f"§CH{ci}§" if page_markers else "",
        )
        pages.append(ch_html)

    # Conclusion
    if conclusion:
        conc_html = _render("conclusion.html",
            title=conclusion.get("title", "Conclusion"),
            content=_prose(conclusion.get("content", "")),
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

    # Back Cover (screen/ebook only — a print interior never includes covers)
    if back_cover_blurb and not print_trim:
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
        "print_trim": print_trim,
        "print_margins": PRINT_MARGINS,
        "running_left": _css_string(structure.get("author") or structure.get("title", "")),
        "running_right": _css_string(structure.get("title", "")),
    }

    base = env.get_template("base.html")
    return base.render(lang=lang, labels=labels, kind=spec.id, **context)
