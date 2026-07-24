import os
import re
from datetime import datetime
from ebooklib import epub
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from backend.themes import get_theme
from backend.core.color_engine import detect_topic, get_color_palette
from backend.core.icon_service import get_cover_icon
from backend.core.infographic_engine import render_infographic
from backend.core.builder import env


def _html_to_text(html: str) -> str:
    html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'</p>', '\n\n', html, flags=re.IGNORECASE)
    html = re.sub(r'<[^>]+>', '', html)
    html = re.sub(r'\n{3,}', '\n\n', html)
    return html.strip()


def _svg_to_png(svg: str, output_path: str) -> bool:
    try:
        import cairosvg
        cairosvg.svg2png(bytestring=svg.encode('utf-8'), write_to=output_path)
        return True
    except Exception:
        return False


def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip('#')
    if len(h) < 6:
        h = h * 6
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _build_common(structure, style, infographics,
                  introduction="", author_bio="",
                  references=None, glossary_terms=None,
                  back_cover_blurb="", back_cover_tagline="",
                  cover_svg="", cover_image="",
                  chapter_illustrations=None):
    if references is None:
        references = []
    if glossary_terms is None:
        glossary_terms = []
    if chapter_illustrations is None:
        chapter_illustrations = []

    topic = detect_topic(structure)
    topic_palette = get_color_palette(topic)
    theme = get_theme(style)
    colors = theme["colors"].copy()
    colors["cover_gradient"] = theme.get("cover_gradient", "linear-gradient(135deg, #0F172A 0%, #1E3A5F 50%, #1D4ED8 100%)")
    fonts = theme["fonts"]

    if topic != "general":
        colors["accent"] = topic_palette["colors"]["accent"]
        colors["secondary"] = topic_palette["colors"]["secondary"]
        colors["highlight"] = topic_palette["colors"]["highlight"]

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

    ch_ills = {}
    for ill in chapter_illustrations:
        ch_ills[ill.get("chapter_index")] = ill.get("image_uri") or ill.get("svg", "")

    cover_icon_svg = get_cover_icon(topic, colors["accent"], 80)

    return {
        "topic": topic, "theme": theme, "colors": colors, "fonts": fonts,
        "rendered": rendered, "ch_ills": ch_ills, "cover_icon_svg": cover_icon_svg,
        "introduction": introduction, "author_bio": author_bio,
        "references": references, "glossary_terms": glossary_terms,
        "back_cover_blurb": back_cover_blurb, "back_cover_tagline": back_cover_tagline,
        "cover_svg": cover_svg, "cover_image": cover_image,
    }


def build_epub(structure: dict, style: str, infographics: list, output_path: str,
               introduction="", author_bio="",
               references=None, glossary_terms=None,
               back_cover_blurb="", back_cover_tagline="",
               cover_svg="", cover_image="",
               chapter_illustrations=None) -> str:
    ctx = _build_common(structure, style, infographics,
                        introduction, author_bio, references, glossary_terms,
                        back_cover_blurb, back_cover_tagline,
                        cover_svg, cover_image, chapter_illustrations)
    colors = ctx["colors"]
    fonts = ctx["fonts"]

    book = epub.EpubBook()
    book.set_identifier(f"ebook-{datetime.now().timestamp()}")
    book.set_title(structure.get("title", "Ebook"))
    book.set_language("en")
    book.add_author(structure.get("author", "AI Design Engine"))

    spine = ['nav']
    toc = []

    css_content = f"""
    @namespace epub "http://www.idpf.org/2007/ops";
    body {{ font-family: {fonts['body']}; color: {colors['text']}; background: {colors['background']}; line-height: 1.6; margin: 0; padding: 0; }}
    h1 {{ font-family: {fonts['heading']}; color: {colors['heading']}; font-size: 1.8em; margin-top: 1em; }}
    h2 {{ font-family: {fonts['heading']}; color: {colors['accent']}; font-size: 1.4em; margin-top: 0.8em; }}
    h3 {{ font-family: {fonts['heading']}; color: {colors['accent']}; font-size: 1.1em; }}
    p {{ margin: 0.5em 0; text-align: justify; }}
    .chapter-header {{ border-bottom: 1px solid {colors['border']}; margin-bottom: 1em; }}
    .chapter-number {{ color: {colors['accent']}; font-size: 0.8em; text-transform: uppercase; letter-spacing: 2px; }}
    .takeaway {{ background: {colors['highlight']}; border-left: 3px solid {colors['accent']}; padding: 0.5em; margin: 1em 0; }}
    .cover-page {{ text-align: center; padding: 20% 2em; background: {colors['cover_gradient']}; color: white; }}
    .cover-page h1 {{ font-family: {fonts['heading']}; font-size: 2.2em; color: white; }}
    .cover-page .subtitle {{ font-size: 1.1em; opacity: 0.85; }}
    .cover-page .meta {{ font-size: 0.8em; opacity: 0.7; margin-top: 2em; }}
    .toc-item {{ padding: 0.3em 0; }}
    .section {{ margin-bottom: 1em; }}
    img.chapter-ill {{ max-width: 100%; height: auto; border-radius: 4px; margin: 0.5em 0; }}
    """

    style_css = epub.EpubItem(uid="style", file_name="style/style.css", media_type="text/css", content=css_content)
    book.add_item(style_css)

    def add_page(html_content, title, filename, is_cover=False):
        if is_cover:
            html_full = f'<!DOCTYPE html><html><head><link rel="stylesheet" type="text/css" href="style/style.css"/></head><body class="cover-page">{html_content}</body></html>'
        else:
            html_full = f'<!DOCTYPE html><html><head><link rel="stylesheet" type="text/css" href="style/style.css"/></head><body>{html_content}</body></html>'
        page = epub.EpubHtml(title=title, file_name=filename, lang="en")
        page.content = html_full.encode('utf-8')
        book.add_item(page)
        return page

    # Cover
    cover_data = env.get_template("cover.html").render(
        title=structure.get("title", "Ebook"),
        subtitle=structure.get("subtitle", ""),
        author=structure.get("author", "AI Design Engine"),
        summary=structure.get("summary", ""),
        icon=ctx["cover_icon_svg"],
        cover_svg=ctx["cover_svg"],
        cover_image=ctx["cover_image"],
        date=datetime.now().strftime("%B %d, %Y"),
    )
    cover_page = add_page(cover_data, "Cover", "cover.xhtml", is_cover=True)
    spine.insert(0, cover_page)
    toc.append(epub.Link("cover.xhtml", "Cover", "cover"))

    # Introduction
    if ctx["introduction"]:
        intro_html = env.get_template("introduction.html").render(title="Introduction", content=ctx["introduction"])
        page = add_page(intro_html, "Introduction", "intro.xhtml")
        spine.append(page)
        toc.append(epub.Link("intro.xhtml", "Introduction", "intro"))

    # Chapters
    chapters = structure.get("chapters", [])
    for ci, ch in enumerate(chapters):
        sections = []
        for si, sec in enumerate(ch.get("sections", [])):
            sec_html = f"<h2>{sec.get('heading', '')}</h2>\n{sec.get('content', '')}"
            key = f"{ci}_{si}"
            if key in ctx["rendered"]:
                for ig in ctx["rendered"][key]:
                    sec_html += f'\n<h3>{ig["title"]}</h3>\n{ig["svg"]}'
            sections.append({"heading": "", "content": sec_html})

        if ch.get("chapter_summary"):
            sections.append({"heading": "", "content": env.get_template("summary.html").render(**ch["chapter_summary"])})
        if ch.get("faq"):
            sections.append({"heading": "", "content": env.get_template("faq.html").render(items=ch["faq"])})
        if ch.get("checklist"):
            sections.append({"heading": "", "content": env.get_template("checklist.html").render(**ch["checklist"])})

        ch_html = env.get_template("chapter.html").render(
            number=ci + 1,
            title=ch.get("title", f"Chapter {ci+1}"),
            introduction=ch.get("introduction", ""),
            key_takeaway=ch.get("key_takeaway", ""),
            sections=sections,
            illustration=ctx["ch_ills"].get(ci, ""),
        )

        ch_file = f"ch{ci+1}.xhtml"
        page = add_page(ch_html, ch.get("title", f"Chapter {ci+1}"), ch_file)
        spine.append(page)
        toc.append(epub.Link(ch_file, ch.get("title", f"Chapter {ci+1}"), f"ch{ci+1}"))

    # Conclusion
    conclusion = structure.get("conclusion", {})
    if conclusion:
        conc_html = env.get_template("conclusion.html").render(
            title=conclusion.get("title", "Conclusion"),
            content=conclusion.get("content", ""),
        )
        page = add_page(conc_html, "Conclusion", "conclusion.xhtml")
        spine.append(page)
        toc.append(epub.Link("conclusion.xhtml", "Conclusion", "conclusion"))

    # Author Bio
    if ctx["author_bio"]:
        bio_html = env.get_template("author.html").render(bio=ctx["author_bio"])
        page = add_page(bio_html, "About the Author", "author.xhtml")
        spine.append(page)
        toc.append(epub.Link("author.xhtml", "About the Author", "author"))

    # References
    if ctx["references"]:
        ref_html = env.get_template("references.html").render(
            title="References & Further Reading", items=ctx["references"], content="",
        )
        page = add_page(ref_html, "References", "references.xhtml")
        spine.append(page)
        toc.append(epub.Link("references.xhtml", "References", "references"))

    # Glossary
    if ctx["glossary_terms"]:
        gl_html = env.get_template("glossary.html").render(terms=ctx["glossary_terms"])
        page = add_page(gl_html, "Glossary", "glossary.xhtml")
        spine.append(page)
        toc.append(epub.Link("glossary.xhtml", "Glossary", "glossary"))

    # Back Cover
    if ctx["back_cover_blurb"]:
        bc_html = env.get_template("back_cover.html").render(
            blurb=ctx["back_cover_blurb"],
            author=structure.get("author", "AI Design Engine"),
            tagline=ctx["back_cover_tagline"] or "AI-Powered Publishing",
            icon="📖",
        )
        page = add_page(bc_html, "Back Cover", "backcover.xhtml")
        spine.append(page)
        toc.append(epub.Link("backcover.xhtml", "Back Cover", "backcover"))

    book.toc = toc
    book.spine = spine
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub.write_epub(output_path, book, {})
    return output_path


def build_docx(structure: dict, style: str, infographics: list, output_path: str,
               introduction="", author_bio="",
               references=None, glossary_terms=None,
               back_cover_blurb="", back_cover_tagline="",
               cover_svg="", cover_image="",
               chapter_illustrations=None) -> str:
    ctx = _build_common(structure, style, infographics,
                        introduction, author_bio, references, glossary_terms,
                        back_cover_blurb, back_cover_tagline,
                        cover_svg, cover_image, chapter_illustrations)
    colors = ctx["colors"]
    fonts = ctx["fonts"]

    doc = Document()

    heading_font = fonts["heading"].split(",")[0].strip().strip("'").strip('"')
    body_font = fonts["body"].split(",")[0].strip().strip("'").strip('"')

    h1_color = _hex_to_rgb(colors["heading"])
    accent_color = _hex_to_rgb(colors["accent"])
    text_color = _hex_to_rgb(colors["text"])
    muted_color = _hex_to_rgb(colors["muted"])

    normal = doc.styles['Normal']
    normal.font.name = body_font
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = RGBColor(*text_color)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.5

    for level in range(1, 4):
        h_style = doc.styles[f'Heading {level}']
        h_font = h_style.font
        h_font.name = heading_font
        if level == 1:
            h_font.size = Pt(22)
            h_font.color.rgb = RGBColor(*h1_color)
        elif level == 2:
            h_font.size = Pt(16)
            h_font.color.rgb = RGBColor(*accent_color)
        else:
            h_font.size = Pt(13)
            h_font.color.rgb = RGBColor(*accent_color)
        h_style.paragraph_format.space_before = Pt(12)

    # Title / Cover page
    title = structure.get("title", "Ebook")
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = t.add_run(title)
    run.font.size = Pt(28)
    run.font.bold = True
    run.font.color.rgb = RGBColor(*h1_color)
    run.font.name = heading_font

    if structure.get("subtitle"):
        p = doc.add_paragraph(structure["subtitle"])
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for r in p.runs:
            r.font.size = Pt(14)
            r.font.color.rgb = RGBColor(*muted_color)

    if structure.get("author"):
        p = doc.add_paragraph(structure["author"])
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for r in p.runs:
            r.font.size = Pt(12)
            r.font.color.rgb = RGBColor(*accent_color)

    if structure.get("summary"):
        doc.add_paragraph()
        p = doc.add_paragraph(structure["summary"])
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for r in p.runs:
            r.font.italic = True
            r.font.color.rgb = RGBColor(*muted_color)

    doc.add_page_break()

    # Introduction
    if ctx["introduction"]:
        doc.add_heading("Introduction", level=1)
        for para in ctx["introduction"].split('\n\n'):
            if para.strip():
                doc.add_paragraph(para.strip())
        doc.add_page_break()

    # TOC
    chapters = structure.get("chapters", [])
    doc.add_heading("Table of Contents", level=1)
    for ci, ch in enumerate(chapters):
        p = doc.add_paragraph(f"Chapter {ci+1}: {ch.get('title', f'Chapter {ci+1}')}")
        for r in p.runs:
            r.font.color.rgb = RGBColor(*accent_color)

    doc.add_page_break()

    # Chapters
    for ci, ch in enumerate(chapters):
        doc.add_heading(ch.get("title", f"Chapter {ci+1}"), level=1)

        # Chapter illustration
        ch_ill = ctx["ch_ills"].get(ci, "")
        if ch_ill:
            try:
                img_path = f"/tmp/ch_ill_{ci}.png"
                if _svg_to_png(ch_ill, img_path):
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p.add_run().add_picture(img_path, width=Inches(5.5))
                    os.remove(img_path)
            except Exception:
                pass

        if ch.get("introduction"):
            p = doc.add_paragraph(ch["introduction"])
            for r in p.runs:
                r.font.italic = True
                r.font.color.rgb = RGBColor(*muted_color)

        for si, sec in enumerate(ch.get("sections", [])):
            if sec.get("heading"):
                doc.add_heading(sec["heading"], level=2)
            content = sec.get("content", "")
            for para in content.split('\n\n'):
                if para.strip():
                    doc.add_paragraph(para.strip())

            key = f"{ci}_{si}"
            if key in ctx["rendered"]:
                for ig in ctx["rendered"][key]:
                    doc.add_heading(ig["title"], level=3)
                    try:
                        img_path = f"/tmp/ig_{ci}_{si}.png"
                        if _svg_to_png(ig["svg"], img_path):
                            p = doc.add_paragraph()
                            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                            p.add_run().add_picture(img_path, width=Inches(5.5))
                            os.remove(img_path)
                    except Exception:
                        doc.add_paragraph("[Infographic - see PDF version]")

        if ch.get("key_takeaway"):
            p = doc.add_paragraph()
            r = p.add_run("KEY TAKEAWAY: ")
            r.bold = True
            r.font.color.rgb = RGBColor(*accent_color)
            r2 = p.add_run(ch["key_takeaway"])
            r2.font.italic = True

        if ch.get("chapter_summary"):
            s = ch["chapter_summary"]
            doc.add_heading(s.get("title", "Chapter Summary"), level=2)
            for point in s.get("points", []):
                doc.add_paragraph(point, style='List Bullet')

        if ch.get("faq"):
            doc.add_heading("Frequently Asked Questions", level=2)
            for faq_item in ch["faq"]:
                p = doc.add_paragraph()
                r = p.add_run(f"Q: {faq_item.get('question', '')}")
                r.bold = True
                r.font.color.rgb = RGBColor(*accent_color)
                doc.add_paragraph(f"A: {faq_item.get('answer', '')}")

        if ch.get("checklist"):
            c = ch["checklist"]
            doc.add_heading(c.get("title", "Action Checklist"), level=2)
            for item in c.get("items", []):
                doc.add_paragraph(item.get("text", ""), style='List Bullet')

        doc.add_page_break()

    # Conclusion
    conclusion = structure.get("conclusion", {})
    if conclusion:
        doc.add_heading(conclusion.get("title", "Conclusion"), level=1)
        doc.add_paragraph(conclusion.get("content", ""))
        doc.add_page_break()

    # Author Bio
    if ctx["author_bio"]:
        doc.add_heading("About the Author", level=1)
        doc.add_paragraph(ctx["author_bio"])
        doc.add_page_break()

    # References
    if ctx["references"]:
        doc.add_heading("References & Further Reading", level=1)
        for ref in ctx["references"]:
            if isinstance(ref, dict):
                text = ref.get("text") or ref.get("title", "")
                url = ref.get("url", "")
                if url:
                    p = doc.add_paragraph(f"{text} — {url}")
                else:
                    doc.add_paragraph(text)
            else:
                doc.add_paragraph(str(ref))

    # Glossary
    if ctx["glossary_terms"]:
        doc.add_heading("Glossary", level=1)
        for term in ctx["glossary_terms"]:
            if isinstance(term, dict):
                p = doc.add_paragraph()
                r = p.add_run(f"{term.get('term', '')}: ")
                r.bold = True
                r.font.color.rgb = RGBColor(*accent_color)
                p.add_run(term.get('definition', ''))
            else:
                doc.add_paragraph(str(term))

    # Back Cover
    if ctx["back_cover_blurb"]:
        doc.add_page_break()
        p = doc.add_paragraph(ctx["back_cover_blurb"])
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for r in p.runs:
            r.font.italic = True
            r.font.color.rgb = RGBColor(*muted_color)
        if ctx["back_cover_tagline"]:
            p = doc.add_paragraph(ctx["back_cover_tagline"])
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:
                r.font.size = Pt(14)
                r.font.color.rgb = RGBColor(*accent_color)

    doc.save(output_path)
    return output_path


def export_mobi(html_content: str, output_path: str, title: str = "Ebook", author: str = "AI Design Engine") -> str:
    """Export to MOBI via Calibre's ebook-convert (must be installed)."""
    import tempfile
    epub_path = output_path.replace(".mobi", ".epub")
    export_epub(html_content, epub_path, title, author)
    mobi_path = output_path
    try:
        import subprocess
        result = subprocess.run(
            ["ebook-convert", epub_path, mobi_path],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ebook-convert failed: {result.stderr[:200]}")
        return mobi_path
    except FileNotFoundError:
        raise RuntimeError("Calibre not installed. Install it via: apt install calibre")
    except Exception as e:
        raise RuntimeError(f"MOBI conversion failed: {e}")


def generate_kdp_package(html_content: str, output_dir: str, title: str = "Ebook",
                          author: str = "AI Design Engine", trim_size: str = "6x9") -> dict:
    """Generate KDP-ready package: print PDF + EPUB + metadata."""
    import json
    from backend.core.pdf import html_to_print_pdf, TRIM_SIZES
    os.makedirs(output_dir, exist_ok=True)
    print_pdf = os.path.join(output_dir, f"{title}_print_{trim_size}.pdf")
    epub_file = os.path.join(output_dir, f"{title}.epub")

    # Generate print PDF
    try:
        html_to_print_pdf(html_content, print_pdf, trim_size)
    except Exception as e:
        print_pdf = None

    # Generate EPUB
    try:
        export_epub(html_content, epub_file, title, author)
    except Exception as e:
        epub_file = None

    # Generate KDP metadata file
    ts = TRIM_SIZES.get(trim_size, TRIM_SIZES["6x9"])
    metadata = {
        "title": title,
        "author": author,
        "trim_size": trim_size,
        "trim_width_mm": ts["width"],
        "trim_height_mm": ts["height"],
        "bleed": "0.125in" if ts["width"] >= 6 else "no_bleed",
        "interior_type": "black_and_white",
        "paper_color": "cream",
        "cover_finish": "matte",
        "kdp_categories": ["Computers / Artificial Intelligence"],
        "kdp_keywords": ["AI", "ebook", "artificial intelligence"],
    }
    meta_path = os.path.join(output_dir, "kdp_metadata.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    return {
        "print_pdf": print_pdf,
        "epub": epub_file,
        "metadata": meta_path,
        "trim_size": trim_size,
    }
