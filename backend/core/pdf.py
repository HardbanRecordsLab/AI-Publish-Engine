import asyncio
import os

from playwright.async_api import async_playwright

TRIM_SIZES = {
    "6x9": {"width": 6, "height": 9, "label": "6\" x 9\""},
    "5.5x8.5": {"width": 5.5, "height": 8.5, "label": "5.5\" x 8.5\""},
    "5.25x8": {"width": 5.25, "height": 8, "label": "5.25\" x 8\""},
    "8x10": {"width": 8, "height": 10, "label": "8\" x 10\""},
    "8.5x11": {"width": 8.5, "height": 11, "label": "8.5\" x 11\""},
}
BLEED = 0.125  # inches

# Print-interior margins (inches). KDP's minimum gutter is 0.375" up to 150
# pages and 0.5"+ beyond, outside margins at least 0.25"; these sit
# comfortably above both, in the range trade paperbacks actually use.
PRINT_MARGINS = {"top": 0.75, "bottom": 0.8, "inside": 0.875, "outside": 0.6}


def normalize_isbn(isbn: str) -> str:
    """Return the ISBN as printed on a copyright page ("978-…" kept as given,
    minus spaces), or raise ValueError if its check digit is wrong."""
    raw = (isbn or "").strip()
    digits = raw.replace("-", "").replace(" ", "").upper()
    if len(digits) == 13 and digits.isdigit():
        total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits[:12]))
        if (10 - total % 10) % 10 != int(digits[12]):
            raise ValueError("ISBN-13 check digit is wrong")
    elif len(digits) == 10 and digits[:9].isdigit() and (digits[9].isdigit() or digits[9] == "X"):
        total = sum((10 - i) * int(d) for i, d in enumerate(digits[:9]))
        check = (11 - total % 11) % 11
        if ("X" if check == 10 else str(check)) != digits[9]:
            raise ValueError("ISBN-10 check digit is wrong")
    else:
        raise ValueError("ISBN must have 10 or 13 digits")
    return raw.replace(" ", "")


async def _generate(html: str, output_path: str):
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(html, wait_until="networkidle")
        await page.pdf(path=output_path, format="A4", print_background=True, margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        await browser.close()


def html_to_pdf(html: str, output_path: str):
    """Sync entry point — only safe to call when no event loop is already
    running in the current thread (e.g. from a sync FastAPI route, which
    FastAPI dispatches to a worker thread). From async code, await
    html_to_pdf_async() directly instead — asyncio.run() cannot be nested
    inside an already-running loop (this broke PDF generation in production
    for every job from 2026-07-05 until this fix, since worker.py's
    process_job() is async and called this from inside its own event loop)."""
    asyncio.run(_generate(html, output_path))


async def html_to_pdf_async(html: str, output_path: str):
    await _generate(html, output_path)


async def _generate_book(html: str, output_path: str):
    """PDF whose page size and margins come from the document's own @page
    rules (trim size, mirrored margins, running heads)."""
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(html, wait_until="networkidle")
        await page.pdf(path=output_path, print_background=True, prefer_css_page_size=True)
        await browser.close()


def html_to_book_pdf(html: str, output_path: str):
    """Sync entry point (see html_to_pdf() on event loops)."""
    asyncio.run(_generate_book(html, output_path))


def _in_to_pt(inches: float) -> float:
    return inches * 72


def _in_to_px(inches: float, dpi: int = 96) -> int:
    return int(inches * dpi)


def wrap_print_html(html: str, trim_size: str = "6x9", isbn: str = "",
                    include_marks: bool = False, include_bleed: bool = True) -> str:
    """Wrap content HTML in a print-ready layout with bleeds and crop marks."""
    sz = TRIM_SIZES.get(trim_size, TRIM_SIZES["6x9"])
    tw, th = sz["width"], sz["height"]
    total_w = tw + (BLEED * 2 if include_bleed else 0)
    total_h = th + (BLEED * 2 if include_bleed else 0)

    marks_css = ""
    if include_marks:
        marks_css = f"""
        @page {{
            size: {total_w}in {total_h}in;
            margin: {BLEED}in;
            marks: crop cross;
            bleed: {BLEED}in;
        }}
        """

    # Legacy path (jobs saved without book data). No fake barcode: KDP and
    # printers place the real one on the cover; the interior only states it.
    isbn_html = f'<p style="text-align:center;font-size:9pt">ISBN {isbn}</p>' if isbn else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
    @page {{
        size: {total_w}in {total_h}in;
        margin: {BLEED}in;
        {f'marks: crop cross; bleed: {BLEED}in;' if include_marks else ''}
    }}
    @page :first {{ margin-top: 0; }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    html {{ background: white; }}
    body {{
        width: {tw}in;
        min-height: {th}in;
        margin: 0 auto;
        font-family: 'Georgia', 'Times New Roman', serif;
        color: #333;
        line-height: 1.6;
        font-size: 11pt;
        position: relative;
        background: white;
        padding: 0;
    }}
    /* Bleed guide (safe area) */
    .safe-area {{
        position: absolute;
        top: {BLEED}in;
        left: {BLEED}in;
        right: {BLEED}in;
        bottom: {BLEED}in;
        border: 1px dashed #ccc;
        pointer-events: none;
        z-index: 9999;
    }}
    img {{ max-width: 100%; height: auto; }}
    h1 {{ font-size: 18pt; margin-bottom: 12pt; page-break-before: always; }}
    h1:first-of-type {{ page-break-before: avoid; }}
    h2 {{ font-size: 14pt; margin-bottom: 8pt; margin-top: 16pt; }}
    p {{ margin-bottom: 8pt; text-align: justify; }}
    table {{ width: 100%; border-collapse: collapse; margin: 12pt 0; font-size: 9pt; }}
    th, td {{ border: 1px solid #999; padding: 4pt 6pt; text-align: left; }}
    /* Page numbers */
    @page {{
        @bottom-center {{
            content: counter(page);
            font-size: 9pt;
            color: #666;
            font-family: 'Georgia', serif;
        }}
    }}
    @page :first {{
        @bottom-center {{ content: none; }}
    }}
    /* Keep lines together */
    p {{ orphans: 2; widows: 2; }}
    {marks_css}
    .cover-page {{ height: {th}in; display: flex; flex-direction: column; justify-content: center; align-items: center; page-break-after: always; }}
    .cover-page h1 {{ font-size: 24pt; text-align: center; }}
    .cover-page .subtitle {{ font-size: 14pt; text-align: center; color: #666; }}
    .cover-page .author {{ font-size: 12pt; text-align: center; margin-top: 24pt; }}
    .section-break {{ page-break-before: always; }}
    .print-only {{ display: block; }}
    .screen-only {{ display: none; }}
</style>
</head>
<body>
    {'<div class="safe-area"></div>' if include_marks else ''}
    {html}
    {isbn_html}
</body>
</html>"""


async def _generate_print(html: str, output_path: str, trim_size: str = "6x9",
                          isbn: str = "", include_marks: bool = False):
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    wrapped = wrap_print_html(html, trim_size, isbn, include_marks)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(wrapped, wait_until="networkidle")
        await page.pdf(path=output_path, format=None, print_background=True,
                       width=f"{TRIM_SIZES[trim_size]['width'] + BLEED * 2}in",
                       height=f"{TRIM_SIZES[trim_size]['height'] + BLEED * 2}in",
                       margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        await browser.close()


def html_to_print_pdf(html: str, output_path: str, trim_size: str = "6x9",
                      isbn: str = "", include_marks: bool = False):
    """Sync entry point — see html_to_pdf()'s docstring: safe only outside
    a running event loop. From async code, await html_to_print_pdf_async()."""
    asyncio.run(_generate_print(html, output_path, trim_size, isbn, include_marks))


async def html_to_print_pdf_async(html: str, output_path: str, trim_size: str = "6x9",
                                   isbn: str = "", include_marks: bool = False):
    await _generate_print(html, output_path, trim_size, isbn, include_marks)
