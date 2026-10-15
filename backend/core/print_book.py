"""Print-ready book interior: typeset from the saved book, with every chapter
opening on a right-hand (odd) page, as in professionally typeset books.

Chromium ignores `break-before: right`, so recto openings take two passes:
render once with tiny invisible per-chapter markers, read back which page
each chapter starts on, then render again with a blank page in front of each
chapter that landed on a left-hand page (and without the markers).
"""
import io
import re

import pypdf

from backend.core.builder import build_ebook_html
from backend.core.pdf import TRIM_SIZES, html_to_book_pdf

# Matched against the page text with all whitespace removed: how extraction
# spaces out tiny glyphs differs between Chromium versions.
_MARKER = re.compile(r"§CH(\d+)§")


def chapter_start_pages(pdf_bytes: bytes) -> dict[int, int]:
    """{chapter index: 1-based page number} from the pass-one markers."""
    starts: dict[int, int] = {}
    for number, page in enumerate(pypdf.PdfReader(io.BytesIO(pdf_bytes)).pages, start=1):
        for m in _MARKER.finditer(re.sub(r"\s+", "", page.extract_text() or "")):
            starts.setdefault(int(m.group(1)), number)
    return starts


def recto_blanks(starts: dict[int, int]) -> set[int]:
    """Chapters that need a blank page before them. Each inserted blank
    shifts every later chapter by one page, so parity is tracked as we go."""
    blanks, shift = set(), 0
    for ci in sorted(starts):
        if (starts[ci] + shift) % 2 == 0:
            blanks.add(ci)
            shift += 1
    return blanks


def build_print_pdf(book: dict, style: str, infographics: list, trim_size: str,
                    output_path: str, isbn: str = "", **build_kwargs) -> None:
    trim = TRIM_SIZES[trim_size]
    first = build_ebook_html(book, style, infographics, print_trim=trim, isbn=isbn,
                             page_markers=True, **build_kwargs)
    html_to_book_pdf(first, output_path)
    with open(output_path, "rb") as f:
        blanks = recto_blanks(chapter_start_pages(f.read()))
    final = build_ebook_html(book, style, infographics, print_trim=trim, isbn=isbn,
                             recto_blanks=blanks, **build_kwargs)
    html_to_book_pdf(final, output_path)
