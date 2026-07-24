import os
import asyncio
from playwright.async_api import async_playwright

TRIM_SIZES = {
    "6x9": {"width": 6, "height": 9, "label": "6\" x 9\""},
    "5.5x8.5": {"width": 5.5, "height": 8.5, "label": "5.5\" x 8.5\""},
    "5.25x8": {"width": 5.25, "height": 8, "label": "5.25\" x 8\""},
    "8x10": {"width": 8, "height": 10, "label": "8\" x 10\""},
    "8.5x11": {"width": 8.5, "height": 11, "label": "8.5\" x 11\""},
}
BLEED = 0.125  # inches


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
    asyncio.run(_generate(html, output_path))


def _in_to_pt(inches: float) -> float:
    return inches * 72


def _in_to_px(inches: float, dpi: int = 96) -> int:
    return int(inches * dpi)


def wrap_print_html(html: str, trim_size: str = "6x9", isbn: str = "",
                    include_marks: bool = True, include_bleed: bool = True) -> str:
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

    isbn_html = ""
    if isbn:
        isbn_html = f"""
        <div style="page-break-before:always;display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;padding:40px">
            <div style="border:2px solid #000;padding:20px 40px;margin-bottom:20px;text-align:center">
                <div style="font-size:10px;letter-spacing:2px;text-transform:uppercase;margin-bottom:8px">ISBN</div>
                <div style="font-size:18px;font-weight:bold;font-family:monospace;letter-spacing:1px">{isbn}</div>
                <div style="margin-top:12px;display:flex;justify-content:center;gap:4px">
                    {'<div style="width:2px;height:30px;background:#000"></div>' * 8}
                </div>
            </div>
            <div style="font-size:9px;color:#666;text-align:center">9 780000 000000 ></div>
        </div>"""

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
                          isbn: str = "", include_marks: bool = True):
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
                      isbn: str = "", include_marks: bool = True):
    asyncio.run(_generate_print(html, output_path, trim_size, isbn, include_marks))
