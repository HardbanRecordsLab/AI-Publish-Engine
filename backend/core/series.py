"""Book Series Manager — CRUD + landing page generation."""
import json
import os
from datetime import datetime

SERIES_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "jobs", "series.json")
_series_cache = {}


def _load():
    global _series_cache
    if os.path.exists(SERIES_FILE):
        try:
            with open(SERIES_FILE) as f:
                _series_cache = json.load(f)
        except Exception:
            _series_cache = {}
    return _series_cache


def _save():
    os.makedirs(os.path.dirname(SERIES_FILE), exist_ok=True)
    with open(SERIES_FILE, "w") as f:
        json.dump(_series_cache, f, indent=2)


def list_series() -> list:
    _load()
    results = []
    for sid, s in _series_cache.items():
        s["id"] = sid
        results.append(s)
    results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return results


def get_series(series_id: str) -> dict | None:
    _load()
    s = _series_cache.get(series_id)
    if s:
        s["id"] = series_id
    return s


def create_series(name: str, description: str = "", author: str = "",
                  genre: str = "") -> dict:
    import uuid
    series_id = str(uuid.uuid4())
    _series_cache[series_id] = {
        "name": name,
        "description": description,
        "author": author,
        "genre": genre,
        "books": [],
        "cover_color": "#6366F1",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    _save()
    result = _series_cache[series_id]
    result["id"] = series_id
    return result


def update_series(series_id: str, data: dict) -> dict | None:
    _load()
    if series_id not in _series_cache:
        return None
    s = _series_cache[series_id]
    for key in ("name", "description", "author", "genre", "cover_color"):
        if key in data:
            s[key] = data[key]
    s["updated_at"] = datetime.now().isoformat()
    _save()
    s["id"] = series_id
    return s


def delete_series(series_id: str) -> bool:
    _load()
    if series_id in _series_cache:
        del _series_cache[series_id]
        _save()
        return True
    return False


def add_book_to_series(series_id: str, job_id: str, title: str = "",
                       volume: int = None) -> dict | None:
    _load()
    if series_id not in _series_cache:
        return None
    s = _series_cache[series_id]
    existing = [b for b in s["books"] if b["job_id"] == job_id]
    if existing:
        return s | {"id": series_id}

    book_entry = {
        "job_id": job_id,
        "title": title or f"Volume {len(s['books']) + 1}",
        "volume": volume or (len(s["books"]) + 1),
        "added_at": datetime.now().isoformat(),
    }
    s["books"].append(book_entry)
    s["updated_at"] = datetime.now().isoformat()
    _save()
    s["id"] = series_id
    return s


def remove_book_from_series(series_id: str, job_id: str) -> dict | None:
    _load()
    if series_id not in _series_cache:
        return None
    s = _series_cache[series_id]
    s["books"] = [b for b in s["books"] if b["job_id"] != job_id]
    s["updated_at"] = datetime.now().isoformat()
    _save()
    s["id"] = series_id
    return s


def generate_series_landing(series_id: str) -> str:
    s = get_series(series_id)
    if not s:
        return "<h1>Series not found</h1>"
    books_html = ""
    for b in s.get("books", []):
        books_html += f"""
        <div class="book-card">
            <div class="book-vol">Volume {b.get('volume', '?')}</div>
            <h3>{b['title']}</h3>
            <div class="book-links">
                <a href="/api/preview/{b['job_id']}" class="btn">Read</a>
                <a href="/api/download/{b['job_id']}?format=pdf" class="btn">PDF</a>
                <a href="/api/download/{b['job_id']}?format=epub" class="btn">EPUB</a>
            </div>
        </div>"""
    if not books_html:
        books_html = '<p style="text-align:center;color:#999">No books in this series yet.</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{s['name']} — Series</title>
<meta property="og:title" content="{s['name']}">
<meta name="twitter:card" content="summary_large_image">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,system-ui,sans-serif;background:#f8f9fa;color:#333;min-height:100vh}}
.hero{{background:linear-gradient(135deg,{s.get('cover_color','#6366F1')},{s.get('cover_color','#6366F1')}aa);color:#fff;padding:60px 24px;text-align:center}}
.hero h1{{font-size:36px;font-weight:800;margin-bottom:8px}}
.hero p{{font-size:16px;opacity:.9;max-width:600px;margin:0 auto}}
.hero .author{{margin-top:12px;font-size:14px;opacity:.8}}
.container{{max-width:900px;margin:0 auto;padding:32px 24px}}
.book-card{{background:#fff;border-radius:12px;padding:24px;margin-bottom:16px;box-shadow:0 2px 12px rgba(0,0,0,.08);display:flex;align-items:center;gap:20px}}
.book-vol{{background:{s.get('cover_color','#6366F1')};color:#fff;border-radius:50%;width:48px;height:48px;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:700;flex-shrink:0}}
.book-card h3{{flex:1;font-size:18px}}
.book-links{{display:flex;gap:8px}}
.book-links .btn{{padding:8px 16px;border-radius:8px;text-decoration:none;font-size:13px;font-weight:600;border:1px solid #ddd;color:#555;transition:all .2s}}
.book-links .btn:hover{{border-color:{s.get('cover_color','#6366F1')};color:{s.get('cover_color','#6366F1')}}}
.series-meta{{text-align:center;padding:24px;color:#999;font-size:13px}}
@media(max-width:600px){{.hero h1{{font-size:28px}}.book-card{{flex-direction:column;text-align:center}}}}
</style>
</head>
<body>
<div class="hero">
    <h1>{s['name']}</h1>
    <p>{s.get('description', '')}</p>
    <div class="author">{s.get('author', '')}</div>
</div>
<div class="container">
    {books_html}
    <div class="series-meta">
        {len(s.get('books', []))} book(s) · {s.get('genre', '')} · Generated by AI Design Engine
    </div>
</div>
</body>
</html>"""
