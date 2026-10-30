"""Single-file HTML engine for generated interactive courses.

`build_course_html(course)` returns one self-contained page: a navigator by phases and lessons ("your position"), lessons with
objectives, explanation, worked example, practice exercise and a quiz that explains every answer, saved progress, a final test,
a sources page and a completion screen.

Progress lives in the browser's localStorage when the page runs on its own. When the page is embedded in an iframe (HRL Nova
Campus) it talks to the host with postMessage instead:
    page -> host   {source: "hrl-course", type: "hrl-course-ready" | "hrl-course-progress" | "hrl-course-open-test" | "hrl-course-state", ...}
    host -> page   {type: "hrl-course-init", host: "nova", completed: [lesson index, ...], work: {note, steps, meas, ans, view}}
"hrl-course-state" carries what the learner keeps inside the course (notes, ticked session steps, 0-10 ratings, quiz answers, where they are) as a patch
{note: {key: text}, steps: {key: 1}, ..., view: "lesson:2"}; a null value deletes a key. The host stores it on the learner's account and returns it in "work".
The host stores progress on the learner's account and runs the graded final test itself (that is what issues the certificate).

All course text is escaped here at build time; the page never inserts model output as markup unescaped.
"""
from __future__ import annotations

import hashlib
import html
import json
import re

ACCENTS = ["#0b6e99", "#0f766e", "#6d28d9", "#a14a08", "#be123c", "#1d4ed8"]
_CITE = re.compile(r"\[(S\d+)\]")
_BULLET = re.compile(r"^\s*[-*•]\s+")
_NUMBER = re.compile(r"^\s*\d+[.)]\s+")

LABELS = {
    "en": {
        "start": "Start", "lessons": "Lessons", "lessons_gen": "lessons", "test": "Final test", "sources": "Sources", "objectives": "In this lesson you will",
        "example": "Worked example", "exercise": "Practice", "hint": "Hint", "show_answer": "Show model answer", "hide_answer": "Hide model answer",
        "your_answer": "Write your answer here. It is saved on this device.", "quiz": "Check yourself", "correct": "Correct.", "wrong": "Not quite.",
        "retry": "Try the quiz again", "takeaways": "Key takeaways", "sources_used": "Sources for this lesson", "next": "Next", "prev": "Back",
        "continue": "Continue", "begin": "Start the course", "progress": "Progress", "position": "Your position", "learn": "What you will learn",
        "level": "Level", "beginner": "Beginner", "intermediate": "Intermediate", "advanced": "Advanced", "minutes": "min", "lesson": "Lesson",
        "lesson_done": "Lesson complete", "quiz_left": "Answer all questions to complete the lesson.", "score": "Score",
        "test_locked": "Complete all lessons to unlock the final test.", "test_intro": "Answer all questions. You pass with 70% or more.",
        "submit": "Check my answers", "passed": "Passed", "failed": "Not passed yet", "again": "Try again", "nova_test":
        "The graded final test, which issues your certificate, is in the Nova Campus panel next to this course.", "open_nova_test": "Go to the final test",
        "congrats": "You have completed the course.", "congrats_nova": "All lessons are complete. Take the final test in the panel to receive your certificate.",
        "note": "Note", "reset": "Reset my progress", "reset_confirm": "Delete all saved progress for this course?", "menu": "Menu", "skip": "Skip to content",
        "sources_intro": "Where the facts in this course come from. Check important details there.", "license": "Licence", "open": "Open",
        "ai_note": "Generated with the help of AI from the author's material and the sources listed here.", "of": "of", "question": "Question",
        "day": "Day", "days": "Days", "days_gen": "days", "theme": "Theme of the day", "reflection": "Deep reflection", "session": "Session",
        "intention": "Intention for the session", "cues": "Keep in mind", "steps": "Step by step", "before": "Before the session", "after": "After the session",
        "aha": "The insight", "complete_day": "Complete day", "undo_day": "Mark as not done", "day_done": "Day complete",
        "program": "Day-by-day programme", "structure": "Structure of the programme", "days_range": "Days", "progress_days": "Completed {n} of {m} days",
        "front": "Introduction", "extras": "Extras", "back": "Wrapping up",
        "welcome": "Welcome", "about": "About the programme", "legal": "Copyright and disclaimer", "forwhom": "Who this programme is for",
        "for_you": "This programme is for you if:", "not_for_you": "This programme is not for you if:", "what": "What the programme does",
        "does": "What it gives you:", "does_not": "What it does not promise:", "howto": "How to use it", "safety": "When NOT to use it",
        "stop_when": "Stop and rest when:", "seek_help": "Where to look for support:", "toolkit": "Worksheets", "worksheet": "Worksheet",
        "when_to_use": "When to use it", "use_on": "Useful on days:", "faq": "Frequently asked questions", "keepgoing": "What next",
        "closing": "A closing word", "outcomes_recap": "What you can do now", "start_day": "Start with day 1", "back_home": "Back to the start",
        "copyright": "© {year}. All rights reserved. This programme is for your own learning; please do not copy or share it without the author's permission. The sources keep their own licences (see Sources).",
        "disclaimer_general": "This programme is educational and does not replace advice from a professional.",
        "write_here": "Write here. Saved on this device.", "tick": "Done",
        "answered": "answered", "how": "How it works", "how_text": "Work through the lessons in order. Each one has an explanation, an example, a practice task and a short quiz. A lesson counts as complete when you have answered its quiz.",
    },
    "pl": {
        "start": "Start", "lessons": "Lekcje", "lessons_gen": "lekcji", "test": "Test końcowy", "sources": "Źródła", "objectives": "Po tej lekcji będziesz",
        "example": "Przykład krok po kroku", "exercise": "Ćwiczenie", "hint": "Podpowiedź", "show_answer": "Pokaż wzorcową odpowiedź", "hide_answer": "Ukryj wzorcową odpowiedź",
        "your_answer": "Wpisz tu swoją odpowiedź. Zapisze się na tym urządzeniu.", "quiz": "Sprawdź się", "correct": "Dobrze.", "wrong": "Nie tym razem.",
        "retry": "Rozwiąż quiz jeszcze raz", "takeaways": "Najważniejsze", "sources_used": "Źródła tej lekcji", "next": "Dalej", "prev": "Wstecz",
        "continue": "Kontynuuj", "begin": "Zacznij kurs", "progress": "Postęp", "position": "Twoja pozycja", "learn": "Czego się nauczysz",
        "level": "Poziom", "beginner": "Początkujący", "intermediate": "Średniozaawansowany", "advanced": "Zaawansowany", "minutes": "min", "lesson": "Lekcja",
        "lesson_done": "Lekcja ukończona", "quiz_left": "Odpowiedz na wszystkie pytania, aby ukończyć lekcję.", "score": "Wynik",
        "test_locked": "Ukończ wszystkie lekcje, aby odblokować test końcowy.", "test_intro": "Odpowiedz na wszystkie pytania. Zaliczasz od 70%.",
        "submit": "Sprawdź odpowiedzi", "passed": "Zaliczone", "failed": "Jeszcze nie zaliczone", "again": "Spróbuj ponownie", "nova_test":
        "Test końcowy z certyfikatem znajdziesz w panelu Nova Campus obok kursu.", "open_nova_test": "Przejdź do testu końcowego",
        "congrats": "Kurs ukończony. Gratulacje!", "congrats_nova": "Wszystkie lekcje ukończone. Zalicz test końcowy w panelu, aby dostać certyfikat.",
        "note": "Uwaga", "reset": "Wyzeruj mój postęp", "reset_confirm": "Usunąć cały zapisany postęp w tym kursie?", "menu": "Menu", "skip": "Przejdź do treści",
        "sources_intro": "Skąd pochodzą fakty w tym kursie. Ważne szczegóły sprawdź w źródłach.", "license": "Licencja", "open": "Otwórz",
        "ai_note": "Kurs powstał z pomocą AI na podstawie materiałów autora i wymienionych tu źródeł.", "of": "z", "question": "Pytanie",
        "day": "Dzień", "days": "Dni", "days_gen": "dni", "theme": "Temat dnia", "reflection": "Głęboka refleksja", "session": "Sesja",
        "intention": "Intencja sesji", "cues": "O czym pamiętać", "steps": "Krok po kroku", "before": "Przed sesją", "after": "Po sesji",
        "aha": "Moment AHA", "complete_day": "Ukończ dzień", "undo_day": "Cofnij ukończenie", "day_done": "Dzień ukończony",
        "program": "Program dzień po dniu", "structure": "Struktura programu", "days_range": "Dni", "progress_days": "Ukończono {n} z {m} dni",
        "front": "Wstęp", "extras": "Materiały dodatkowe", "back": "Zakończenie",
        "welcome": "Powitanie", "about": "O programie", "legal": "Prawa autorskie i zastrzeżenie", "forwhom": "Do kogo jest ten program",
        "for_you": "Ten program jest dla Ciebie, jeśli:", "not_for_you": "Ten program nie jest dla Ciebie, jeśli:", "what": "Co program robi",
        "does": "Co Ci daje:", "does_not": "Czego nie obiecuje:", "howto": "Jak korzystać", "safety": "Kiedy NIE korzystać",
        "stop_when": "Przerwij i odpocznij, gdy:", "seek_help": "Gdzie szukać wsparcia:", "toolkit": "Karty pracy", "worksheet": "Karta pracy",
        "when_to_use": "Kiedy jej użyć", "use_on": "Przydatna w dniach:", "faq": "Najczęstsze pytania", "keepgoing": "Następne kroki",
        "closing": "Słowo końcowe", "outcomes_recap": "Co potrafisz po programie", "start_day": "Zacznij od dnia 1", "back_home": "Wróć na start",
        "copyright": "© {year}. Wszelkie prawa zastrzeżone. Program służy do Twojej osobistej nauki; nie kopiuj go i nie rozpowszechniaj bez zgody autora. Źródła zachowują własne licencje (zob. Źródła).",
        "disclaimer_general": "Program ma charakter edukacyjny i nie zastępuje porady specjalisty.",
        "write_here": "Pisz tutaj. Zapisze się na tym urządzeniu.", "tick": "Zrobione",
        "answered": "odpowiedzi", "how": "Jak to działa", "how_text": "Przerabiaj lekcje po kolei. Każda ma wyjaśnienie, przykład, zadanie do wykonania i krótki quiz. Lekcja jest ukończona, gdy odpowiesz na pytania quizu.",
    },
}


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def _inline(text: str, nums: dict[str, int]) -> str:
    t = esc(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)

    def cite(m):
        sid = m.group(1)
        return f'<sup class="cite"><a href="#" data-src="{sid}">[{nums[sid]}]</a></sup>' if sid in nums else ""
    return _CITE.sub(cite, t)


def md(text: str, nums: dict[str, int]) -> str:
    """Small, safe subset: paragraphs, '- ' bullets, '1. ' numbered lists, **bold**, `code`, [S#] citations."""
    out = []
    for block in re.split(r"\n\s*\n", (text or "").strip()):
        lines = [l.rstrip() for l in block.split("\n") if l.strip()]
        if not lines:
            continue
        if all(_BULLET.match(l) for l in lines):
            out.append("<ul>" + "".join("<li>" + _inline(_BULLET.sub("", l), nums) + "</li>" for l in lines) + "</ul>")
        elif all(_NUMBER.match(l) for l in lines):
            out.append("<ol>" + "".join("<li>" + _inline(_NUMBER.sub("", l), nums) + "</li>" for l in lines) + "</ol>")
        else:
            out.append("<p>" + "<br>".join(_inline(l, nums) for l in lines) + "</p>")
    return "".join(out)


def course_key(course: dict) -> str:
    return hashlib.sha1(json.dumps([course.get("title"), [l["title"] for p in course["phases"] for l in p["lessons"]]], ensure_ascii=False).encode()).hexdigest()[:12]


def _html_list(items, nums) -> list[str]:
    return [_inline(i, nums) for i in items or []]


def _day_payload(l: dict, nums: dict[str, int]) -> dict:
    ses = l["session"]
    return {"focus": l.get("focus", ""), "reflection": _html_list(l.get("reflection"), nums), "aha": _inline(l.get("aha", ""), nums),
            "session": {"title": ses.get("title", ""), "minutes": ses.get("minutes", 0), "intention": _inline(ses.get("intention", ""), nums),
                        "cues": _html_list(ses.get("cues"), nums), "steps": _html_list(ses.get("steps"), nums), "measure": ses.get("measure", "")}}


def _frame_payload(frame: dict, nums: dict[str, int]) -> dict:
    """Every string in the frame leaves here HTML-safe (escaped, **bold** and paragraphs only); the page inserts it as HTML."""
    f: dict = {}
    for k in ("welcome", "about", "closing"):
        if frame.get(k):
            f[k] = md(frame[k], nums)
    for k in ("for_you", "not_for_you", "does", "does_not", "how_to_use"):
        if frame.get(k):
            f[k] = _html_list(frame[k], nums)
    if frame.get("safety"):
        s = frame["safety"]
        f["safety"] = {"title": _inline(s.get("title", ""), nums), "intro": md(s.get("intro", ""), nums),
                       "stop_when": _html_list(s.get("stop_when"), nums), "seek_help": _html_list(s.get("seek_help"), nums)}
    if frame.get("worksheets"):
        f["worksheets"] = [{"title": _inline(w["title"], nums), "when": _inline(w.get("when", ""), nums), "steps": _html_list(w["steps"], nums),
                            "prompts": _html_list(w["prompts"], nums), "days": [d for d in w.get("days", []) if isinstance(d, int)]} for w in frame["worksheets"]]
    if frame.get("faq"):
        f["faq"] = [{"q": _inline(i["q"], nums), "a": md(i["a"], nums)} for i in frame["faq"]]
    if frame.get("keep_going"):
        kg = frame["keep_going"]
        f["keep_going"] = {"intro": md(kg.get("intro", ""), nums), "items": [{"title": _inline(i["title"], nums), "text": md(i["text"], nums)} for i in kg["items"]]}
    return f


def _payload(course: dict) -> dict:
    nums = {s["id"]: i + 1 for i, s in enumerate(course.get("sources", []))}
    phases = []
    for p in course["phases"]:
        lessons = []
        for l in p["lessons"]:
            item = {
                "id": l["id"], "title": l["title"], "minutes": l["minutes"], "goal": l.get("goal", ""), "objectives": l["objectives"],
                "sections": [{"heading": s["heading"], "html": md(s["body"], nums)} for s in l["sections"]],
                "example": {"title": l["example"]["title"], "html": md(l["example"]["body"], nums)} if l["example"]["body"] else None,
                "exercise": {"prompt": md(l["exercise"]["prompt"], nums), "hint": l["exercise"]["hint"], "model": md(l["exercise"]["model_answer"], nums)} if l["exercise"]["prompt"] else None,
                "quiz": l["quiz"], "takeaways": l["takeaways"], "sources": [nums[i] for i in l["sources"] if i in nums],
            }
            if l.get("kind") == "day":
                item.update(_day_payload(l, nums))
            lessons.append(item)
        phases.append({"id": p["id"], "title": p["title"], "summary": p["summary"], "lessons": lessons})
    return {"format": course.get("format") or "lessons", "title": course["title"], "subtitle": course["subtitle"], "summary": course["summary"], "level": course["level"],
            "minutes": course["minutes"], "outcomes": course["outcomes"], "phases": phases, "test": course["final_test"], "disclaimer": course.get("disclaimer", ""),
            "frame": _frame_payload(course.get("frame") or {}, nums), "year": course.get("year") or "",
            "ui": {k: str(v)[:40] for k, v in (course.get("ui") or {}).items() if k in ("session", "reflection", "aha", "steps") and v},
            "sources": [{"n": nums[s["id"]], "title": s["title"], "url": s["url"], "license": s.get("license", "")} for s in course.get("sources", [])]}


def build_course_html(course: dict, *, accent_color: str = "", cover_image: str = "") -> str:
    lang = course.get("language") if course.get("language") in LABELS else "en"
    accent = accent_color if re.fullmatch(r"#[0-9a-fA-F]{6}", accent_color or "") else ACCENTS[int(course_key(course), 16) % len(ACCENTS)]
    data = {"key": course_key(course), "labels": LABELS[lang], "course": _payload(course), "cover": cover_image if (cover_image or "").startswith(("data:image/", "https://")) else ""}
    blob = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return (TEMPLATE.replace("__LANG__", lang).replace("__TITLE__", esc(course["title"])).replace("__ACCENT__", accent)
            .replace("__SKIP__", esc(LABELS[lang]["skip"])).replace("__CSS__", CSS).replace("__JS__", JS).replace("__DATA__", blob))


def _wrap(text: str, width: int, max_lines: int) -> list[str]:
    lines, cur = [], ""
    for w in text.split():
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".,;: ") + "…"
    return lines


def course_cover_svg(course: dict, accent_color: str = "") -> str:
    """A 1200x675 thumbnail for the course card (used as the Nova cover): gradient, soft shapes, the title."""
    accent = accent_color if re.fullmatch(r"#[0-9a-fA-F]{6}", accent_color or "") else ACCENTS[int(course_key(course), 16) % len(ACCENTS)]
    lang = course.get("language") if course.get("language") in LABELS else "en"
    n = sum(len(p["lessons"]) for p in course["phases"])
    title = _wrap(course["title"], 20, 4)
    size = 78 if len(title) <= 3 else 64
    y0 = 300 - (len(title) - 1) * size * 0.55
    tspans = "".join(f'<tspan x="80" y="{y0 + i * size * 1.15:.0f}">{esc(l)}</tspan>' for i, l in enumerate(title))
    unit = LABELS[lang]["days_gen"] if course.get("format") == "program" else LABELS[lang]["lessons"].lower()
    sub = esc(" · ".join([LABELS[lang][course["level"]] if course["level"] in LABELS[lang] else "", f"{n} {unit}", f"≈ {course['minutes']} {LABELS[lang]['minutes']}"]).strip(" ·"))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 675" width="1200" height="675" role="img" aria-label="{esc(course["title"])}">'
            f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{accent}"/><stop offset="1" stop-color="#0b1220"/></linearGradient></defs>'
            f'<rect width="1200" height="675" fill="url(#g)"/><circle cx="1010" cy="140" r="260" fill="#fff" opacity=".07"/><circle cx="1120" cy="560" r="180" fill="#fff" opacity=".06"/>'
            f'<circle cx="930" cy="470" r="90" fill="#fff" opacity=".08"/><rect x="80" y="70" width="120" height="8" rx="4" fill="#fff" opacity=".85"/>'
            f'<text font-family="Segoe UI,Helvetica,Arial,sans-serif" font-weight="700" font-size="{size}" fill="#fff">{tspans}</text>'
            f'<text x="80" y="610" font-family="Segoe UI,Helvetica,Arial,sans-serif" font-size="30" fill="#fff" opacity=".9">{sub}</text></svg>')


def cover_data_uri(course: dict, accent_color: str = "") -> str:
    import base64
    return "data:image/svg+xml;base64," + base64.b64encode(course_cover_svg(course, accent_color).encode("utf-8")).decode("ascii")


TEMPLATE = """<!doctype html>
<html lang="__LANG__"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title><style>:root{--accent:__ACCENT__}__CSS__</style></head>
<body><a class="skip" href="#main">__SKIP__</a>
<div id="app"></div>
<script type="application/json" id="course-data">__DATA__</script>
<script>__JS__</script></body></html>"""

CSS = """
*{box-sizing:border-box}html{scroll-behavior:smooth}
:root{--bg:#f6f7f9;--card:#fff;--ink:#16202a;--muted:#5b6672;--line:#dde2e8;--ok:#0a7d3c;--okbg:#e6f6ec;--bad:#b3261e;--badbg:#fdeceb;--onaccent:#fff;--soft:color-mix(in srgb,var(--accent) 9%,var(--card))}
@media (prefers-color-scheme:dark){:root{--bg:#10151b;--card:#18202a;--ink:#e8edf2;--muted:#9aa6b2;--line:#2a3441;--ok:#6fd49a;--okbg:#12281c;--bad:#ff8b84;--badbg:#321513;--soft:color-mix(in srgb,var(--accent) 16%,var(--card))}}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.65 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.skip{position:absolute;left:-999px;top:0;background:var(--accent);color:var(--onaccent);padding:.6rem 1rem;z-index:50}.skip:focus{left:8px;top:8px}
.top{position:sticky;top:0;z-index:20;background:var(--card);border-bottom:1px solid var(--line);display:flex;align-items:center;gap:.9rem;padding:.55rem 1rem}
.top h1{font-size:1rem;margin:0;flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.btn.menu{display:none}
.bar{width:150px;height:8px;background:var(--line);border-radius:99px;overflow:hidden}.bar i{display:block;height:100%;background:var(--accent);transition:width .3s}
.pct{font-size:.85rem;color:var(--muted);min-width:5.5rem;text-align:right;white-space:nowrap}
.layout{display:grid;grid-template-columns:310px minmax(0,1fr);align-items:start}
nav{position:sticky;top:3.3rem;max-height:calc(100vh - 3.3rem);overflow:auto;padding:1rem;border-right:1px solid var(--line);background:var(--card)}
nav h2{font-size:.72rem;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);margin:1rem 0 .3rem}
nav h2:first-child{margin-top:0}
nav button.n{display:flex;gap:.55rem;align-items:flex-start;width:100%;text-align:left;border:0;background:none;color:var(--ink);font:inherit;font-size:.93rem;line-height:1.35;padding:.5rem .55rem;border-radius:9px;cursor:pointer;min-height:44px}
nav button.n:hover{background:var(--soft)}nav button.n[aria-current=page]{background:var(--soft);box-shadow:inset 3px 0 var(--accent);font-weight:600}
nav button.n:disabled{opacity:.5;cursor:not-allowed}
.dot{flex:0 0 1.35rem;height:1.35rem;border-radius:50%;border:2px solid var(--line);display:grid;place-items:center;font-size:.72rem;margin-top:.05rem}
.dot.done{background:var(--ok);border-color:var(--ok);color:#fff}
main{padding:1.6rem clamp(1rem,4vw,3rem) 4rem;max-width:860px;outline:0}
main h2{font-size:1.75rem;line-height:1.25;margin:.2rem 0 .5rem}main h3{font-size:1.2rem;margin:1.8rem 0 .4rem}
.eyebrow{font-size:.8rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
.hero{background:linear-gradient(135deg,var(--accent),color-mix(in srgb,var(--accent) 55%,#000));color:var(--onaccent);border-radius:16px;padding:2rem;margin-bottom:1.3rem;background-size:cover;background-position:center}
.hero h2{color:inherit;font-size:2rem}.hero p{margin:.4rem 0;opacity:.95}
.chips{display:flex;flex-wrap:wrap;gap:.5rem;margin:.8rem 0 0}.chip{background:rgba(255,255,255,.18);border-radius:99px;padding:.15rem .75rem;font-size:.85rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:1.1rem 1.3rem;margin:1rem 0}
.card.soft{background:var(--soft)}
ul,ol{padding-left:1.3rem}li{margin:.25rem 0}
.btn{display:inline-flex;align-items:center;gap:.4rem;border:1px solid var(--accent);background:var(--accent);color:var(--onaccent);font:inherit;font-weight:600;padding:.6rem 1.2rem;border-radius:10px;cursor:pointer;min-height:44px;text-decoration:none}
.btn.ghost{background:transparent;color:var(--accent)}.btn:disabled{opacity:.5;cursor:not-allowed}
.btn:focus-visible,nav button:focus-visible,.opt:focus-visible,textarea:focus-visible,a:focus-visible{outline:3px solid color-mix(in srgb,var(--accent) 60%,#fff);outline-offset:2px}
.row{display:flex;flex-wrap:wrap;gap:.7rem;margin:1.2rem 0}
.q{margin:1.2rem 0}.q p.t{font-weight:600;margin:.2rem 0 .5rem}
.opt{display:block;width:100%;text-align:left;border:2px solid var(--line);background:var(--card);color:var(--ink);font:inherit;padding:.65rem .9rem;border-radius:10px;margin:.4rem 0;cursor:pointer;min-height:44px}
.opt:hover:not(:disabled){border-color:var(--accent)}.opt:disabled{cursor:default}
.opt.right{border-color:var(--ok);background:var(--okbg)}.opt.wrong{border-color:var(--bad);background:var(--badbg)}
.fb{margin:.4rem 0 0;padding:.6rem .9rem;border-radius:10px;font-size:.95rem}.fb.ok{background:var(--okbg)}.fb.no{background:var(--badbg)}
textarea{width:100%;min-height:8rem;font:inherit;padding:.7rem;border:2px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink);resize:vertical}
.cite a{text-decoration:none;color:var(--accent);font-weight:700}
.pill{display:inline-block;border:1px solid var(--line);border-radius:99px;padding:.1rem .7rem;font-size:.85rem;margin:.15rem .3rem .15rem 0;color:var(--accent);background:var(--card);cursor:pointer}
.banner{background:var(--okbg);border:1px solid var(--ok);border-radius:12px;padding:.8rem 1.1rem;margin:1rem 0;font-weight:600}
.note{font-size:.88rem;color:var(--muted)}
code{background:var(--soft);padding:.05rem .35rem;border-radius:5px;font-size:.92em}
.src{padding:.55rem 0;border-bottom:1px solid var(--line)}.src.hl{background:var(--soft)}
.lead{font-size:1.08rem;color:var(--muted);margin:.1rem 0 1rem}
.bar.big{width:100%;height:12px}
.phasegrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.8rem;margin:.4rem 0 1rem}.phasegrid .card{margin:0}.phase p{margin:.3rem 0 0}
.daybtn{display:flex;gap:.6rem;align-items:flex-start;width:100%;text-align:left;border:1px solid var(--line);background:var(--card);color:var(--ink);font:inherit;padding:.6rem .8rem;border-radius:10px;margin:.35rem 0;cursor:pointer;min-height:44px}
.daybtn:hover{border-color:var(--accent)}
.sess{border-left:5px solid var(--accent)}
.intent{margin:.6rem 0;padding:.6rem 1rem;border-left:3px solid var(--accent);background:var(--soft);border-radius:0 10px 10px 0;font-style:italic}
.chips2{display:flex;flex-wrap:wrap;gap:.45rem;margin:.4rem 0 .8rem}.cue{background:var(--soft);border:1px solid var(--line);border-radius:99px;padding:.15rem .8rem;font-size:.92rem}
.steps{padding-left:0;list-style:none;counter-reset:s}.steps li{counter-increment:s;margin:.5rem 0}.stp{display:flex;gap:.6rem;align-items:flex-start;cursor:pointer}
.stp input{width:1.25rem;height:1.25rem;margin-top:.3rem;accent-color:var(--accent);flex:0 0 auto}.stp span:before{content:counter(s) ". ";font-weight:700;color:var(--accent)}
.meas{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;margin:.6rem 0}
.meas select{font:inherit;padding:.3rem .5rem;border:2px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink);min-height:36px}
.aha{background:linear-gradient(135deg,var(--soft),var(--card));border-color:var(--accent)}.aha p{font-size:1.1rem;font-weight:600;margin:.4rem 0 0}
.card.good{border-left:5px solid var(--ok)}.card.bad{border-left:5px solid var(--bad)}.warn{border-color:var(--bad);border-width:2px}
ul.good li::marker{content:"✓  ";color:var(--ok);font-weight:700}ul.bad li::marker{content:"✕  ";color:var(--bad);font-weight:700}
details.faq{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:.2rem 1rem;margin:.5rem 0}details.faq summary{cursor:pointer;font-weight:600;padding:.6rem 0;min-height:44px}
@media (max-width:860px){.layout{display:block}.btn.menu{display:inline-flex}.bar{width:90px}nav{display:none;position:fixed;inset:3.3rem 0 0 0;z-index:30;max-height:none;border-right:0}nav.open{display:block}
.hero{padding:1.3rem}.hero h2{font-size:1.5rem}.pct{min-width:0}}
@media print{.top,nav,.row,.skip{display:none}.layout{display:block}body{background:#fff}}
"""

JS = r"""
(function(){'use strict';
var D=JSON.parse(document.getElementById('course-data').textContent),L=D.labels,C=D.course,KEY='hrl-course:'+D.key;
['session','reflection','aha','steps'].forEach(function(k){if(C.ui&&typeof C.ui[k]==='string'&&C.ui[k])L[k]=C.ui[k];});   // names of the day's blocks, chosen to fit the subject
var lessons=[];C.phases.forEach(function(p){p.lessons.forEach(function(l){l.index=lessons.length;l.phase=p.title;lessons.push(l);});});
var host=null,embedded=window.parent!==window,S=load(),navOpen=false,hlSrc=null;
function fresh(){return{done:{},ans:{},note:{},steps:{},meas:{},test:null,view:'home'};}
function load(){try{var r=localStorage.getItem(KEY);return r?Object.assign(fresh(),JSON.parse(r)):fresh();}catch(e){return fresh();}}
var SYNC=['note','steps','meas','ans'],sent={},flushT;
function real(v){return v!=null&&!(typeof v==='object'&&Object.keys(v).length===0);}   // an empty rating or answer list is just a place waiting for input
function snap(){sent={view:S.view};SYNC.forEach(function(g){sent[g]={};Object.keys(S[g]||{}).forEach(function(k){if(real(S[g][k]))sent[g][k]=JSON.stringify(S[g][k]);});});}
function flush(){var patch={},any=false;SYNC.forEach(function(g){var cur=S[g]||{},was=sent[g]=sent[g]||{},p={},n=0;
Object.keys(cur).forEach(function(k){if(!real(cur[k]))return;var j=JSON.stringify(cur[k]);if(was[k]!==j){p[k]=cur[k];was[k]=j;n++;}});
Object.keys(was).forEach(function(k){if(!real(cur[k])){p[k]=null;delete was[k];n++;}});if(n){patch[g]=p;any=true;}});
if(S.view!==sent.view){patch.view=S.view;sent.view=S.view;any=true;}if(any)post({type:'hrl-course-state',patch:patch});}
function save(){try{localStorage.setItem(KEY,JSON.stringify(S));}catch(e){}if(embedded){clearTimeout(flushT);flushT=setTimeout(flush,600);}}
function post(m){if(!embedded)return;try{window.parent.postMessage(Object.assign({source:'hrl-course',course:D.key},m),'*');}catch(e){}}
function h(tag,attrs){var e=document.createElement(tag);attrs=attrs||{};for(var k in attrs){var v=attrs[k];if(v==null||v===false)continue;if(k==='class')e.className=v;else if(k==='html')e.innerHTML=v;else if(k.slice(0,2)==='on')e.addEventListener(k.slice(2),v);else e.setAttribute(k,v===true?'':v);}
for(var i=2;i<arguments.length;i++)add(e,arguments[i]);return e;}
function add(e,c){if(c==null||c===false)return;if(Array.isArray(c)){c.forEach(function(x){add(e,x);});return;}e.appendChild(typeof c==='object'?c:document.createTextNode(String(c)));}
function done(l){return !!S.done[l.id];}
function doneCount(){return lessons.filter(done).length;}
function percent(){return lessons.length?Math.round(100*doneCount()/lessons.length):0;}
function allDone(){return doneCount()===lessons.length;}
function setDone(l,v){if(!!S.done[l.id]===v)return;if(v)S.done[l.id]=true;else delete S.done[l.id];save();post({type:'hrl-course-progress',index:l.index,lessonId:l.id,completed:v,done:doneCount(),total:lessons.length,percent:percent()});}
snap();
window.addEventListener('message',function(ev){var m=ev.data;if(ev.source!==window.parent||!m||m.type!=='hrl-course-init')return;host=m.host||'nova';
if(Array.isArray(m.completed)){m.completed.forEach(function(i){if(lessons[i])S.done[lessons[i].id]=true;});}
if(m.work&&typeof m.work==='object'){SYNC.forEach(function(g){var w=m.work[g];if(!w||typeof w!=='object')return;S[g]=S[g]||{};Object.keys(w).forEach(function(k){S[g][k]=w[k];});});
if(typeof m.work.view==='string'&&S.view==='home')S.view=m.work.view;snap();}   // what the account already holds is not sent back
save();render();});
function go(view){S.view=view;save();navOpen=false;render();var m=document.getElementById('main');if(m){m.focus({preventScroll:true});}window.scrollTo(0,0);}
function nextOpen(){for(var i=0;i<lessons.length;i++)if(!done(lessons[i]))return i;return -1;}
function levelName(){return L[C.level]||C.level;}
var PROGRAM=C.format==='program',FR=C.frame||{},HAS_FRAME=PROGRAM||Object.keys(FR).length>0,UNIT=PROGRAM?L.days_gen:L.lessons_gen;
function wsheets(){return FR.worksheets||[];}
var FRONT=[],BACK=[];
if(FR.welcome)FRONT.push('welcome');if(FR.about)FRONT.push('about');if(HAS_FRAME)FRONT.push('legal');if(FR.safety)FRONT.push('safety');
if(FR.for_you||FR.not_for_you)FRONT.push('forwhom');if(FR.does||FR.does_not)FRONT.push('what');if(FR.how_to_use)FRONT.push('howto');
if(wsheets().length)BACK.push('toolkit');if(FR.faq)BACK.push('faq');if(HAS_FRAME)BACK.push('next');
var PAGE_LABEL={welcome:L.welcome,about:L.about,legal:L.legal,safety:L.safety,forwhom:L.forwhom,what:L.what,howto:L.howto,toolkit:L.toolkit,faq:L.faq,next:L.keepgoing};
function dayLabel(l){return PROGRAM?L.day+' '+(l.index+1)+': '+l.title:l.title;}
function noteArea(key){var ta=h('textarea',{'aria-label':L.write_here,placeholder:L.write_here});ta.value=S.note[key]||'';var t;ta.addEventListener('input',function(){clearTimeout(t);t=setTimeout(function(){S.note[key]=ta.value;save();},300);});return ta;}

function renderNav(){var n=h('nav',{id:'nav','aria-label':L.position,class:navOpen?'open':''});
n.appendChild(h('h2',null,L.position));
n.appendChild(navBtn(L.start,'home',false,S.view==='home'));
if(FRONT.length){n.appendChild(h('h2',null,L.front));FRONT.forEach(function(p){n.appendChild(navBtn(PAGE_LABEL[p],'page:'+p,false,S.view==='page:'+p));});}
C.phases.forEach(function(p){n.appendChild(h('h2',null,p.title));p.lessons.forEach(function(l){
var cur=S.view==='lesson:'+l.index;n.appendChild(navBtn(dayLabel(l),'lesson:'+l.index,done(l),cur,l.minutes+' '+L.minutes));});});
var extras=BACK.filter(function(p){return p!=='next';});
if(extras.length){n.appendChild(h('h2',null,L.extras));extras.forEach(function(p){n.appendChild(navBtn(PAGE_LABEL[p],'page:'+p,false,S.view==='page:'+p));});}
n.appendChild(h('h2',null,L.test));n.appendChild(navBtn(L.test,'test',!!(S.test&&S.test.passed),S.view==='test',null,false));
if(BACK.indexOf('next')>=0){n.appendChild(h('h2',null,L.back));n.appendChild(navBtn(PAGE_LABEL.next,'page:next',false,S.view==='page:next'));}
n.appendChild(h('h2',null,L.sources));n.appendChild(navBtn(L.sources,'sources',false,S.view==='sources'));
if(!embedded)n.appendChild(h('p',{class:'note'},h('button',{class:'btn ghost',style:'font-size:.8rem;min-height:36px;padding:.3rem .8rem',onclick:function(){if(confirm(L.reset_confirm)){S=fresh();save();render();}}},L.reset)));
return n;}
function navBtn(label,view,isDone,isCur,meta,disabled){var b=h('button',{class:'n',type:'button','aria-current':isCur?'page':null,disabled:disabled?true:null,onclick:function(){go(view);}},
h('span',{class:'dot'+(isDone?' done':''),'aria-hidden':'true'},isDone?'✓':''),h('span',null,label,meta?h('span',{class:'note'},' · '+meta):null));return b;}

function renderTop(){return h('header',{class:'top'},h('button',{class:'btn ghost menu',type:'button','aria-expanded':String(navOpen),'aria-controls':'nav',onclick:function(){navOpen=!navOpen;render();}},L.menu),
h('h1',null,C.title),h('div',{class:'bar',role:'progressbar','aria-valuemin':'0','aria-valuemax':'100','aria-valuenow':String(percent()),'aria-label':L.progress},h('i',{style:'width:'+percent()+'%'})),h('span',{class:'pct'},host==='nova'?doneCount()+' '+L.of+' '+lessons.length+' '+UNIT:L.progress+' '+percent()+'%'));}

function startTarget(){var i=nextOpen();if(doneCount()===0&&FRONT.length)return 'page:'+FRONT[0];return i<0?'test':'lesson:'+i;}
function viewHomeProgram(){var f=document.createDocumentFragment(),i=nextOpen();
f.appendChild(h('div',{class:'hero',style:D.cover?'background-image:linear-gradient(135deg,rgba(0,0,0,.55),rgba(0,0,0,.25)),url('+D.cover+')':null},h('div',{class:'eyebrow',style:'color:inherit;opacity:.85'},C.subtitle||''),h('h2',null,C.title),h('p',null,C.summary),
h('div',{class:'chips'},h('span',{class:'chip'},L.level+': '+levelName()),h('span',{class:'chip'},lessons.length+' '+L.days_gen),h('span',{class:'chip'},'≈ '+C.minutes+' '+L.minutes))));
f.appendChild(h('div',{class:'row'},h('button',{class:'btn',type:'button',onclick:function(){go(startTarget());}},doneCount()===0?L.begin:(i<0?L.test:L.continue))));
f.appendChild(h('div',{class:'card'},h('h3',{style:'margin-top:0'},L.progress),h('p',null,L.progress_days.replace('{n}',doneCount()).replace('{m}',lessons.length)),
h('div',{class:'bar big',role:'progressbar','aria-valuemin':'0','aria-valuemax':'100','aria-valuenow':String(percent()),'aria-label':L.progress},h('i',{style:'width:'+percent()+'%'}))));
if(allDone())f.appendChild(h('div',{class:'banner',role:'status'},host==='nova'?L.congrats_nova:L.congrats));
f.appendChild(h('h3',null,L.structure));var grid=h('div',{class:'phasegrid'}),from=0;
C.phases.forEach(function(p,pi){var a=from+1,b=from+p.lessons.length;from=b;
grid.appendChild(h('div',{class:'card phase'},h('div',{class:'eyebrow'},String(pi+1).padStart(2,'0')+' · '+L.days_range+' '+a+(b>a?'–'+b:'')),h('strong',null,p.title),h('p',{class:'note'},p.summary)));});
f.appendChild(grid);
if(C.outcomes.length){f.appendChild(h('div',{class:'card'},h('h3',{style:'margin-top:0'},L.learn),h('ul',null,C.outcomes.map(function(o){return h('li',null,o);}))));}
f.appendChild(h('h3',null,L.program));
C.phases.forEach(function(p){f.appendChild(h('div',{class:'eyebrow',style:'margin-top:1rem'},p.title));p.lessons.forEach(function(l){
f.appendChild(h('button',{class:'daybtn',type:'button',onclick:function(){go('lesson:'+l.index);}},h('span',{class:'dot'+(done(l)?' done':''),'aria-hidden':'true'},done(l)?'✓':''),
h('span',null,h('strong',null,L.day+' '+(l.index+1)+': '),l.title,l.focus?h('span',{class:'note'},' — '+l.focus):null)));});});
if(C.disclaimer){f.appendChild(h('p',{class:'note'},h('strong',null,L.note+': '),C.disclaimer));}
f.appendChild(h('p',{class:'note'},L.ai_note));return f;}

function viewHome(){if(PROGRAM)return viewHomeProgram();var f=document.createDocumentFragment(),i=nextOpen();
var hero=h('div',{class:'hero',style:D.cover?'background-image:linear-gradient(135deg,rgba(0,0,0,.55),rgba(0,0,0,.25)),url('+D.cover+')':null},h('div',{class:'eyebrow',style:'color:inherit;opacity:.85'},C.subtitle||''),h('h2',null,C.title),h('p',null,C.summary),
h('div',{class:'chips'},h('span',{class:'chip'},L.level+': '+levelName()),h('span',{class:'chip'},lessons.length+' '+L.lessons.toLowerCase()),h('span',{class:'chip'},'≈ '+C.minutes+' '+L.minutes)));
f.appendChild(hero);
if(C.outcomes.length){f.appendChild(h('div',{class:'card'},h('h3',{style:'margin-top:0'},L.learn),h('ul',null,C.outcomes.map(function(o){return h('li',null,o);}))));}
f.appendChild(h('div',{class:'card soft'},h('strong',null,L.how),h('p',{style:'margin:.3rem 0 0'},L.how_text)));
if(allDone()){f.appendChild(h('div',{class:'banner',role:'status'},host==='nova'?L.congrats_nova:L.congrats));}
f.appendChild(h('div',{class:'row'},h('button',{class:'btn',type:'button',onclick:function(){go(i<0?'test':'lesson:'+i);}},doneCount()===0?L.begin:(i<0?L.test:L.continue))));
if(C.disclaimer){f.appendChild(h('p',{class:'note'},h('strong',null,L.note+': '),C.disclaimer));}
f.appendChild(h('p',{class:'note'},L.ai_note));return f;}

function sourcePills(l){if(!l.sources.length)return null;var sp=h('p',{class:'note'},L.sources_used+': ');
l.sources.forEach(function(n){sp.appendChild(h('a',{class:'pill',href:'#','data-src':'S'+n,onclick:function(e){e.preventDefault();hlSrc=n;go('sources');}},'['+n+'] '+((C.sources.filter(function(s){return s.n===n;})[0]||{}).title||'').slice(0,40)));});return sp;}

function measureSel(l,which){var m=S.meas[l.id]=S.meas[l.id]||{},label=(which==='before'?L.before:L.after),sel=h('select',{'aria-label':label+': '+l.session.measure},h('option',{value:''},'—'));
for(var i=0;i<=10;i++)sel.appendChild(h('option',{value:String(i)},String(i)));
sel.value=m[which]==null?'':String(m[which]);sel.addEventListener('change',function(){if(sel.value==='')delete m[which];else m[which]=+sel.value;save();});
return h('label',{class:'meas'},h('span',null,label+' (0–10): '+l.session.measure),sel);}

function viewDay(l){var f=document.createDocumentFragment(),ses=l.session;
f.appendChild(h('div',{class:'eyebrow'},l.phase+' · '+L.day+' '+(l.index+1)+' '+L.of+' '+lessons.length+' · '+l.minutes+' '+L.minutes));
f.appendChild(h('h2',null,L.day+' '+(l.index+1)+': '+l.title));
if(l.focus)f.appendChild(h('p',{class:'lead'},l.focus));
var ban=h('div',{class:'banner',role:'status'},'✓ '+L.day_done);f.appendChild(ban);
f.appendChild(h('h3',null,L.theme));
l.sections.forEach(function(s){if(s.heading)f.appendChild(h('h4',{style:'margin:1.2rem 0 .3rem'},s.heading));f.appendChild(h('div',{html:s.html}));});
if(l.reflection.length){var rc=h('div',{class:'card'},h('strong',null,L.reflection));l.reflection.forEach(function(q,qi){rc.appendChild(h('p',{html:q,style:'margin-bottom:.3rem'}));rc.appendChild(noteArea(l.id+':r'+qi));});f.appendChild(rc);}
var sc=h('div',{class:'card sess'},h('div',{class:'eyebrow'},L.session+' · '+ses.minutes+' '+L.minutes),h('h3',{style:'margin:.2rem 0 .4rem'},ses.title||L.session));
if(ses.intention)sc.appendChild(h('blockquote',{class:'intent',html:ses.intention}));
if(ses.measure)sc.appendChild(measureSel(l,'before'));
if(ses.cues.length){sc.appendChild(h('strong',null,L.cues));sc.appendChild(h('div',{class:'chips2'},ses.cues.map(function(c){return h('span',{class:'cue',html:c});})));}
sc.appendChild(h('strong',null,L.steps));
sc.appendChild(h('ol',{class:'steps'},ses.steps.map(function(s,si){var key=l.id+':'+si,cb=h('input',{type:'checkbox','aria-label':L.tick+' '+(si+1)});
cb.checked=!!S.steps[key];cb.addEventListener('change',function(){if(cb.checked)S.steps[key]=1;else delete S.steps[key];save();});
return h('li',null,h('label',{class:'stp'},cb,h('span',{html:s})));})));
if(ses.measure)sc.appendChild(measureSel(l,'after'));
f.appendChild(sc);
if(l.aha)f.appendChild(h('div',{class:'card aha'},h('strong',null,L.aha),h('p',{html:l.aha})));
var used=wsheets().filter(function(w){return w.days.indexOf(l.index+1)>=0;});
if(used.length){var wp=h('p',{class:'note'},L.worksheet+': ');used.forEach(function(w){wp.appendChild(h('a',{class:'pill',href:'#',onclick:function(e){e.preventDefault();go('page:toolkit');},html:w.title}));});f.appendChild(wp);}
f.appendChild(quizBlock(l,false));
add(f,sourcePills(l));
var btn=h('button',{class:'btn',type:'button'});
function paint(){var d=done(l);btn.textContent=d?'✓ '+L.undo_day:L.complete_day+' '+(l.index+1);btn.className=d?'btn ghost':'btn';ban.hidden=!d;}
btn.addEventListener('click',function(){setDone(l,!done(l));paint();refreshChrome();});paint();
var nav=h('div',{class:'row'});
if(l.index>0)nav.appendChild(h('button',{class:'btn ghost',type:'button',onclick:function(){go('lesson:'+(l.index-1));}},'← '+L.prev));
nav.appendChild(btn);
nav.appendChild(h('button',{class:'btn ghost',type:'button',onclick:function(){go(l.index+1<lessons.length?'lesson:'+(l.index+1):'test');}},(l.index+1<lessons.length?L.next:L.test)+' →'));
f.appendChild(nav);return f;}

function viewLesson(l){if(l.session)return viewDay(l);var f=document.createDocumentFragment();
f.appendChild(h('div',{class:'eyebrow'},l.phase+' · '+L.lesson+' '+(l.index+1)+' '+L.of+' '+lessons.length+' · '+l.minutes+' '+L.minutes));
f.appendChild(h('h2',null,l.title));
if(done(l))f.appendChild(h('div',{class:'banner',role:'status'},'✓ '+L.lesson_done));
if(l.objectives.length)f.appendChild(h('div',{class:'card soft'},h('strong',null,L.objectives),h('ul',null,l.objectives.map(function(o){return h('li',null,o);}))));
l.sections.forEach(function(s){if(s.heading)f.appendChild(h('h3',null,s.heading));f.appendChild(h('div',{html:s.html}));});
if(l.example){f.appendChild(h('div',{class:'card'},h('strong',null,L.example+(l.example.title?': '+l.example.title:'')),h('div',{html:l.example.html})));}
if(l.exercise)f.appendChild(exerciseBlock(l));
f.appendChild(quizBlock(l));
if(l.takeaways.length)f.appendChild(h('div',{class:'card soft'},h('strong',null,L.takeaways),h('ul',null,l.takeaways.map(function(t){return h('li',null,t);}))));
add(f,sourcePills(l));
var nav=h('div',{class:'row'});
if(l.index>0)nav.appendChild(h('button',{class:'btn ghost',type:'button',onclick:function(){go('lesson:'+(l.index-1));}},'← '+L.prev));
nav.appendChild(h('button',{class:'btn',type:'button',onclick:function(){go(l.index+1<lessons.length?'lesson:'+(l.index+1):'test');}},(l.index+1<lessons.length?L.next:L.test)+' →'));
f.appendChild(nav);return f;}

function exerciseBlock(l){var ex=l.exercise,shown=false,box=h('div',{class:'card'});
var ta=h('textarea',{'aria-label':L.exercise,placeholder:L.your_answer});ta.value=S.note[l.id]||'';
var t;ta.addEventListener('input',function(){clearTimeout(t);t=setTimeout(function(){S.note[l.id]=ta.value;save();},300);});
var ans=h('div',{class:'card soft',hidden:true,html:ex.model});
var hint=ex.hint?h('p',{class:'note',hidden:true},h('strong',null,L.hint+': '),ex.hint):null;
var bHint=ex.hint?h('button',{class:'btn ghost',type:'button',onclick:function(){hint.hidden=!hint.hidden;}},L.hint):null;
var bAns=h('button',{class:'btn ghost',type:'button','aria-expanded':'false',onclick:function(){shown=!shown;ans.hidden=!shown;bAns.textContent=shown?L.hide_answer:L.show_answer;bAns.setAttribute('aria-expanded',String(shown));}},L.show_answer);
box.appendChild(h('strong',null,L.exercise));box.appendChild(h('div',{html:ex.prompt}));box.appendChild(ta);box.appendChild(h('div',{class:'row',style:'margin:.6rem 0'},bHint,bAns));
if(hint)box.appendChild(hint);box.appendChild(ans);return box;}

function quizBlock(l,gate){var box=h('div',{class:'card'}),a=S.ans[l.id]=S.ans[l.id]||[];
function draw(){box.innerHTML='';box.appendChild(h('strong',null,L.quiz));
l.quiz.forEach(function(q,qi){var qd=h('div',{class:'q'},h('p',{class:'t'},(qi+1)+'. '+q.q)),chosen=a[qi];
q.options.forEach(function(o,oi){var cls='opt'+(chosen!=null?(oi===q.correct?' right':(oi===chosen?' wrong':'')):'');
qd.appendChild(h('button',{class:cls,type:'button',disabled:chosen!=null?true:null,'aria-pressed':chosen===oi?'true':'false',onclick:function(){a[qi]=oi;save();finish();draw();}},o));});
if(chosen!=null){qd.appendChild(h('p',{class:'fb '+(chosen===q.correct?'ok':'no'),role:'status'},h('strong',null,(chosen===q.correct?L.correct:L.wrong)+' '),q.explanation));}
box.appendChild(qd);});
var n=a.filter(function(x){return x!=null;}).length,right=l.quiz.filter(function(q,i){return a[i]===q.correct;}).length;
if(n<l.quiz.length)box.appendChild(h('p',{class:'note'},L.quiz_left+' ('+n+'/'+l.quiz.length+')'));
else{box.appendChild(h('p',null,h('strong',null,L.score+': '+right+'/'+l.quiz.length)));box.appendChild(h('button',{class:'btn ghost',type:'button',onclick:function(){S.ans[l.id]=a=[];save();draw();}},L.retry));}}
function finish(){if(gate!==false&&a.filter(function(x){return x!=null;}).length===l.quiz.length){setDone(l,true);refreshChrome();}}
draw();return box;}

function listCard(title,items,cls){return h('div',{class:'card '+(cls||'')},h('strong',null,title),h('ul',{class:cls||null},items.map(function(x){return h('li',{html:x});})));}
function pageNav(id){var i=FRONT.indexOf(id),row=h('div',{class:'row'});if(i<0)return row;
if(i>0)row.appendChild(h('button',{class:'btn ghost',type:'button',onclick:function(){go('page:'+FRONT[i-1]);}},'← '+L.prev));
if(i+1<FRONT.length)row.appendChild(h('button',{class:'btn',type:'button',onclick:function(){go('page:'+FRONT[i+1]);}},PAGE_LABEL[FRONT[i+1]]+' →'));
else row.appendChild(h('button',{class:'btn',type:'button',onclick:function(){go('lesson:0');}},(PROGRAM?L.start_day:L.begin)+' →'));
return row;}
function viewPage(id){var f=document.createDocumentFragment();f.appendChild(h('h2',null,PAGE_LABEL[id]));
if(id==='welcome'){f.appendChild(h('div',{html:FR.welcome}));}
else if(id==='about'){f.appendChild(h('div',{html:FR.about}));}
else if(id==='legal'){f.appendChild(h('div',{class:'card'},h('p',null,(L.copyright||'').replace('{year}',C.year||new Date().getFullYear()))));
f.appendChild(h('div',{class:'card soft'},h('p',null,C.disclaimer||L.disclaimer_general),h('p',{class:'note'},L.ai_note)));}
else if(id==='safety'){var s=FR.safety;f.appendChild(h('div',{class:'card warn'},s.title?h('strong',{html:s.title}):null,h('div',{html:s.intro})));
if(s.stop_when.length)f.appendChild(listCard(L.stop_when,s.stop_when));if(s.seek_help.length)f.appendChild(listCard(L.seek_help,s.seek_help));
if(C.disclaimer)f.appendChild(h('p',{class:'note'},C.disclaimer));}
else if(id==='forwhom'){if(FR.for_you)f.appendChild(listCard(L.for_you,FR.for_you,'good'));if(FR.not_for_you)f.appendChild(listCard(L.not_for_you,FR.not_for_you,'bad'));}
else if(id==='what'){f.appendChild(h('p',null,C.summary));if(FR.does)f.appendChild(listCard(L.does,FR.does,'good'));if(FR.does_not)f.appendChild(listCard(L.does_not,FR.does_not,'bad'));}
else if(id==='howto'){f.appendChild(h('ol',null,FR.how_to_use.map(function(x){return h('li',{html:x});})));}
else if(id==='toolkit'){wsheets().forEach(function(w,wi){var c=h('div',{class:'card'},h('h3',{style:'margin-top:0',html:w.title}));
if(w.when)c.appendChild(h('p',{class:'note'},h('strong',null,L.when_to_use+': '),h('span',{html:w.when})));
c.appendChild(h('ol',null,w.steps.map(function(x){return h('li',{html:x});})));
w.prompts.forEach(function(p,pj){c.appendChild(h('p',{html:p,style:'margin-bottom:.2rem;font-weight:600'}));c.appendChild(noteArea('ws'+wi+':'+pj));});
if(w.days.length){var dp=h('p',{class:'note'},L.use_on+' ');w.days.forEach(function(d){if(lessons[d-1])dp.appendChild(h('a',{class:'pill',href:'#',onclick:function(e){e.preventDefault();go('lesson:'+(d-1));}},String(d)));});c.appendChild(dp);}
f.appendChild(c);});}
else if(id==='faq'){FR.faq.forEach(function(it){f.appendChild(h('details',{class:'faq'},h('summary',{html:it.q}),h('div',{html:it.a})));});}
else if(id==='next'){if(FR.keep_going){if(FR.keep_going.intro)f.appendChild(h('div',{html:FR.keep_going.intro}));
FR.keep_going.items.forEach(function(it){f.appendChild(h('div',{class:'card'},h('strong',{html:it.title}),h('div',{html:it.text})));});}
if(C.outcomes.length)f.appendChild(h('div',{class:'card soft'},h('strong',null,L.outcomes_recap),h('ul',null,C.outcomes.map(function(o){return h('li',null,o);}))));
if(FR.closing){f.appendChild(h('h3',null,L.closing));f.appendChild(h('div',{html:FR.closing}));}
f.appendChild(h('div',{class:'row'},h('button',{class:'btn ghost',type:'button',onclick:function(){go('home');}},L.back_home)));}
if(FRONT.indexOf(id)>=0)f.appendChild(pageNav(id));return f;}
function afterTest(){return BACK.indexOf('next')>=0?h('div',{class:'row'},h('button',{class:'btn ghost',type:'button',onclick:function(){go('page:next');}},L.keepgoing+' →')):null;}

function viewTest(){var f=document.createDocumentFragment();f.appendChild(h('h2',null,L.test));
if(!allDone()){f.appendChild(h('div',{class:'card soft',role:'status'},L.test_locked));return f;}
if(host==='nova'){f.appendChild(h('div',{class:'card soft'},L.nova_test));f.appendChild(h('div',{class:'row'},h('button',{class:'btn',type:'button',onclick:function(){post({type:'hrl-course-open-test'});}},L.open_nova_test)));add(f,afterTest());return f;}
f.appendChild(h('p',null,L.test_intro));var T=S.test||{a:[],passed:false,submitted:false},box=h('div');f.appendChild(box);add(f,afterTest());
function draw(){box.innerHTML='';C.test.forEach(function(q,qi){var qd=h('div',{class:'q'},h('p',{class:'t'},(qi+1)+'. '+q.q));
q.options.forEach(function(o,oi){var cls='opt'+(T.submitted?(oi===q.correct?' right':(oi===T.a[qi]?' wrong':'')):(T.a[qi]===oi?' wrong':''));
qd.appendChild(h('button',{class:cls,style:(!T.submitted&&T.a[qi]===oi)?'border-color:var(--accent);background:var(--soft)':null,type:'button',disabled:T.submitted?true:null,'aria-pressed':T.a[qi]===oi?'true':'false',onclick:function(){T.a[qi]=oi;S.test=T;save();draw();}},o));});
if(T.submitted)qd.appendChild(h('p',{class:'fb '+(T.a[qi]===q.correct?'ok':'no')},q.explanation));box.appendChild(qd);});
var answered=T.a.filter(function(x){return x!=null;}).length;
if(!T.submitted)box.appendChild(h('button',{class:'btn',type:'button',disabled:answered<C.test.length?true:null,onclick:function(){var right=C.test.filter(function(q,i){return T.a[i]===q.correct;}).length;T.submitted=true;T.score=Math.round(100*right/C.test.length);T.passed=T.score>=70;S.test=T;save();draw();}},L.submit+' ('+answered+'/'+C.test.length+')'));
else{box.appendChild(h('div',{class:'banner',role:'status'},L.score+': '+T.score+'% · '+(T.passed?L.passed+'. '+L.congrats:L.failed)));if(!T.passed)box.appendChild(h('button',{class:'btn ghost',type:'button',onclick:function(){S.test=T={a:[],passed:false,submitted:false};save();draw();}},L.again));}}
draw();return f;}

function viewSources(){var f=document.createDocumentFragment();f.appendChild(h('h2',null,L.sources));f.appendChild(h('p',null,L.sources_intro));
if(!C.sources.length)f.appendChild(h('p',{class:'note'},'—'));
C.sources.forEach(function(s){f.appendChild(h('div',{class:'src'+(hlSrc===s.n?' hl':'')},h('strong',null,'['+s.n+'] '),s.title,' ',h('a',{href:s.url,target:'_blank',rel:'noopener noreferrer'},L.open+' ↗'),s.license?h('div',{class:'note'},L.license+': '+s.license):null));});
hlSrc=null;f.appendChild(h('p',{class:'note'},L.ai_note));return f;}

function refreshChrome(){var app=document.getElementById('app');var top=app.querySelector('.top'),nav=app.querySelector('nav');if(top)top.replaceWith(renderTop());if(nav)nav.replaceWith(renderNav());}
function render(){var app=document.getElementById('app');app.innerHTML='';app.appendChild(renderTop());
var main=h('main',{id:'main',tabindex:'-1'});var v=S.view,m=/^lesson:(\d+)$/.exec(v),pm=/^page:(\w+)$/.exec(v);
main.appendChild(m&&lessons[+m[1]]?viewLesson(lessons[+m[1]]):pm&&PAGE_LABEL[pm[1]]&&(FRONT.indexOf(pm[1])>=0||BACK.indexOf(pm[1])>=0)?viewPage(pm[1]):v==='test'?viewTest():v==='sources'?viewSources():viewHome());
app.appendChild(h('div',{class:'layout'},renderNav(),main));}
render();
if(embedded)post({type:'hrl-course-ready',total:lessons.length,done:doneCount()});
})();
"""
