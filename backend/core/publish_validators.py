"""Platform compliance validators — ported from Kiro eBook Studio (validators/*.js).

Each validator returns a dict with the same shape:
{platform, isValid, score, errors, warnings, requirements/suggestions, checkedAt}
so results can be rendered generically by the frontend.
"""
import os
import re
import zipfile
from datetime import UTC, datetime

MAX_COVER_BYTES = 50 * 1024 * 1024        # 50MB (KDP cover limit)
MAX_EPUB_BYTES = 650 * 1024 * 1024        # 650MB (KDP EPUB limit)
MAX_PDF_BYTES = 2 * 1024 * 1024 * 1024    # 2GB (KDP PDF limit)
MAX_APPLE_COVER_BYTES = 100 * 1024 * 1024  # 100MB (Apple Books cover limit)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _score(errors: list, warnings: list, error_weight: int = 20, warning_weight: int = 5) -> int:
    return max(0, 100 - len(errors) * error_weight - len(warnings) * warning_weight)


def _is_valid_language_code(lang: str) -> bool:
    return bool(re.match(r"^[a-z]{2}(-[A-Z]{2})?$", lang or ""))


def _is_valid_isbn(isbn: str) -> bool:
    cleaned = re.sub(r"[-\s]", "", isbn or "")
    if len(cleaned) == 13:
        return bool(re.match(r"^\d{13}$", cleaned)) and cleaned.startswith("978")
    if len(cleaned) == 10:
        return bool(re.match(r"^\d{9}[\dX]$", cleaned))
    return False


def _is_valid_date(date_str: str) -> bool:
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str or ""):
        return False
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_metadata(metadata: dict) -> dict:
    """Comprehensive book metadata validation (ported from metadata-validator.js)."""
    metadata = metadata or {}
    errors, warnings = [], []

    title = (metadata.get("title") or "").strip()
    if not title:
        errors.append({"code": "M001", "message": "Tytuł jest wymagany", "field": "title"})
    elif len(title) > 200:
        warnings.append({"code": "M002", "message": "Tytuł > 200 znaków (limit KDP)", "field": "title"})

    if not (metadata.get("author") or "").strip():
        errors.append({"code": "M003", "message": "Autor jest wymagany", "field": "author"})

    language = metadata.get("language")
    if not language:
        warnings.append({"code": "M004", "message": "Język powinien być określony (np. pl, en)", "field": "language"})
    elif not _is_valid_language_code(language):
        warnings.append({"code": "M005", "message": f'Kod języka "{language}" może być nieprawidłowy. Użyj BCP 47 (pl, en, de, es)', "field": "language"})

    description = metadata.get("description")
    if not description:
        warnings.append({"code": "M006", "message": "Opis jest zalecany", "field": "description"})
    elif len(description) < 100:
        warnings.append({"code": "M007", "message": "Opis powinien mieć min. 100 znaków", "field": "description"})
    elif len(description) > 4000:
        errors.append({"code": "M008", "message": "Opis przekracza 4000 znaków (limit KDP)", "field": "description"})

    if not metadata.get("category"):
        warnings.append({"code": "M009", "message": "Kategoria jest zalecana", "field": "category"})

    keywords = metadata.get("keywords")
    if keywords is not None:
        if not isinstance(keywords, list):
            errors.append({"code": "M010", "message": "keywords musi być listą", "field": "keywords"})
        elif len(keywords) > 7:
            warnings.append({"code": "M011", "message": f"Za dużo słów kluczowych: {len(keywords)} (max 7 dla KDP)", "field": "keywords"})
    else:
        warnings.append({"code": "M012", "message": "Słowa kluczowe są zalecane", "field": "keywords"})

    isbn = metadata.get("isbn")
    if isbn and not _is_valid_isbn(isbn):
        errors.append({"code": "M013", "message": f"Nieprawidłowy format ISBN: {isbn}", "field": "isbn"})

    pub_date = metadata.get("publicationDate")
    if not pub_date:
        warnings.append({"code": "M014", "message": "Data publikacji jest zalecana", "field": "publicationDate"})
    elif not _is_valid_date(pub_date):
        errors.append({"code": "M015", "message": f"Nieprawidłowy format daty: {pub_date}. Użyj YYYY-MM-DD", "field": "publicationDate"})

    is_valid = len(errors) == 0
    fields = ["title", "author", "description", "language", "category", "keywords", "publicationDate", "isbn", "publisher", "rights"]
    filled = sum(1 for f in fields if metadata.get(f) and (len(metadata[f]) > 0 if isinstance(metadata[f], list) else str(metadata[f]).strip()))
    completeness = round(filled / len(fields) * 100)

    suggestions = []
    if not description or len(description) < 300:
        suggestions.append("Rozbuduj opis do min. 300 znaków dla lepszej konwersji")
    if not keywords:
        suggestions.append("Dodaj 3-7 słów kluczowych dla widoczności w sklepach")
    if not isbn:
        suggestions.append("Rozważ uzyskanie ISBN przez ISBN Agency (wymagany na Apple Books i KDP Print)")
    if not pub_date:
        suggestions.append("Podaj datę publikacji w formacie YYYY-MM-DD")

    return {
        "platform": "metadata",
        "isValid": is_valid,
        "completeness": completeness,
        "score": _score(errors, warnings, error_weight=15),
        "errors": errors,
        "warnings": warnings,
        "suggestions": suggestions,
        "requiredFields": ["title", "author"],
        "recommendedFields": ["description", "language", "category", "keywords", "publicationDate", "isbn"],
        "checkedAt": _now(),
    }


def validate_kdp(metadata: dict = None, cover_path: str = None, epub_path: str = None, pdf_path: str = None) -> dict:
    """Amazon KDP requirements validator (ported from kdp-validator.js)."""
    metadata = metadata or {}
    errors, warnings = [], []

    if metadata:
        title = metadata.get("title")
        if not title:
            errors.append({"code": "KDP001", "message": "Tytuł jest wymagany", "field": "title"})
        elif len(title) > 200:
            warnings.append({"code": "KDP002", "message": "Tytuł przekracza 200 znaków", "field": "title"})

        if not metadata.get("author"):
            errors.append({"code": "KDP003", "message": "Autor jest wymagany", "field": "author"})

        description = metadata.get("description")
        if not description:
            warnings.append({"code": "KDP004", "message": "Opis jest zalecany", "field": "description"})
        elif len(description) > 4000:
            errors.append({"code": "KDP005", "message": "Opis przekracza 4000 znaków", "field": "description"})

        keywords = metadata.get("keywords") or []
        if len(keywords) > 7:
            warnings.append({"code": "KDP006", "message": f"Amazon KDP akceptuje max 7 słów kluczowych. Masz: {len(keywords)}", "field": "keywords"})

    if cover_path:
        if not os.path.exists(cover_path):
            errors.append({"code": "KDP010", "message": f"Plik okładki nie istnieje: {cover_path}", "file": cover_path})
        else:
            if os.path.getsize(cover_path) > MAX_COVER_BYTES:
                errors.append({"code": "KDP011", "message": "Okładka przekracza 50MB", "file": cover_path})
            warnings.append({"code": "KDP012", "message": "Sprawdź ręcznie wymiary okładki: min. 1600x2400px, format JPG, RGB", "file": cover_path})
    else:
        errors.append({"code": "KDP013", "message": "Okładka jest wymagana dla Amazon KDP"})

    if epub_path:
        if not os.path.exists(epub_path):
            errors.append({"code": "KDP020", "message": f"Plik EPUB nie istnieje: {epub_path}"})
        elif os.path.getsize(epub_path) > MAX_EPUB_BYTES:
            size_mb = os.path.getsize(epub_path) / 1024 / 1024
            errors.append({"code": "KDP021", "message": f"EPUB przekracza 650MB limit KDP ({size_mb:.1f}MB)"})

    if pdf_path:
        if not os.path.exists(pdf_path):
            warnings.append({"code": "KDP030", "message": f"Plik PDF nie istnieje: {pdf_path}"})
        elif os.path.getsize(pdf_path) > MAX_PDF_BYTES:
            errors.append({"code": "KDP031", "message": "PDF przekracza limit 2GB dla Amazon KDP"})

    return {
        "platform": "amazon-kdp",
        "isValid": len(errors) == 0,
        "score": _score(errors, warnings),
        "errors": errors,
        "warnings": warnings,
        "requirements": {
            "cover": "1600x2400px JPG RGB 72DPI",
            "epub": "EPUB 3.0, max 650MB",
            "pdf": "PDF/X-1a lub standard, max 2GB, embedded fonts",
            "metadata": "Tytuł, autor, opis, max 7 słów kluczowych",
            "isbn": "Wymagany dla wersji drukowanej",
        },
        "suggestions": [
            "Upewnij się, że okładka jest JPG, RGB, 1600x2400px, 72 DPI",
            "Sprawdź embedded fonts w PDF",
            "EPUB musi przejść walidację epubcheck",
            "ISBN wymagany dla wersji print-on-demand",
        ],
        "checkedAt": _now(),
    }


def validate_apple_books(metadata: dict = None, cover_path: str = None, epub_path: str = None) -> dict:
    """Apple Books requirements validator (ported from apple-books-validator.js)."""
    metadata = metadata or {}
    errors, warnings = [], []

    if metadata:
        if not metadata.get("title"):
            errors.append({"code": "AB001", "message": "Tytuł jest wymagany", "field": "title"})
        if not metadata.get("author"):
            errors.append({"code": "AB002", "message": "Autor jest wymagany", "field": "author"})
        if not metadata.get("isbn"):
            errors.append({"code": "AB003", "message": "ISBN jest wymagany dla Apple Books", "field": "isbn"})
        if not metadata.get("language"):
            errors.append({"code": "AB004", "message": "Język jest wymagany dla Apple Books", "field": "language"})
        if not metadata.get("publicationDate"):
            errors.append({"code": "AB005", "message": "Data publikacji jest wymagana", "field": "publicationDate"})
        if not metadata.get("description"):
            warnings.append({"code": "AB006", "message": "Opis jest zalecany", "field": "description"})

    if cover_path:
        if not os.path.exists(cover_path):
            errors.append({"code": "AB010", "message": f"Plik okładki nie istnieje: {cover_path}"})
        else:
            if os.path.getsize(cover_path) > MAX_APPLE_COVER_BYTES:
                errors.append({"code": "AB013", "message": "Okładka przekracza 100MB"})
            warnings.append({"code": "AB011", "message": "Sprawdź ręcznie: okładka musi mieć min. 3000x4000px, sRGB, JPG/PNG, max 100MB"})
    else:
        errors.append({"code": "AB012", "message": "Okładka jest wymagana dla Apple Books"})

    if epub_path and not os.path.exists(epub_path):
        errors.append({"code": "AB020", "message": f"Plik EPUB nie istnieje: {epub_path}"})

    return {
        "platform": "apple-books",
        "isValid": len(errors) == 0,
        "score": _score(errors, warnings),
        "errors": errors,
        "warnings": warnings,
        "requirements": {
            "epub": "EPUB 3.0 strict, XHTML 1.1",
            "cover": "Min. 3000x4000px, sRGB, JPG/PNG, max 100MB",
            "isbn": "Wymagany (10 lub 13 cyfr)",
            "language": "Wymagany kod BCP 47 (pl, en, etc.)",
            "publicationDate": "Wymagana",
        },
        "checkedAt": _now(),
    }


def validate_epub(epub_path: str, strict: bool = False) -> dict:
    """EPUB 3.0 structure validator — reads directly from the .epub zip archive.

    Improvement over the original Kiro validator (which only validated an
    already-unzipped directory and left the .epub case as a TODO): this
    reads the zip's central directory in-memory, no extraction to disk.
    """
    errors, warnings = [], []

    if not epub_path or not os.path.exists(epub_path):
        return _epub_result(False, [{"code": "E000", "message": f"Plik nie istnieje: {epub_path}"}], [])

    try:
        with zipfile.ZipFile(epub_path) as zf:
            names = zf.namelist()

            if "mimetype" not in names:
                errors.append({"code": "E101", "message": "Brak wymaganego pliku EPUB: mimetype", "file": "mimetype"})
            else:
                content = zf.read("mimetype").decode("utf-8", errors="replace").strip()
                if content != "application/epub+zip":
                    errors.append({"code": "E103", "message": f'Nieprawidłowy mimetype: "{content}". Oczekiwano: "application/epub+zip"'})

            if "META-INF/container.xml" not in names:
                errors.append({"code": "E101", "message": "Brak wymaganego pliku EPUB: META-INF/container.xml", "file": "META-INF/container.xml"})
            else:
                container = zf.read("META-INF/container.xml").decode("utf-8", errors="replace")
                if "content.opf" not in container:
                    errors.append({"code": "E104", "message": "container.xml nie wskazuje na content.opf"})
                if "application/oebps-package+xml" not in container:
                    warnings.append({"code": "W101", "message": "container.xml może nie zawierać poprawnego media-type"})

            opf_name = next((n for n in names if n.endswith(".opf")), None)
            if not opf_name:
                errors.append({"code": "E102", "message": "Brak pliku content.opf"})
            else:
                opf_content = zf.read(opf_name).decode("utf-8", errors="replace")
                for tag in ["<dc:title", "<dc:creator", "<dc:language", "<dc:identifier"]:
                    if tag not in opf_content:
                        errors.append({"code": "E105", "message": f"Brak wymaganego metadanych OPF: {tag}"})
                if 'version="3.0"' not in opf_content:
                    warnings.append({"code": "W102", "message": 'OPF powinien wskazywać EPUB version="3.0"'})
                if 'properties="nav"' not in opf_content:
                    errors.append({"code": "E106", "message": 'Brak pliku nawigacji (nav) z properties="nav" w manifest'})
    except zipfile.BadZipFile:
        errors.append({"code": "E001", "message": f"Plik nie jest poprawnym archiwum ZIP/EPUB: {epub_path}"})

    return _epub_result(len(errors) == 0, errors, warnings)


def _epub_result(is_valid: bool, errors: list, warnings: list) -> dict:
    suggestions = []
    codes = {e["code"] for e in errors}
    if "E106" in codes:
        suggestions.append('Dodaj plik toc.xhtml z atrybutem epub:type="toc"')
    if "E105" in codes:
        suggestions.append("Uzupełnij metadane OPF (tytuł, autor, język)")
    if any(w["code"] == "W102" for w in warnings):
        suggestions.append('Zaktualizuj OPF do EPUB 3.0: xmlns="http://www.idpf.org/2007/opf" version="3.0"')

    return {
        "platform": "epub",
        "isValid": is_valid,
        "score": max(0, 100 - len(errors) * 15 - len(warnings) * 5),
        "errors": errors,
        "warnings": warnings,
        "suggestions": suggestions,
        "checkedAt": _now(),
    }
