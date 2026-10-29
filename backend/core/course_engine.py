"""Single-file HTML engine for generated interactive courses.

`build_course_html(course)` returns one self-contained page: a navigator by phases and lessons ("your position"), lessons with
objectives, explanation, worked example, practice exercise and a quiz that explains every answer, saved progress, a final test,
a sources page and a completion screen.

Progress lives in the browser's localStorage when the page runs on its own. When the page is embedded in an iframe (HRL Nova
Campus) it talks to the host with postMessage instead:
    page -> host   {source: "hrl-course", type: "hrl-course-ready" | "hrl-course-progress" | "hrl-course-open-test", ...}
    host -> page   {type: "hrl-course-init", host: "nova", completed: [lesson index, ...]}
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


def _payload(course: dict) -> dict:
    nums = {s["id"]: i + 1 for i, s in enumerate(course.get("sources", []))}
    phases = []
    for p in course["phases"]:
        lessons = []
        for l in p["lessons"]:
            lessons.append({
                "id": l["id"], "title": l["title"], "minutes": l["minutes"], "goal": l.get("goal", ""), "objectives": l["objectives"],
                "sections": [{"heading": s["heading"], "html": md(s["body"], nums)} for s in l["sections"]],
                "example": {"title": l["example"]["title"], "html": md(l["example"]["body"], nums)} if l["example"]["body"] else None,
                "exercise": {"prompt": md(l["exercise"]["prompt"], nums), "hint": l["exercise"]["hint"], "model": md(l["exercise"]["model_answer"], nums)} if l["exercise"]["prompt"] else None,
                "quiz": l["quiz"], "takeaways": l["takeaways"], "sources": [nums[i] for i in l["sources"] if i in nums],
            })
        phases.append({"id": p["id"], "title": p["title"], "summary": p["summary"], "lessons": lessons})
    return {"title": course["title"], "subtitle": course["subtitle"], "summary": course["summary"], "level": course["level"], "minutes": course["minutes"],
            "outcomes": course["outcomes"], "phases": phases, "test": course["final_test"], "disclaimer": course.get("disclaimer", ""),
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
    sub = esc(" · ".join([LABELS[lang][course["level"]] if course["level"] in LABELS[lang] else "", f"{n} {LABELS[lang]['lessons'].lower()}", f"≈ {course['minutes']} {LABELS[lang]['minutes']}"]).strip(" ·"))
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
@media (max-width:860px){.layout{display:block}.btn.menu{display:inline-flex}.bar{width:90px}nav{display:none;position:fixed;inset:3.3rem 0 0 0;z-index:30;max-height:none;border-right:0}nav.open{display:block}
.hero{padding:1.3rem}.hero h2{font-size:1.5rem}.pct{min-width:0}}
@media print{.top,nav,.row,.skip{display:none}.layout{display:block}body{background:#fff}}
"""

JS = r"""
(function(){'use strict';
var D=JSON.parse(document.getElementById('course-data').textContent),L=D.labels,C=D.course,KEY='hrl-course:'+D.key;
var lessons=[];C.phases.forEach(function(p){p.lessons.forEach(function(l){l.index=lessons.length;l.phase=p.title;lessons.push(l);});});
var host=null,embedded=window.parent!==window,S=load(),navOpen=false,hlSrc=null;
function fresh(){return{done:{},ans:{},note:{},test:null,view:'home'};}
function load(){try{var r=localStorage.getItem(KEY);return r?Object.assign(fresh(),JSON.parse(r)):fresh();}catch(e){return fresh();}}
function save(){try{localStorage.setItem(KEY,JSON.stringify(S));}catch(e){}}
function post(m){if(!embedded)return;try{window.parent.postMessage(Object.assign({source:'hrl-course',course:D.key},m),'*');}catch(e){}}
function h(tag,attrs){var e=document.createElement(tag);attrs=attrs||{};for(var k in attrs){var v=attrs[k];if(v==null||v===false)continue;if(k==='class')e.className=v;else if(k==='html')e.innerHTML=v;else if(k.slice(0,2)==='on')e.addEventListener(k.slice(2),v);else e.setAttribute(k,v===true?'':v);}
for(var i=2;i<arguments.length;i++)add(e,arguments[i]);return e;}
function add(e,c){if(c==null||c===false)return;if(Array.isArray(c)){c.forEach(function(x){add(e,x);});return;}e.appendChild(typeof c==='object'?c:document.createTextNode(String(c)));}
function done(l){return !!S.done[l.id];}
function doneCount(){return lessons.filter(done).length;}
function percent(){return lessons.length?Math.round(100*doneCount()/lessons.length):0;}
function allDone(){return doneCount()===lessons.length;}
function setDone(l,v){if(!!S.done[l.id]===v)return;if(v)S.done[l.id]=true;else delete S.done[l.id];save();post({type:'hrl-course-progress',index:l.index,lessonId:l.id,completed:v,done:doneCount(),total:lessons.length,percent:percent()});}
window.addEventListener('message',function(ev){var m=ev.data;if(ev.source!==window.parent||!m||m.type!=='hrl-course-init')return;host=m.host||'nova';
if(Array.isArray(m.completed)){m.completed.forEach(function(i){if(lessons[i])S.done[lessons[i].id]=true;});}save();render();});
function go(view){S.view=view;save();navOpen=false;render();var m=document.getElementById('main');if(m){m.focus({preventScroll:true});}window.scrollTo(0,0);}
function nextOpen(){for(var i=0;i<lessons.length;i++)if(!done(lessons[i]))return i;return -1;}
function levelName(){return L[C.level]||C.level;}

function renderNav(){var n=h('nav',{id:'nav','aria-label':L.position,class:navOpen?'open':''});
n.appendChild(h('h2',null,L.position));
n.appendChild(navBtn(L.start,'home',false,S.view==='home'));
C.phases.forEach(function(p){n.appendChild(h('h2',null,p.title));p.lessons.forEach(function(l){
var cur=S.view==='lesson:'+l.index;n.appendChild(navBtn(l.title,'lesson:'+l.index,done(l),cur,l.minutes+' '+L.minutes));});});
n.appendChild(h('h2',null,L.test));n.appendChild(navBtn(L.test,'test',!!(S.test&&S.test.passed),S.view==='test',null,false));
n.appendChild(h('h2',null,L.sources));n.appendChild(navBtn(L.sources,'sources',false,S.view==='sources'));
if(!embedded)n.appendChild(h('p',{class:'note'},h('button',{class:'btn ghost',style:'font-size:.8rem;min-height:36px;padding:.3rem .8rem',onclick:function(){if(confirm(L.reset_confirm)){S=fresh();save();render();}}},L.reset)));
return n;}
function navBtn(label,view,isDone,isCur,meta,disabled){var b=h('button',{class:'n',type:'button','aria-current':isCur?'page':null,disabled:disabled?true:null,onclick:function(){go(view);}},
h('span',{class:'dot'+(isDone?' done':''),'aria-hidden':'true'},isDone?'✓':''),h('span',null,label,meta?h('span',{class:'note'},' · '+meta):null));return b;}

function renderTop(){return h('header',{class:'top'},h('button',{class:'btn ghost menu',type:'button','aria-expanded':String(navOpen),'aria-controls':'nav',onclick:function(){navOpen=!navOpen;render();}},L.menu),
h('h1',null,C.title),h('div',{class:'bar',role:'progressbar','aria-valuemin':'0','aria-valuemax':'100','aria-valuenow':String(percent()),'aria-label':L.progress},h('i',{style:'width:'+percent()+'%'})),h('span',{class:'pct'},host==='nova'?doneCount()+' '+L.of+' '+lessons.length+' '+L.lessons_gen:L.progress+' '+percent()+'%'));}

function viewHome(){var f=document.createDocumentFragment(),i=nextOpen();
var hero=h('div',{class:'hero',style:D.cover?'background-image:linear-gradient(135deg,rgba(0,0,0,.55),rgba(0,0,0,.25)),url('+D.cover+')':null},h('div',{class:'eyebrow',style:'color:inherit;opacity:.85'},C.subtitle||''),h('h2',null,C.title),h('p',null,C.summary),
h('div',{class:'chips'},h('span',{class:'chip'},L.level+': '+levelName()),h('span',{class:'chip'},lessons.length+' '+L.lessons.toLowerCase()),h('span',{class:'chip'},'≈ '+C.minutes+' '+L.minutes)));
f.appendChild(hero);
if(C.outcomes.length){f.appendChild(h('div',{class:'card'},h('h3',{style:'margin-top:0'},L.learn),h('ul',null,C.outcomes.map(function(o){return h('li',null,o);}))));}
f.appendChild(h('div',{class:'card soft'},h('strong',null,L.how),h('p',{style:'margin:.3rem 0 0'},L.how_text)));
if(allDone()){f.appendChild(h('div',{class:'banner',role:'status'},host==='nova'?L.congrats_nova:L.congrats));}
f.appendChild(h('div',{class:'row'},h('button',{class:'btn',type:'button',onclick:function(){go(i<0?'test':'lesson:'+i);}},doneCount()===0?L.begin:(i<0?L.test:L.continue))));
if(C.disclaimer){f.appendChild(h('p',{class:'note'},h('strong',null,L.note+': '),C.disclaimer));}
f.appendChild(h('p',{class:'note'},L.ai_note));return f;}

function viewLesson(l){var f=document.createDocumentFragment();
f.appendChild(h('div',{class:'eyebrow'},l.phase+' · '+L.lesson+' '+(l.index+1)+' '+L.of+' '+lessons.length+' · '+l.minutes+' '+L.minutes));
f.appendChild(h('h2',null,l.title));
if(done(l))f.appendChild(h('div',{class:'banner',role:'status'},'✓ '+L.lesson_done));
if(l.objectives.length)f.appendChild(h('div',{class:'card soft'},h('strong',null,L.objectives),h('ul',null,l.objectives.map(function(o){return h('li',null,o);}))));
l.sections.forEach(function(s){if(s.heading)f.appendChild(h('h3',null,s.heading));f.appendChild(h('div',{html:s.html}));});
if(l.example){f.appendChild(h('div',{class:'card'},h('strong',null,L.example+(l.example.title?': '+l.example.title:'')),h('div',{html:l.example.html})));}
if(l.exercise)f.appendChild(exerciseBlock(l));
f.appendChild(quizBlock(l));
if(l.takeaways.length)f.appendChild(h('div',{class:'card soft'},h('strong',null,L.takeaways),h('ul',null,l.takeaways.map(function(t){return h('li',null,t);}))));
if(l.sources.length){var sp=h('p',{class:'note'},L.sources_used+': ');l.sources.forEach(function(n){sp.appendChild(h('a',{class:'pill',href:'#','data-src':'S'+n,onclick:function(e){e.preventDefault();hlSrc=n;go('sources');}},'['+n+'] '+((C.sources.filter(function(s){return s.n===n;})[0]||{}).title||'').slice(0,40)));});f.appendChild(sp);}
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

function quizBlock(l){var box=h('div',{class:'card'}),a=S.ans[l.id]=S.ans[l.id]||[];
function draw(){box.innerHTML='';box.appendChild(h('strong',null,L.quiz));
l.quiz.forEach(function(q,qi){var qd=h('div',{class:'q'},h('p',{class:'t'},(qi+1)+'. '+q.q)),chosen=a[qi];
q.options.forEach(function(o,oi){var cls='opt'+(chosen!=null?(oi===q.correct?' right':(oi===chosen?' wrong':'')):'');
qd.appendChild(h('button',{class:cls,type:'button',disabled:chosen!=null?true:null,'aria-pressed':chosen===oi?'true':'false',onclick:function(){a[qi]=oi;save();finish();draw();}},o));});
if(chosen!=null){qd.appendChild(h('p',{class:'fb '+(chosen===q.correct?'ok':'no'),role:'status'},h('strong',null,(chosen===q.correct?L.correct:L.wrong)+' '),q.explanation));}
box.appendChild(qd);});
var n=a.filter(function(x){return x!=null;}).length,right=l.quiz.filter(function(q,i){return a[i]===q.correct;}).length;
if(n<l.quiz.length)box.appendChild(h('p',{class:'note'},L.quiz_left+' ('+n+'/'+l.quiz.length+')'));
else{box.appendChild(h('p',null,h('strong',null,L.score+': '+right+'/'+l.quiz.length)));box.appendChild(h('button',{class:'btn ghost',type:'button',onclick:function(){S.ans[l.id]=a=[];save();draw();}},L.retry));}}
function finish(){if(a.filter(function(x){return x!=null;}).length===l.quiz.length){setDone(l,true);refreshChrome();}}
draw();return box;}

function viewTest(){var f=document.createDocumentFragment();f.appendChild(h('h2',null,L.test));
if(!allDone()){f.appendChild(h('div',{class:'card soft',role:'status'},L.test_locked));return f;}
if(host==='nova'){f.appendChild(h('div',{class:'card soft'},L.nova_test));f.appendChild(h('div',{class:'row'},h('button',{class:'btn',type:'button',onclick:function(){post({type:'hrl-course-open-test'});}},L.open_nova_test)));return f;}
f.appendChild(h('p',null,L.test_intro));var T=S.test||{a:[],passed:false,submitted:false},box=h('div');f.appendChild(box);
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
var main=h('main',{id:'main',tabindex:'-1'});var v=S.view,m=/^lesson:(\d+)$/.exec(v);
main.appendChild(m&&lessons[+m[1]]?viewLesson(lessons[+m[1]]):v==='test'?viewTest():v==='sources'?viewSources():viewHome());
app.appendChild(h('div',{class:'layout'},renderNav(),main));}
render();
if(embedded)post({type:'hrl-course-ready',total:lessons.length,done:doneCount()});
})();
"""
