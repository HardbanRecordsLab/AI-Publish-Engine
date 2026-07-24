"""Book Launch Countdown page generator — pre-order landing page with timer."""
from datetime import datetime, timedelta


def generate_launch_page(ebook_dict: dict, launch_date: str = None,
                         accent_color: str = "#6366F1", book_job_id: str = "") -> str:
    title = ebook_dict.get("title", "Untitled Book")
    author = ebook_dict.get("author", "AI Design Engine")
    summary = ebook_dict.get("summary", "")
    chapters = ebook_dict.get("chapters", [])
    topic = ebook_dict.get("topic", "general")

    if not launch_date:
        launch_date_obj = datetime.now() + timedelta(days=30)
    else:
        launch_date_obj = datetime.fromisoformat(launch_date)

    launch_ts = int(launch_date_obj.timestamp() * 1000)
    launch_str = launch_date_obj.strftime("%B %d, %Y")

    chapter_count = len(chapters)

    download_links = ""
    if book_job_id:
        download_links = f"""
        <div class="download-links">
            <a href="/api/download/{book_job_id}?format=pdf" class="btn">Download PDF</a>
            <a href="/api/download/{book_job_id}?format=epub" class="btn">Download EPUB</a>
            <a href="/api/preview/{book_job_id}" class="btn btn-outline">Read Online</a>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title} — Launch Page</title>
<meta property="og:title" content="{title} — Coming {launch_str}">
<meta property="og:description" content="{summary[:200]}">
<meta name="twitter:card" content="summary_large_image">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,system-ui,sans-serif;background:#0B0F1A;color:#E8EDF5;min-height:100vh;overflow-x:hidden}}
.hero{{background:linear-gradient(135deg,{accent_color}22,{accent_color}44);padding:80px 24px 60px;text-align:center;position:relative;overflow:hidden}}
.hero::before{{content:'';position:absolute;top:-50%;left:-50%;width:200%;height:200%;background:radial-gradient(circle,{accent_color}11 0%,transparent 60%);animation:pulse 4s ease-in-out infinite}}
@keyframes pulse{{0%,100%{{transform:scale(1)}}50%{{transform:scale(1.05)}}}}
.hero h1{{font-size:42px;font-weight:800;margin-bottom:8px;position:relative}}
.hero .subtitle{{font-size:18px;color:{accent_color};margin-bottom:4px;position:relative}}
.hero .author{{font-size:14px;color:#8892A6;margin-bottom:24px;position:relative}}
.countdown{{display:flex;justify-content:center;gap:16px;margin:32px 0;position:relative}}
.countdown-item{{text-align:center}}
.countdown-num{{font-size:48px;font-weight:800;background:{accent_color}22;border:1px solid {accent_color}44;border-radius:12px;padding:16px 24px;min-width:80px;font-variant-numeric:tabular-nums}}
.countdown-label{{font-size:11px;color:#8892A6;text-transform:uppercase;letter-spacing:1px;margin-top:6px}}
.container{{max-width:800px;margin:0 auto;padding:40px 24px}}
.features{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin:32px 0}}
.feature-card{{background:#0F1320;border:1px solid #1C2136;border-radius:12px;padding:24px;text-align:center}}
.feature-icon{{font-size:32px;margin-bottom:8px}}
.feature-card h3{{font-size:14px;font-weight:600;margin-bottom:4px}}
.feature-card p{{font-size:12px;color:#8892A6}}
.book-meta{{display:flex;gap:24px;justify-content:center;margin:24px 0;flex-wrap:wrap}}
.book-meta-item{{text-align:center;padding:12px 20px;background:#0F1320;border-radius:8px;border:1px solid #1C2136}}
.book-meta-item .val{{font-size:24px;font-weight:700;color:{accent_color}}}
.book-meta-item .lbl{{font-size:11px;color:#8892A6;text-transform:uppercase}}
.email-section{{text-align:center;padding:40px;background:#0F1320;border:1px solid #1C2136;border-radius:12px;margin:32px 0}}
.email-section h3{{font-size:18px;margin-bottom:8px}}
.email-section p{{font-size:13px;color:#8892A6;margin-bottom:16px}}
.email-form{{display:flex;gap:8px;max-width:400px;margin:0 auto}}
.email-form input{{flex:1;padding:12px 16px;border-radius:8px;border:1px solid #1C2136;background:#0B0F1A;color:#E8EDF5;font-size:14px;outline:none}}
.email-form input:focus{{border-color:{accent_color}}}
.email-form button{{padding:12px 24px;border-radius:8px;border:none;background:{accent_color};color:#fff;font-weight:600;cursor:pointer;font-size:14px}}
.email-form button:hover{{opacity:.9}}
.btn{{display:inline-block;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;transition:all .2s}}
.btn{{background:{accent_color};color:#fff;margin:4px}}
.btn:hover{{opacity:.9;transform:translateY(-1px)}}
.btn-outline{{background:transparent;border:1px solid {accent_color};color:{accent_color}}}
.download-links{{text-align:center;margin:24px 0}}
.footer{{text-align:center;padding:24px;font-size:12px;color:#5B657A}}
@media(max-width:600px){{.hero h1{{font-size:28px}}.countdown-num{{font-size:32px;min-width:60px;padding:12px 16px}}.email-form{{flex-direction:column}}}}
</style>
</head>
<body>
<div class="hero">
    <div class="subtitle">Coming {launch_str}</div>
    <h1>{title}</h1>
    <div class="author">by {author}</div>
    <p style="max-width:500px;margin:0 auto;color:#8892A6;font-size:15px">{summary[:300]}</p>
    <div class="countdown" id="countdown">
        <div class="countdown-item"><div class="countdown-num" id="cd-days">00</div><div class="countdown-label">Days</div></div>
        <div class="countdown-item"><div class="countdown-num" id="cd-hours">00</div><div class="countdown-label">Hours</div></div>
        <div class="countdown-item"><div class="countdown-num" id="cd-mins">00</div><div class="countdown-label">Minutes</div></div>
        <div class="countdown-item"><div class="countdown-num" id="cd-secs">00</div><div class="countdown-label">Seconds</div></div>
    </div>
</div>
<div class="container">
    <div class="book-meta">
        <div class="book-meta-item"><div class="val">{chapter_count}</div><div class="lbl">Chapters</div></div>
        <div class="book-meta-item"><div class="val">{topic}</div><div class="lbl">Genre</div></div>
        <div class="book-meta-item"><div class="val">{launch_date_obj.strftime('%b')}</div><div class="lbl">Launch Month</div></div>
    </div>
    {download_links}
    <div class="features">
        <div class="feature-card"><div class="feature-icon">📖</div><h3>Read Anywhere</h3><p>PDF, EPUB, DOCX — all formats included</p></div>
        <div class="feature-card"><div class="feature-icon">🎨</div><h3>Beautiful Design</h3><p>Professional formatting with custom themes</p></div>
        <div class="feature-card"><div class="feature-icon">🌍</div><h3>Multi-language</h3><p>Available in 28 languages</p></div>
    </div>
    <div class="email-section">
        <h3>📬 Get notified when it launches</h3>
        <p>Be the first to know when "{title}" is available</p>
        <div class="email-form">
            <input type="email" id="launchEmail" placeholder="your@email.com">
            <button onclick="notifyMe()">Notify Me</button>
        </div>
        <div id="emailMsg" style="margin-top:8px;font-size:13px;color:#22C55E"></div>
    </div>
</div>
<div class="footer">Generated by AI Publishing Engine · {datetime.now().year}</div>
<script>
var countDownDate = new Date({launch_ts}).getTime();
var x = setInterval(function() {{
    var now = new Date().getTime();
    var distance = countDownDate - now;
    document.getElementById('cd-days').textContent = String(Math.floor(distance / (1000 * 60 * 60 * 24))).padStart(2,'0');
    document.getElementById('cd-hours').textContent = String(Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60))).padStart(2,'0');
    document.getElementById('cd-mins').textContent = String(Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60))).padStart(2,'0');
    document.getElementById('cd-secs').textContent = String(Math.floor((distance % (1000 * 60)) / 1000)).padStart(2,'0');
    if (distance < 0) {{ clearInterval(x); document.getElementById('countdown').innerHTML = '<h2>🎉 Available Now!</h2>'; }}
}}, 1000);
function notifyMe() {{
    var email = document.getElementById('launchEmail').value;
    if (!email) return;
    document.getElementById('emailMsg').textContent = '✅ You\\'ll be notified at ' + email;
    // In production, this would call a backend endpoint
}}
</script>
</body>
</html>"""
