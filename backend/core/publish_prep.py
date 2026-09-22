"""Per-platform publish packaging — ported from Kiro eBook Studio (platforms/*.js).

Each `prepare_*` function copies the source EPUB/PDF into a platform-specific
output folder, resizes the cover to that store's required dimensions, writes
a metadata JSON file, and runs the matching validator from
`backend.core.publish_validators`.

Amazon KDP already has an equivalent (print PDF + EPUB + metadata) in
`backend.core.export.generate_kdp_package` — `prepare_kdp` below additionally
handles cover resizing/validation, which that function does not.
"""
import json
import os
import re
import shutil

from backend.core.publish_validators import validate_apple_books, validate_kdp

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

# platform -> (width, height, jpeg_quality)
COVER_SPECS = {
    "amazon-kdp": (1600, 2400, 95),
    "apple-books": (3000, 4000, 95),
    "kobo": (1400, 2100, 90),
    "google-play": (600, 800, 90),
}


def _safe_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "_", (title or "book").lower())


def _resize_cover(src_path: str, dest_path: str, size: tuple) -> bool:
    """Resize+crop to fill target (width, height) — Pillow equivalent of sharp's fit:'cover'.

    `size` is (width, height, jpeg_quality); only the first two go to ImageOps.fit.
    """
    if not _PIL_AVAILABLE:
        return False
    width, height, quality = size
    try:
        from PIL import ImageOps
        with Image.open(src_path) as img:
            rgb_img = img.convert("RGB")
            fitted = ImageOps.fit(rgb_img, (width, height), method=Image.LANCZOS)
            fitted.save(dest_path, "JPEG", quality=quality)
        return True
    except Exception:
        return False


def _prepare_cover(cover_path: str, output_dir: str, safe_title: str, platform_suffix: str, size: tuple) -> str | None:
    if not cover_path or not os.path.exists(cover_path):
        return None
    dest = os.path.join(output_dir, f"{safe_title}_cover_{platform_suffix}.jpg")
    w, h, quality = size
    if _resize_cover(cover_path, dest, (w, h, quality)):
        return dest
    # Fallback: copy original file untouched (mirrors Kiro's sharp-unavailable fallback)
    ext = os.path.splitext(cover_path)[1] or ".jpg"
    fallback_dest = dest.replace(".jpg", ext)
    shutil.copy2(cover_path, fallback_dest)
    return fallback_dest


def _write_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def prepare_kdp(metadata: dict, output_dir: str, epub_path: str = None, pdf_path: str = None, cover_path: str = None) -> dict:
    """Prepare an Amazon KDP upload package (ported from amazon-kdp-prep.js)."""
    os.makedirs(output_dir, exist_ok=True)
    safe_title = _safe_title(metadata.get("title"))
    prepared = {}

    if epub_path and os.path.exists(epub_path):
        dest = os.path.join(output_dir, f"{safe_title}_kdp.epub")
        shutil.copy2(epub_path, dest)
        prepared["epub"] = dest

    if pdf_path and os.path.exists(pdf_path):
        dest = os.path.join(output_dir, f"{safe_title}_kdp.pdf")
        shutil.copy2(pdf_path, dest)
        prepared["pdf"] = dest

    cover_dest = _prepare_cover(cover_path, output_dir, safe_title, "kdp", COVER_SPECS["amazon-kdp"])
    if cover_dest:
        prepared["cover"] = cover_dest

    kdp_metadata = {
        "platform": "Amazon KDP",
        "title": metadata.get("title"),
        "subtitle": metadata.get("subtitle", ""),
        "author": metadata.get("author"),
        "description": metadata.get("description", ""),
        "keywords": (metadata.get("keywords") or [])[:7],
        "category": metadata.get("category", ""),
        "isbn": metadata.get("isbn", ""),
        "language": metadata.get("language", "pl"),
        "publicationDate": metadata.get("publicationDate", ""),
        "publisher": metadata.get("publisher", ""),
        "rights": metadata.get("rights", ""),
        "coverDimensions": "1600x2400px",
        "coverFormat": "JPG",
        "coverDPI": 72,
        "epubVersion": "3.0",
        "requirements": {
            "pdf": "PDF standard, embedded fonts, RGB, 300 DPI min dla druku",
            "epub": "EPUB 3.0, max 650MB, valid TOC",
            "cover": "1600x2400px JPG RGB 72DPI, safe zone 40px",
        },
    }
    _write_json(os.path.join(output_dir, "kdp-metadata.json"), kdp_metadata)

    checklist = {
        "platform": "Amazon KDP",
        "items": [
            {"item": "Tytuł", "status": "OK" if metadata.get("title") else "MISSING", "value": metadata.get("title")},
            {"item": "Autor", "status": "OK" if metadata.get("author") else "MISSING", "value": metadata.get("author")},
            {"item": "Opis (100+ znaków)", "status": "OK" if len(metadata.get("description", "")) >= 100 else "WARNING",
             "value": f"{len(metadata.get('description', ''))} znaków"},
            {"item": "Słowa kluczowe (max 7)", "status": "OK" if len(metadata.get("keywords", [])) <= 7 else "WARNING",
             "value": str(len(metadata.get("keywords", [])))},
            {"item": "Okładka", "status": "OK" if prepared.get("cover") else "MISSING"},
            {"item": "Plik EPUB", "status": "OK" if prepared.get("epub") else "MISSING"},
            {"item": "Plik PDF", "status": "OK" if prepared.get("pdf") else "WARNING (optional)"},
            {"item": "ISBN", "status": "OK" if metadata.get("isbn") else "WARNING (required for print)"},
            {"item": "Język", "status": "OK" if metadata.get("language") else "WARNING", "value": metadata.get("language")},
            {"item": "Kategoria", "status": "OK" if metadata.get("category") else "WARNING", "value": metadata.get("category")},
        ],
    }
    _write_json(os.path.join(output_dir, "kdp-checklist.json"), checklist)

    validation = validate_kdp(metadata, cover_path=prepared.get("cover"), epub_path=prepared.get("epub"), pdf_path=prepared.get("pdf"))
    _write_json(os.path.join(output_dir, "validation-results.json"), validation)

    return {"platform": "amazon-kdp", "outputDir": output_dir, "files": prepared, "metadata": kdp_metadata, "validation": validation, "checklist": checklist}


def prepare_apple_books(metadata: dict, output_dir: str, epub_path: str = None, cover_path: str = None) -> dict:
    """Prepare an Apple Books upload package (ported from apple-books-prep.js)."""
    os.makedirs(output_dir, exist_ok=True)
    safe_title = _safe_title(metadata.get("title"))
    prepared = {}

    if epub_path and os.path.exists(epub_path):
        dest = os.path.join(output_dir, f"{safe_title}_apple.epub")
        shutil.copy2(epub_path, dest)
        prepared["epub"] = dest

    cover_dest = _prepare_cover(cover_path, output_dir, safe_title, "apple", COVER_SPECS["apple-books"])
    if cover_dest:
        prepared["cover"] = cover_dest

    apple_metadata = {
        "platform": "Apple Books",
        "title": metadata.get("title"),
        "author": metadata.get("author"),
        "isbn": metadata.get("isbn") or "REQUIRED",
        "language": metadata.get("language", "pl"),
        "publicationDate": metadata.get("publicationDate") or "REQUIRED",
        "description": metadata.get("description", ""),
        "category": metadata.get("category", ""),
        "coverDimensions": "3000x4000px minimum",
        "coverFormat": "JPG/PNG sRGB",
        "epubVersion": "3.0 strict",
    }
    _write_json(os.path.join(output_dir, "apple-books-metadata.json"), apple_metadata)

    validation = validate_apple_books(metadata, cover_path=prepared.get("cover"), epub_path=prepared.get("epub"))
    _write_json(os.path.join(output_dir, "validation-results.json"), validation)

    return {"platform": "apple-books", "outputDir": output_dir, "files": prepared, "metadata": apple_metadata, "validation": validation}


def prepare_kobo(metadata: dict, output_dir: str, epub_path: str = None, cover_path: str = None) -> dict:
    """Prepare a Kobo Writing Life upload package (ported from kobo-prep.js)."""
    os.makedirs(output_dir, exist_ok=True)
    safe_title = _safe_title(metadata.get("title"))
    prepared = {}

    if epub_path and os.path.exists(epub_path):
        dest = os.path.join(output_dir, f"{safe_title}_kobo.epub")
        shutil.copy2(epub_path, dest)
        prepared["epub"] = dest

    cover_dest = _prepare_cover(cover_path, output_dir, safe_title, "kobo", COVER_SPECS["kobo"])
    if cover_dest:
        prepared["cover"] = cover_dest

    kobo_metadata = {
        "platform": "Kobo",
        "title": metadata.get("title"),
        "author": metadata.get("author"),
        "language": metadata.get("language", "pl"),
        "coverDimensions": "1400x2100px minimum",
        "epubVersion": "3.0",
    }
    _write_json(os.path.join(output_dir, "kobo-metadata.json"), kobo_metadata)

    return {"platform": "kobo", "outputDir": output_dir, "files": prepared, "metadata": kobo_metadata}


def prepare_google_play(metadata: dict, output_dir: str, epub_path: str = None, pdf_path: str = None, cover_path: str = None) -> dict:
    """Prepare a Google Play Books upload package (ported from google-play-prep.js)."""
    os.makedirs(output_dir, exist_ok=True)
    safe_title = _safe_title(metadata.get("title"))
    prepared = {}

    if epub_path and os.path.exists(epub_path):
        dest = os.path.join(output_dir, f"{safe_title}_googleplay.epub")
        shutil.copy2(epub_path, dest)
        prepared["epub"] = dest

    if pdf_path and os.path.exists(pdf_path):
        dest = os.path.join(output_dir, f"{safe_title}_googleplay.pdf")
        shutil.copy2(pdf_path, dest)
        prepared["pdf"] = dest

    cover_dest = _prepare_cover(cover_path, output_dir, safe_title, "google", COVER_SPECS["google-play"])
    if cover_dest:
        prepared["cover"] = cover_dest

    gp_metadata = {
        "platform": "Google Play Books",
        "title": metadata.get("title"),
        "author": metadata.get("author"),
        "description": metadata.get("description") or "REQUIRED",
        "isbn": metadata.get("isbn", ""),
        "language": metadata.get("language", "pl"),
        "coverDimensions": "600x800px minimum",
        "pdfResolution": "150 DPI minimum",
    }
    _write_json(os.path.join(output_dir, "google-play-metadata.json"), gp_metadata)

    return {"platform": "google-play", "outputDir": output_dir, "files": prepared, "metadata": gp_metadata}


PREPARERS = {
    "amazon-kdp": prepare_kdp,
    "apple-books": prepare_apple_books,
    "kobo": prepare_kobo,
    "google-play": prepare_google_play,
}
