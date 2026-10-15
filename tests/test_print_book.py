"""Print-ready interior: ISBN validation, recto chapter openings, hyphenation
and the print-mode HTML (trim size, mirrored margins, no covers)."""
import re

import pypdf
import pytest

from backend.core.builder import build_ebook_html, hyphenate
from backend.core.pdf import TRIM_SIZES, normalize_isbn
from backend.core.print_book import build_print_pdf, chapter_start_pages, recto_blanks

PARA = ("Budżet domowy zaczyna się od świadomości, dokąd naprawdę płyną pieniądze. "
        "Zanim cokolwiek zmienisz, przez miesiąc zapisuj każdy wydatek. ") * 6
BOOK = {
    "title": "Budżet domowy", "subtitle": "Przewodnik", "author": "Jan Kowalski", "language": "Polish",
    "chapters": [{"title": f"Rozdział {i + 1}", "sections": [
        {"heading": "Sekcja", "content": "\n\n".join([PARA] * (2 + i))}]} for i in range(4)],
    "conclusion": {"content": PARA},
}


class TestIsbn:
    @pytest.mark.parametrize("isbn", ["978-83-01-00000-4", "9788301000004", "0-306-40615-2", "080442957X"])
    def test_valid(self, isbn):
        assert normalize_isbn(isbn)

    @pytest.mark.parametrize("isbn", ["978-83-01-00000-2", "12345", "abcdefghij", "0-306-40615-3"])
    def test_invalid(self, isbn):
        with pytest.raises(ValueError):
            normalize_isbn(isbn)


class TestRectoBlanks:
    def test_parity_is_tracked_across_insertions(self):
        # ch0 on 5 (ok), ch1 on 8 (needs blank -> 9), ch2 on 11 (+1 -> 12, needs blank -> 13)
        assert recto_blanks({0: 5, 1: 8, 2: 11}) == {1, 2}
        assert recto_blanks({0: 3, 1: 5}) == set()
        assert recto_blanks({}) == set()


class TestHyphenate:
    def test_polish_soft_hyphens(self):
        assert hyphenate("świadomości", "pl") == "świa­do­mo­ści"
        assert hyphenate("krótki dom", "pl") == "krótki dom"

    def test_unknown_language_unchanged(self):
        assert hyphenate("świadomości", "xx") == "świadomości"


class TestPrintHtml:
    def test_print_mode(self):
        html = build_ebook_html(BOOK, "dark", [], back_cover_blurb="Blurb", isbn="978-83-01-00000-4",
                                print_trim=TRIM_SIZES["6x9"])
        assert "size: 6in 9in" in html
        assert "@page :left" in html and "@page :right" in html
        assert 'class="title-page page"' in html
        assert 'class="cover' not in html and "back-cover" not in html.split("<body>")[1]
        assert "ISBN 978-83-01-00000-4" in html
        assert "--color-bg: #ffffff" in html
        assert "­" in html  # hyphenated

    def test_screen_mode_unchanged(self):
        html = build_ebook_html(BOOK, "minimal", [], back_cover_blurb="Blurb")
        assert "@page :left" not in html and "title-page" not in html and "­" not in html


class TestPrintPdf:
    def test_chapters_open_on_odd_pages(self, tmp_path):
        path = str(tmp_path / "print.pdf")
        build_print_pdf(BOOK, "minimal", [], "6x9", path, isbn="978-83-01-00000-4", introduction=PARA)
        reader = pypdf.PdfReader(path)
        assert float(reader.pages[0].mediabox.width) == 432 and float(reader.pages[0].mediabox.height) == 648
        openings = [n for n, p in enumerate(reader.pages, 1) if re.search(r"ROZDZIAŁ \d", p.extract_text())]
        assert len(openings) == 4
        assert all(n % 2 == 1 for n in openings), openings
        text = "".join(p.extract_text() for p in reader.pages)
        assert "§" not in text  # pass-one markers never reach the final file
        with open(path, "rb") as f:
            assert chapter_start_pages(f.read()) == {}
