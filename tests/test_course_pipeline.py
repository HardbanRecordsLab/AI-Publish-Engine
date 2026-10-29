"""Interactive course pipeline: web research, course generation checks, HTML engine, agents (no network, no real model)."""
import json
import re
import socket

import pytest

from backend.agents import course_agents
from backend.core import course_engine, course_gen, webresearch
from backend.orchestrator.agent import PipelineContext

PARA = ("Webhooks let one application tell another that something happened, the moment it happens, instead of the other side asking again and again. "
        "A sender posts a small message to an address the receiver published; the receiver checks who sent it, answers quickly and does the heavy work afterwards. ")


def good_lesson(n: int, extra_cite: str = "S1") -> dict:
    def q(i):
        return {"q": f"Lesson {n} question {i}?", "options": [f"right {i}", f"wrong a{i}", f"wrong b{i}", f"wrong c{i}"], "correct": 0,
                "explanation": f"Because right {i} is what the lesson says [{extra_cite}]."}
    return {"title": f"Lesson {n}", "minutes": 20, "objectives": ["Explain the idea", "Use it in a small task"],
            "sections": [{"heading": "Idea", "body": PARA * 3 + f"A fact from the web [{extra_cite}]."}, {"heading": "Detail", "body": "- point one\n- point two\n\n" + PARA * 2}],
            "example": {"title": "Worked example", "body": PARA + "Here is how the steps look when you do them for real in a small project."},
            "exercise": {"prompt": "Write down three events in your own project that should trigger a webhook and why.", "hint": "Think about what changes.",
                         "model_answer": "A good answer names concrete events such as an order paid, and says who needs to know and how fast."},
            "quiz": [q(1), q(2), q(3)], "test_pool": [q(4), q(5)], "takeaways": ["Push beats polling", "Verify the sender"], "sources": [extra_cite]}


def fake_llm(calls=None, bad_first_lessons=0):
    state = {"lesson_calls": 0}

    def llm(system, user, max_tokens=6000):
        if calls is not None:
            calls.append(system[:30])
        if "plan web research" in system:
            return {"queries": ["webhooks explained", "webhook security", "api polling vs webhooks"]}
        if "instructional designer" in system:
            m = re.search(r"exactly (\d+) lessons", user)
            n = int(m.group(1))
            phases = []
            per = max(1, n // 2)
            for pi in range(2):
                phases.append({"title": f"Phase {pi + 1}", "summary": "s", "lessons": [{"title": f"Topic {pi * per + i + 1}", "goal": "g", "source_hints": ["S1", "S9"]}
                                                                                       for i in range(per if pi == 0 else n - per)]})
            return {"title": "Webhooks in practice", "subtitle": "From zero to production", "summary": "You learn webhooks.", "level": "beginner",
                    "sensitive": False, "outcomes": ["Explain webhooks", "Build one"], "phases": phases}
        if "writing one lesson" in system:
            state["lesson_calls"] += 1
            if state["lesson_calls"] <= bad_first_lessons:
                return {"title": "thin", "sections": [{"heading": "x", "body": "too short"}], "quiz": []}
            n = int(re.search(r"Lesson (\d+) of", user).group(1))
            return good_lesson(n)
        raise AssertionError("unexpected prompt: " + system[:60])
    return llm


def src(i=1, text="x" * 600, provider="wikipedia"):
    return webresearch.Source(f"S{i}", f"Source {i}", f"https://example.org/{i}", text, provider, "CC BY-SA 4.0")


# ------------------------------------------------------------------ web research

def test_urls_are_checked_for_public_addresses(monkeypatch):
    for bad in ("http://127.0.0.1/x", "http://10.1.2.3/", "http://169.254.169.254/latest/meta-data", "http://[::1]/", "file:///etc/passwd",
                "ftp://example.org/", "http://192.168.0.5:80/", "https://example.org:8443/"):
        with pytest.raises(webresearch.UnsafeURL):
            webresearch.check_public_url(bad)
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))])
    assert webresearch.check_public_url("https://example.org/page") == "https://example.org/page"
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.7", port))])
    with pytest.raises(webresearch.UnsafeURL):
        webresearch.check_public_url("https://sneaky.example.org/")   # public name, private address


def test_fetch_refuses_redirect_into_private_network(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (host if host[0].isdigit() else "93.184.216.34", port))])
    monkeypatch.setattr(webresearch, "_robots_allows", lambda url: True)

    class Resp:
        status_code, headers, encoding = 302, {"location": "http://169.254.169.254/latest/meta-data"}, "utf-8"
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def iter_bytes(self): return iter([])
    monkeypatch.setattr(webresearch.httpx, "stream", lambda *a, **k: Resp())
    assert webresearch.fetch_page("https://example.org/redirect") is None


def test_readable_text_drops_scripts_and_navigation():
    title, text = webresearch._readable("<html><head><title>Hi there</title><script>evil()</script></head><body><nav>menu menu</nav>"
                                         "<article><h1>Real</h1><p>Content   here.</p></article><footer>foot</footer></body></html>")
    assert title == "Hi there" and "evil" not in text and "menu" not in text and text.startswith("Real Content here.")


def test_urls_in_brief_and_abstract_rebuild():
    assert webresearch.urls_in("see https://a.org/x, and (https://b.org/y). again https://a.org/x") == ["https://a.org/x", "https://b.org/y"]
    assert webresearch._abstract({"world": [1], "hello": [0]}) == "hello world"


def test_gather_sources_merges_dedupes_and_survives_a_failing_provider(monkeypatch):
    def good(q, lang):
        return [webresearch.Hit(f"T {q}", "https://a.org/1", "s" * 700, "wikipedia"), webresearch.Hit("Other", "https://www.b.org/2/", "t" * 700, "wikipedia"),
                webresearch.Hit("Thin", "https://c.org/3", "short", "brave")]

    def boom(q, lang):
        raise RuntimeError("quota")
    monkeypatch.setattr(webresearch, "PROVIDERS", [("brave", boom), ("wikipedia", good)])
    monkeypatch.setattr(webresearch, "active_providers", lambda: ["brave", "wikipedia"])
    monkeypatch.setattr(webresearch, "fetch_page", lambda url, **k: ("Fetched", "f" * 900) if "c.org" in url else None)
    out = webresearch.gather_sources(["one", "two"], "en", max_sources=5)
    assert [s.id for s in out] == ["S1", "S2", "S3"]
    assert [s.url for s in out] == ["https://a.org/1", "https://www.b.org/2/", "https://c.org/3"]
    assert out[2].title == "Thin" and len(out[2].text) == 900     # thin snippet replaced by the page text
    assert set(out[0].public()) == {"id", "title", "url", "license"}   # raw page text never goes into the course


def test_author_urls_are_read_first(monkeypatch):
    monkeypatch.setattr(webresearch, "PROVIDERS", [("wikipedia", lambda q, l: [webresearch.Hit("W", "https://w.org/1", "w" * 700, "wikipedia")])])
    monkeypatch.setattr(webresearch, "active_providers", lambda: ["wikipedia"])
    monkeypatch.setattr(webresearch, "fetch_page", lambda url, **k: ("Author page", "a" * 800))
    out = webresearch.gather_sources(["q"], "en", user_urls=["https://author.org/material"])
    assert out[0].url == "https://author.org/material" and out[0].provider == "author"


# ------------------------------------------------------------------ course generation

def test_questions_are_validated_and_shuffled_without_losing_the_answer():
    items = [
        {"q": "ok", "options": ["a", "b", "c", "d"], "correct": 2, "explanation": "because [S1] and [S9]"},
        {"q": "letter", "options": ["a", "b", "c", "d"], "correct": "B", "explanation": "e"},
        {"q": "by text", "options": ["a", "b", "c", "d"], "answer": "d", "explanation": "e"},
        {"q": "three options", "options": ["a", "b", "c"], "correct": 0, "explanation": "e"},
        {"q": "dupes", "options": ["a", "a", "b", "c"], "correct": 0, "explanation": "e"},
        {"q": "no explanation", "options": ["a", "b", "c", "d"], "correct": 0, "explanation": " "},
        {"q": "bad index", "options": ["a", "b", "c", "d"], "correct": 7, "explanation": "e"},
        "garbage",
    ]
    import random
    out = course_gen.normalize_questions(items, {"S1"}, rng=random.Random(1))
    assert [q["q"] for q in out] == ["ok", "letter", "by text"]
    assert out[0]["explanation"] == "because [S1] and "          # unknown source marker removed
    assert out[0]["options"][out[0]["correct"]] == "c" and out[1]["options"][out[1]["correct"]] == "b" and out[2]["options"][out[2]["correct"]] == "d"
    assert all(len(q["options"]) == 4 for q in out)


def test_five_options_keep_the_correct_one():
    out = course_gen.normalize_questions([{"q": "q", "options": ["a", "b", "c", "d", "e"], "correct": 4, "explanation": "e"}], set())
    assert len(out[0]["options"]) == 4 and out[0]["options"][out[0]["correct"]] == "e"


def test_thin_lesson_is_reported_and_good_lesson_passes():
    spec = {"title": "T", "goal": "g"}
    _, problems = course_gen.normalize_lesson({"title": "x", "sections": [{"heading": "h", "body": "tiny"}], "quiz": []}, spec, 0, {"S1"})
    assert any("explanation too thin" in p for p in problems) and any("quiz" in p for p in problems) and any("exercise" in p for p in problems)
    lesson, problems = course_gen.normalize_lesson(good_lesson(1), spec, 0, {"S1"})
    assert problems == [] and len(lesson["quiz"]) == 3 and lesson["sources"] == ["S1"] and lesson["id"] == "l1"


def test_a_thin_lesson_is_rewritten_once_then_accepted():
    outline = {"title": "C", "level": "beginner", "phases": [{"lessons": [{"title": "Topic 1"}]}], "_brief": "b"}
    lesson = course_gen.write_lesson(fake_llm(bad_first_lessons=1), outline, {"title": "Topic 1", "goal": "g", "source_hints": ["S1"]}, 0, 1, [src(1)], language="English", tone="")
    assert lesson["title"] == "Lesson 1" and len(lesson["quiz"]) == 3


def test_a_lesson_that_stays_thin_fails_the_job():
    outline = {"title": "C", "level": "beginner", "phases": [{"lessons": [{"title": "Topic 1"}]}], "_brief": "b"}
    with pytest.raises(course_gen.CourseGenerationError, match="could not be written well enough"):
        course_gen.write_lesson(fake_llm(bad_first_lessons=5), outline, {"title": "Topic 1", "goal": "g"}, 0, 1, [src(1)], language="English", tone="")


def test_outline_needs_enough_lessons_and_ignores_unknown_sources():
    llm = lambda s, u, m: {"title": "T", "phases": [{"title": "P", "lessons": [{"title": "only one", "source_hints": ["S1", "S77"]}]}]}
    with pytest.raises(course_gen.CourseGenerationError):
        course_gen.design_outline(llm, "brief", [src(1)], language="", audience="", tone="", lessons=6)
    ok = course_gen.design_outline(fake_llm(), "brief", [src(1)], language="", audience="", tone="", lessons=6)
    assert sum(len(p["lessons"]) for p in ok["phases"]) == 6 and all(l["source_hints"] == ["S1"] for p in ok["phases"] for l in p["lessons"])


def test_queries_fall_back_to_the_brief_when_the_model_fails():
    def broken(*a):
        raise RuntimeError("down")
    assert course_gen.plan_queries(broken, "--- BOOK BRIEF ---\nWebhooks for shop owners", "en") == [{"q": "Webhooks for shop owners", "lang": "en"}]
    mixed = lambda s, u, m: {"queries": ["plain string", {"q": "dwuskładnikowe uwierzytelnianie", "lang": "pl"}, {"q": "two-factor authentication", "lang": "English"}, {"q": "x"}]}
    assert course_gen.plan_queries(mixed, "brief", "Polish") == [{"q": "plain string", "lang": "pl"}, {"q": "dwuskładnikowe uwierzytelnianie", "lang": "pl"},
                                                                  {"q": "two-factor authentication", "lang": "en"}]


def test_final_test_prefers_the_harder_pool_and_is_reproducible():
    lessons = [course_gen.normalize_lesson(good_lesson(i), {"title": "t"}, i - 1, {"S1"})[0] for i in range(1, 7)]
    t1, t2 = course_gen.build_final_test(lessons, seed="a"), course_gen.build_final_test(lessons, seed="a")
    assert t1 == t2 and len(t1) == 12
    pool_questions = {q["q"] for l in lessons for q in l["test_pool"]}
    assert all(q["q"] in pool_questions for q in t1)


def test_lesson_count_is_clamped():
    assert (course_gen.lesson_count(""), course_gen.lesson_count("2"), course_gen.lesson_count("30"), course_gen.lesson_count("9")) == (8, 4, 14, 9)


# ------------------------------------------------------------------ agents end to end (stub model, stub search)

def make_ctx(**kw):
    base = dict(job_id="job-x", text="--- BOOK BRIEF ---\nWebhooks for shop owners. Read https://author.org/notes too.", style="minimal", content_type="interactive-course",
                language="English", chapters="6")
    base.update(kw)
    return PipelineContext(**base)


def run_pipeline(monkeypatch, llm=None, gather=None):
    monkeypatch.setattr(course_agents, "update_job", lambda *a, **k: None)
    monkeypatch.setattr(course_agents, "is_cancelled", lambda job_id: False)
    ctx = make_ctx()
    for agent in course_agents.course_pipeline(llm or fake_llm(), gather or (lambda qs, lang, user_urls=None: [src(1), src(2, provider="author")])):
        ctx = agent.run(ctx)
    return ctx


def test_pipeline_builds_a_complete_course(monkeypatch):
    seen = {}

    def gather(qs, lang, user_urls=None):
        seen["queries"], seen["urls"] = qs, user_urls
        return [src(1), src(2)]
    ctx = run_pipeline(monkeypatch, gather=gather)
    c = ctx.course
    assert seen["queries"][0] == {"q": "webhooks explained", "lang": "en"} and seen["urls"] == ["https://author.org/notes"]
    assert sum(len(p["lessons"]) for p in c["phases"]) == 6 and len(c["final_test"]) >= 6 and c["language"] == "en"
    assert course_gen.validate_course(c) == [] and {s["id"] for s in c["sources"]} == {"S1"}
    assert ctx.ebook_dict["title"] == "Webhooks in practice" and ctx.progress == 88


def test_pipeline_stops_on_cancel(monkeypatch):
    monkeypatch.setattr(course_agents, "update_job", lambda *a, **k: None)
    monkeypatch.setattr(course_agents, "is_cancelled", lambda job_id: True)
    ctx = make_ctx()
    agents = course_agents.course_pipeline(fake_llm(), lambda *a, **k: [src(1)])
    ctx = agents[0].run(ctx)
    ctx = agents[1].run(ctx)
    with pytest.raises(RuntimeError, match="Cancelled"):
        agents[2].run(ctx)


# ------------------------------------------------------------------ HTML engine

def built(monkeypatch, **kw):
    ctx = run_pipeline(monkeypatch)
    return ctx.course, course_engine.build_course_html(ctx.course, **kw)


def test_engine_page_is_self_contained_and_escapes_model_text(monkeypatch):
    ctx = run_pipeline(monkeypatch)
    c = ctx.course
    c["title"] = 'Evil </script><img src=x onerror=alert(1)> & "quotes"'
    c["phases"][0]["lessons"][0]["sections"][0]["body"] = "Paragraph <script>alert(1)</script> **bold** [S1] and [S99]\n\n- item <b>x</b>"
    page = course_engine.build_course_html(c)
    data_block = page.split('id="course-data">')[1].split("</script>")[0]
    assert "<" not in data_block                                       # JSON blob cannot close the tag
    assert page.count("<script") == 2 and "onerror=alert(1)>" not in page.split("<title>")[1].split("</title>")[0]
    payload = json.loads(data_block)
    first = payload["course"]["phases"][0]["lessons"][0]["sections"][0]["html"]
    assert "<script>" not in first and "&lt;script&gt;" in first and "<strong>bold</strong>" in first and 'data-src="S1"' in first and "S99" not in first
    assert "http" not in page.split("<style>")[0]                      # no external requests: fonts, CDNs, trackers
    assert re.search(r'(src|href)="https?://', page.split('<script>')[-1]) is None


def test_engine_labels_follow_the_course_language(monkeypatch):
    ctx = run_pipeline(monkeypatch)
    ctx.course["language"] = "pl"
    page = course_engine.build_course_html(ctx.course)
    payload = json.loads(page.split('id="course-data">')[1].split("</script>")[0])
    assert payload["labels"]["test"] == "Test końcowy" and '<html lang="pl">' in page


def test_engine_markdown_subset():
    nums = {"S1": 1}
    assert course_engine.md("a\nb\n\n- x\n- y\n\n1. one\n2. two", nums) == "<p>a<br>b</p><ul><li>x</li><li>y</li></ul><ol><li>one</li><li>two</li></ol>"
    assert course_engine.md("see [S1] `code` <i>", nums) == '<p>see <sup class="cite"><a href="#" data-src="S1">[1]</a></sup> <code>code</code> &lt;i&gt;</p>'


def test_cover_is_valid_svg_with_the_title(monkeypatch):
    import xml.dom.minidom
    ctx = run_pipeline(monkeypatch)
    svg = course_engine.course_cover_svg(ctx.course)
    xml.dom.minidom.parseString(svg)
    assert "Webhooks" in svg
    assert course_engine.cover_data_uri(ctx.course).startswith("data:image/svg+xml;base64,")


# ------------------------------------------------------------------ publishing to Nova Campus

def test_nova_payload_follows_the_service_schema(monkeypatch):
    from backend.core import nova_publish
    ctx = run_pipeline(monkeypatch)
    p = nova_publish.nova_payload("Job_ABC 123", ctx.course, "<html>" + "x" * 3000, "published")
    assert re.fullmatch(r"[a-z0-9][a-z0-9-]{5,80}", p["source_key"]) and p["source_key"] == "aip-job-abc-123"
    assert p["status"] == "PUBLISHED" and nova_publish.nova_payload("j", ctx.course, "h", "whatever")["status"] == "DRAFT"
    assert len(p["stages"]) == 6 and 5 <= len(p["test"]) <= 40 and p["thumbnail"].startswith("data:image/svg+xml;base64,")
    assert all(len(q["options"]) == 4 and 0 <= q["correct"] <= 3 for q in p["test"]) and p["level"] == "beginner" and len(p["description"]) >= 10


def test_publish_sends_the_service_key_and_reports_the_course(monkeypatch):
    import httpx
    from backend.core import nova_publish
    ctx = run_pipeline(monkeypatch)
    seen = {}

    def handler(request):
        seen["url"], seen["key"], seen["body"] = str(request.url), request.headers.get("x-service-key"), json.loads(request.content)
        return httpx.Response(201, json={"course_id": "c1", "created": True, "status": "DRAFT", "lessons": 6, "test_questions": 12})
    monkeypatch.setenv("NOVA_API_URL", "http://nova.local:3002/")
    monkeypatch.setenv("NOVA_SERVICE_KEY", "k" * 40)
    out = nova_publish.publish_course("job1", ctx.course, "<html>" + "x" * 3000, client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert seen["url"] == "http://nova.local:3002/api/service/interactive-courses" and seen["key"] == "k" * 40 and seen["body"]["status"] == "DRAFT"
    assert out["course_id"] == "c1" and out["url"].endswith("/course/c1") and out["created"] is True


def test_publish_explains_a_refusal_and_a_missing_configuration(monkeypatch):
    import httpx
    from backend.core import nova_publish
    ctx = run_pipeline(monkeypatch)
    monkeypatch.delenv("NOVA_API_URL", raising=False)
    monkeypatch.delenv("NOVA_SERVICE_KEY", raising=False)
    with pytest.raises(nova_publish.NovaPublishError, match="not configured"):
        nova_publish.publish_course("job1", ctx.course, "<html>")
    monkeypatch.setenv("NOVA_API_URL", "http://nova.local")
    monkeypatch.setenv("NOVA_SERVICE_KEY", "k" * 40)
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(400, json={"message": "Nieprawidłowe dane kursu: html: Too small"})))
    with pytest.raises(nova_publish.NovaPublishError, match=r"refused the course \(400\).*html"):
        nova_publish.publish_course("job1", ctx.course, "<html>", client=client)


# ------------------------------------------------------------------ quality guards found by the first real run

def test_search_hits_that_miss_the_subject_are_dropped(monkeypatch):
    def prov(q, lang):
        return [webresearch.Hit("Welding robots in laboratories", "https://a.org/1", "Technical aspects of laboratory welding robot stations. " * 20, "openalex"),
                webresearch.Hit("Phishing", "https://pl.wikipedia.org/wiki/Phishing", "Phishing to metoda oszustwa, rozpoznawanie phishingu to podstawa. " * 15, "wikipedia")]
    monkeypatch.setattr(webresearch, "PROVIDERS", [("wikipedia", prov)])
    monkeypatch.setattr(webresearch, "active_providers", lambda: ["wikipedia"])
    out = webresearch.gather_sources(["rozpoznawanie phishingu przykłady"], "pl")
    assert [s.title for s in out] == ["Phishing"]
    assert webresearch.relevance("menedżer haseł jak działa", "laboratory welding robots") == 0.0


def test_a_lesson_is_only_offered_sources_that_talk_about_it():
    prompts = []

    def llm(system, user, max_tokens=6000):
        prompts.append(user)
        return good_lesson(1, extra_cite="S2")
    sources = [src(1, text="Technical aspects of laboratory welding robot stations. " * 20), src(2, text="Menedżer haseł przechowuje hasła w szyfrowanym sejfie. " * 20)]
    sources[0].title, sources[1].title = "Welding robots", "Menedżer haseł"
    outline = {"title": "C", "level": "beginner", "phases": [{"lessons": [{"title": "Menedżer haseł"}]}], "_brief": "b"}
    lesson = course_gen.write_lesson(llm, outline, {"title": "Menedżer haseł", "goal": "jak działa menedżer haseł", "source_hints": ["S1", "S2"]}, 0, 1, sources, language="Polish", tone="")
    assert "use only these ids: S2." in prompts[0] and "welding" not in prompts[0] and lesson["sources"] == ["S2"]


def test_json_with_raw_line_breaks_inside_strings_is_accepted():
    from backend.core.ai import _clean_json
    assert _clean_json('```json\n{"body": "first paragraph\n\nsecond paragraph", "n": 2}\n```') == {"body": "first paragraph\n\nsecond paragraph", "n": 2}


def test_lessons_are_written_in_parallel_and_stay_in_order(monkeypatch):
    import threading
    import time
    seen, lock = set(), threading.Lock()
    inner = fake_llm()

    def slow(system, user, max_tokens=6000):
        if "writing one lesson" in system:
            with lock:
                seen.add(threading.current_thread().name)
            time.sleep(0.05)
        return inner(system, user, max_tokens)
    ctx = run_pipeline(monkeypatch, llm=slow)
    titles = [l["title"] for p in ctx.course["phases"] for l in p["lessons"]]
    assert titles == [f"Lesson {i}" for i in range(1, 7)] and len(seen) > 1


def test_each_query_is_searched_in_its_own_language(monkeypatch):
    calls = []

    def prov(q, lang):
        calls.append((q, lang))
        return [webresearch.Hit(q.title(), f"https://w.org/{len(calls)}", f"{q} " * 120, "wikipedia")]
    monkeypatch.setattr(webresearch, "PROVIDERS", [("wikipedia", prov)])
    monkeypatch.setattr(webresearch, "active_providers", lambda: ["wikipedia"])
    out = webresearch.gather_sources([{"q": "uwierzytelnianie dwuskładnikowe", "lang": "pl"}, {"q": "two factor authentication", "lang": "en"}, "plain query"], "de")
    assert calls == [("uwierzytelnianie dwuskładnikowe", "pl"), ("two factor authentication", "en"), ("plain query", "de")] and len(out) == 3


def test_an_encyclopaedia_hit_must_be_about_the_subject(monkeypatch):
    def prov(q, lang):
        return [webresearch.Hit("Rafał Brzoska", "https://pl.wikipedia.org/wiki/RB", "Przedsiębiorca, założyciel firmy, bezpieczeństwo cyfrowe jego firmy. " * 20, "wikipedia"),
                webresearch.Hit("Bezpieczeństwo cyfrowe", "https://pl.wikipedia.org/wiki/BC", "Bezpieczeństwo cyfrowe małej firmy. " * 20, "wikipedia")]
    monkeypatch.setattr(webresearch, "PROVIDERS", [("wikipedia", prov)])
    monkeypatch.setattr(webresearch, "active_providers", lambda: ["wikipedia"])
    out = webresearch.gather_sources(["bezpieczeństwo cyfrowe mała firma"], "pl")
    assert [s.title for s in out] == ["Bezpieczeństwo cyfrowe"]


def test_the_course_lists_only_sources_a_lesson_uses(monkeypatch):
    ctx = run_pipeline(monkeypatch, gather=lambda qs, lang, user_urls=None: [src(1), src(2), src(3)])
    assert [s["id"] for s in ctx.course["sources"]] == ["S1"]          # the stub lessons cite S1 only
    lessons = [l for p in ctx.course["phases"] for l in p["lessons"]]
    for l in lessons:
        l["sources"] = []
    outline = {"title": "t", "subtitle": "", "summary": "", "level": "beginner", "sensitive": False, "outcomes": [],
               "phases": [{"title": "P", "summary": "", "lessons": lessons[:3]}, {"title": "Q", "summary": "", "lessons": lessons[3:]}]}
    assert course_gen.assemble_course(outline, lessons, [src(1), src(2)], language="en")["sources"] == []


def test_json_with_html_escaped_quotes_is_recovered():
    from backend.core.ai import _clean_json
    assert _clean_json('{&quot;title&quot;: &quot;Hasła&quot;, &quot;n&quot;: [1, 2]}') == {"title": "Hasła", "n": [1, 2]}
    with pytest.raises(ValueError):
        _clean_json("no json here")
