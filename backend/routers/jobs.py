import asyncio
import os
import threading

from fastapi import APIRouter, File, Form, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from loguru import logger

from backend.config import settings
from backend.core.ai import PROVIDERS
from backend.core.jobs import create_job, get_job
from backend.core.parser import extract_text
from backend.limiter import limiter
from backend.ws_manager import cancel_job, get_progress, manager

router = APIRouter()

VALID_EXTENSIONS = (".txt", ".md", ".docx", ".pdf")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", settings.output_dir)


def _mobi_path(job_id: str) -> str:
    return os.path.join(OUTPUT_DIR, f"{job_id}.mobi")


def _queue_job(job_id: str, text: str, style: str, provider: str = None,
               content_type: str = "ebook", audience: str = "", tone: str = "",
               chapters: str = "", keywords: str = "", language: str = "",
               accent_color: str = "", bg_color: str = "",
               heading_font: str = "", body_font: str = ""):
    """Run a generation job in a background thread.

    Note: this used to try enqueueing to a Redis/arq queue first, but that
    call always failed (asyncio.run() can't be started from inside the
    already-running event loop of a FastAPI request handler) and silently
    fell back to this exact threading path every single time. Removed the
    dead code path — if you outgrow single-VPS threading and need a real
    distributed queue, that's the place to reintroduce Redis/arq properly
    (e.g. via a threadsafe enqueue call scheduled on the main event loop).
    """
    ctx = {
        "job_id": job_id, "text": text, "style": style, "provider": provider,
        "content_type": content_type, "audience": audience, "tone": tone,
        "chapters": chapters, "keywords": keywords, "language": language,
        "accent_color": accent_color, "bg_color": bg_color,
        "heading_font": heading_font, "body_font": body_font,
    }
    from backend.worker import process_job

    def _run():
        asyncio.run(process_job(ctx))

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    logger.info(f"Job {job_id} started in background thread")


@router.post("/api/generate")
@limiter.limit("10/minute")
async def generate(
    request: Request,
    files: list[UploadFile] = File(...),
    style: str = Form("minimal"),
    provider: str = Form(settings.ai_provider),
    content_type: str = Form("ebook"),
    audience: str = Form(""),
    tone: str = Form(""),
    chapters: str = Form(""),
    keywords: str = Form(""),
    language: str = Form(""),
    accent_color: str = Form(""),
    bg_color: str = Form(""),
    heading_font: str = Form(""),
    body_font: str = Form(""),
):
    if not files:
        return JSONResponse({"error": "At least one file is required"}, status_code=400)
    for f in files:
        if not f.filename.lower().endswith(VALID_EXTENSIONS):
            return JSONResponse(
                {"error": f"'{f.filename}' not supported. Valid: {', '.join(VALID_EXTENSIONS)}"},
                status_code=400,
            )
    if provider not in PROVIDERS:
        return JSONResponse(
            {"error": f"Unknown provider. Valid: {', '.join(PROVIDERS.keys())}"},
            status_code=400,
        )
    texts = []
    for f in files:
        content = await f.read()
        text = extract_text(f.filename, content)
        if text.strip():
            texts.append(f"--- {f.filename} ---\n{text}")
    if not texts:
        return JSONResponse({"error": "All files are empty or contain no extractable text"}, status_code=400)
    merged = "\n\n".join(texts)
    job_id = create_job(style, content_type, audience, tone, chapters, keywords, language)
    _queue_job(job_id, merged, style, provider, content_type, audience, tone, chapters, keywords, language, accent_color, bg_color, heading_font, body_font)
    return {"job_id": job_id, "status": "queued", "provider": provider, "content_type": content_type}


@router.post("/api/generate-batch")
@limiter.limit("5/minute")
async def generate_batch(
    request: Request,
    files: list[UploadFile] = File(...),
    style: str = Form("minimal"),
    provider: str = Form(settings.ai_provider),
    content_type: str = Form("ebook"),
    audience: str = Form(""),
    tone: str = Form(""),
    chapters: str = Form(""),
    keywords: str = Form(""),
    language: str = Form(""),
):
    if not files:
        return JSONResponse({"error": "At least one file is required"}, status_code=400)
    job_ids = []
    for f in files:
        if not f.filename.lower().endswith(VALID_EXTENSIONS):
            continue
        content = await f.read()
        text = extract_text(f.filename, content)
        if not text.strip():
            continue
        job_id = create_job(style, content_type, audience, tone, chapters, keywords, language)
        _queue_job(job_id, text, style, provider, content_type, audience, tone, chapters, keywords, language)
        job_ids.append({"job_id": job_id, "filename": f.filename})
    return {"jobs": job_ids, "count": len(job_ids), "status": "queued", "provider": provider}


@router.get("/api/status/{job_id}")
@limiter.limit("120/minute")  # generous on purpose: the frontend polls this every ~5s during generation
def get_status(request: Request, job_id: str):
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "topic": job.get("topic"),
        "content_type": job.get("content_type"),
        "style": job.get("style"),
        "error": job.get("error"),
    }


@router.get("/api/download/{job_id}")
@limiter.limit("30/minute")
def download(request: Request, job_id: str, format: str = Query("pdf", pattern="^(pdf|epub|docx|website|mobi)$")):
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job["status"] != "done":
        return JSONResponse({"error": "Job not ready yet"}, status_code=400)
    paths = {
        "pdf": job.get("output_path"),
        "epub": job.get("epub_path"),
        "docx": job.get("docx_path"),
        "website": job.get("website_path"),
        # MOBI isn't part of the main pipeline (job table has no mobi_path
        # column) — it's generated on demand by POST .../mobi and cached on
        # disk at this conventional path; reuse it here if it already exists.
        "mobi": _mobi_path(job_id) if os.path.exists(_mobi_path(job_id)) else None,
    }
    media_types = {
        "pdf": "application/pdf",
        "epub": "application/epub+zip",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "website": "text/html",
        "mobi": "application/x-mobipocket-ebook",
    }
    ext = {"pdf": "pdf", "epub": "epub", "docx": "docx", "website": "html", "mobi": "mobi"}
    path = paths.get(format)
    if not path or not os.path.exists(path):
        if format == "mobi":
            return JSONResponse({"error": "MOBI not generated yet — call POST /api/download/{job_id}/mobi first"}, status_code=400)
        return JSONResponse({"error": f"{format.upper()} not available"}, status_code=400)
    return FileResponse(
        path,
        media_type=media_types[format],
        filename=f"{job_id}.{ext[format]}",
    )


@router.get("/api/print-sizes")
@limiter.limit("60/minute")
def get_print_sizes(request: Request):
    from backend.core.pdf import TRIM_SIZES
    return [{"id": k, "label": v["label"], "width": v["width"], "height": v["height"]}
            for k, v in TRIM_SIZES.items()]


@router.post("/api/download/{job_id}/print")
@limiter.limit("10/minute")
def download_print(request: Request, job_id: str, trim_size: str = Query("6x9"), isbn: str = Query("")):
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job["status"] != "done":
        return JSONResponse({"error": "Job not ready yet"}, status_code=400)
    from backend.core.pdf import TRIM_SIZES, html_to_print_pdf
    if trim_size not in TRIM_SIZES:
        return JSONResponse({"error": f"Invalid trim size. Valid: {', '.join(TRIM_SIZES.keys())}"}, status_code=400)
    html = job.get("html", "")
    if not html:
        return JSONResponse({"error": "No HTML content available"}, status_code=400)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print_path = os.path.join(OUTPUT_DIR, f"{job_id}_print.pdf")
    try:
        html_to_print_pdf(html, print_path, trim_size, isbn)
    except Exception as e:
        return JSONResponse({"error": f"Print PDF generation failed: {e}"}, status_code=500)
    return FileResponse(print_path, media_type="application/pdf", filename=f"{job_id}_print_{trim_size}.pdf")


@router.post("/api/download/{job_id}/mobi")
@limiter.limit("10/minute")
def download_mobi(request: Request, job_id: str):
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job["status"] != "done":
        return JSONResponse({"error": "Job not ready yet"}, status_code=400)
    epub_path = job.get("epub_path")
    if not epub_path or not os.path.exists(epub_path):
        return JSONResponse({"error": "No EPUB available to convert — generate the ebook first"}, status_code=400)
    from backend.core.export import export_mobi
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    mobi_path = _mobi_path(job_id)
    try:
        export_mobi(epub_path, mobi_path)
    except RuntimeError as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    except Exception as e:
        return JSONResponse({"error": f"MOBI generation failed: {e}"}, status_code=500)
    return FileResponse(mobi_path, media_type="application/x-mobipocket-ebook", filename=f"{job_id}.mobi")


@router.post("/api/download/{job_id}/kdp")
@limiter.limit("10/minute")
def download_kdp_package(request: Request, job_id: str, trim_size: str = Query("6x9")):
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job["status"] != "done":
        return JSONResponse({"error": "Job not ready yet"}, status_code=400)
    html = job.get("html", "")
    if not html:
        return JSONResponse({"error": "No HTML content available"}, status_code=400)
    from backend.core.export import generate_kdp_package
    from backend.core.pdf import TRIM_SIZES
    if trim_size not in TRIM_SIZES:
        return JSONResponse({"error": f"Invalid trim size. Valid: {', '.join(TRIM_SIZES.keys())}"}, status_code=400)
    output_dir = os.path.join(OUTPUT_DIR, f"{job_id}_kdp")
    result = generate_kdp_package(job.get("epub_path"), html, output_dir, title=job.get("topic", "Ebook"), trim_size=trim_size)
    return result


@router.get("/api/preview/{job_id}")
@limiter.limit("60/minute")
def preview(request: Request, job_id: str):
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job["status"] != "done":
        return JSONResponse({"error": "Job not ready yet"}, status_code=400)
    return HTMLResponse(content=job.get("html", ""), media_type="text/html")


@router.get("/api/reader/{job_id}")
@limiter.limit("60/minute")
def reader(request: Request, job_id: str):
    """Dedicated reader page for interactive books with full-screen immersive mode."""
    from datetime import datetime
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job["status"] != "done":
        return JSONResponse({"error": "Job not ready"}, status_code=400)
    topic = job.get("topic", "Book")
    html = job.get("html", "")
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{topic} — Reader</title>
<meta name="description" content="Interactive book: {topic}">
<meta property="og:title" content="{topic}">
<meta property="og:type" content="book">
<meta name="twitter:card" content="summary_large_image">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#f5f5f5;font-family:-apple-system,system-ui,sans-serif}}
.reader-header{{background:#fff;border-bottom:1px solid #e0e0e0;padding:12px 24px;display:flex;align-items:center;gap:12px;position:sticky;top:0;z-index:100}}
.reader-header h1{{font-size:16px;font-weight:600;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.reader-btn{{padding:6px 16px;border-radius:6px;border:1px solid #d0d0d0;background:#fff;cursor:pointer;font-size:13px;text-decoration:none;color:#333}}
.reader-btn:hover{{background:#f0f0f0}}
.reader-frame{{max-width:820px;margin:0 auto;background:#fff;min-height:100vh;box-shadow:0 2px 20px rgba(0,0,0,.08)}}
.reader-footer{{text-align:center;padding:20px;font-size:12px;color:#999}}
@media(max-width:768px){{.reader-header{{padding:10px 12px}}.reader-frame{{max-width:100%}}}}
</style>
</head>
<body>
<div class="reader-header">
  <a href="/api/download/{job_id}?format=website" class="reader-btn" download>Download</a>
  <h1>{topic}</h1>
  <button class="reader-btn" onclick="navigator.clipboard.writeText(location.href);this.textContent='Copied!';setTimeout(()=>this.textContent='Share',1500)">Share</button>
  <button class="reader-btn" onclick="document.querySelector('.reader-frame').requestFullscreen()">Fullscreen</button>
</div>
<div class="reader-frame">{html}</div>
<div class="reader-footer">Generated by AI Design Engine — {datetime.now().strftime("%Y")}</div>
</body>
</html>""")


@router.post("/api/cancel/{job_id}")
@limiter.limit("30/minute")
def cancel(request: Request, job_id: str):
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job["status"] in ("done", "failed", "cancelled"):
        return JSONResponse({"error": f"Job already {job['status']}"}, status_code=400)
    cancel_job(job_id)
    return {"status": "cancelling"}


@router.websocket("/ws/progress/{job_id}")
async def ws_progress(websocket: WebSocket, job_id: str):
    await manager.connect(job_id, websocket)
    try:
        # Send current progress immediately if available
        current = get_progress(job_id)
        if current:
            await websocket.send_json(current)
        # Keep connection open for future updates
        while True:
            await websocket.receive_text()  # keepalive pings
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(job_id, websocket)
