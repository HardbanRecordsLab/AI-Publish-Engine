"""Publish a finished interactive course to HRL Nova Campus.

Nova receives the single-file course (HOSTED_HTML), the lesson list (what the learner ticks off by finishing each lesson's quiz) and
the graded final test (single choice, 70% to pass, which is what issues the certificate). A course is created as a DRAFT unless the
caller asks for PUBLISHED: putting something in front of learners is the author's decision. Publishing the same job again updates the
same Nova course (the key is derived from the job id), so learners' saved progress survives a corrected version.

Configuration (environment): NOVA_API_URL (e.g. http://127.0.0.1:3002, Nova runs on the same server), NOVA_SERVICE_KEY (shared secret,
checked by Nova's /api/service/interactive-courses), NOVA_PUBLIC_URL (for the link in the answer).
"""
from __future__ import annotations

import os
import re

import httpx

from backend.core.course_engine import cover_data_uri

DEFAULT_PUBLIC_URL = "https://nova-campus.hardbanrecordslab.online"


class NovaPublishError(RuntimeError):
    pass


def source_key(job_id: str) -> str:
    return ("aip-" + re.sub(r"[^a-z0-9]+", "-", str(job_id).lower()).strip("-"))[:80]


def nova_payload(job_id: str, course: dict, html: str, status: str = "DRAFT") -> dict:
    lessons = [l for p in course["phases"] for l in p["lessons"]]
    day = {"pl": "Dzień", "en": "Day"}.get(course.get("language") or "", "Day") if course.get("format") == "program" else ""
    outcomes = course.get("outcomes") or []
    description = course["summary"] + ((" Po kursie: " if course.get("language") == "pl" else " After the course you can: ") + "; ".join(outcomes[:3]) + ".") if outcomes else course["summary"]
    return {
        "source_key": source_key(job_id), "title": course["title"], "description": description[:2000], "language": course.get("language") or "pl",
        "level": course.get("level") or "beginner", "thumbnail": cover_data_uri(course), "html": html,
        "stages": [(f"{day} {i}: {l['title']}" if day else l["title"])[:200] for i, l in enumerate(lessons, 1)],
        "test": [{"question": q["q"][:500], "options": [o[:300] for o in q["options"]], "correct": q["correct"]} for q in course["final_test"]],
        "minutes": int(course.get("minutes") or 0) or None, "status": "PUBLISHED" if str(status).upper() == "PUBLISHED" else "DRAFT",
    }


def publish_course(job_id: str, course: dict, html: str, status: str = "DRAFT", *, client: httpx.Client | None = None) -> dict:
    base = (os.getenv("NOVA_API_URL") or "").rstrip("/")
    key = os.getenv("NOVA_SERVICE_KEY") or ""
    if not base or not key:
        raise NovaPublishError("Publishing to Nova is not configured (NOVA_API_URL and NOVA_SERVICE_KEY are missing in the server environment).")
    payload = {k: v for k, v in nova_payload(job_id, course, html, status).items() if v is not None}
    try:
        r = (client or httpx).post(base + "/api/service/interactive-courses", json=payload, headers={"x-service-key": key}, timeout=60)
    except httpx.HTTPError as e:
        raise NovaPublishError(f"Nova could not be reached: {e}") from e
    try:
        data = r.json()
    except ValueError:
        data = {}
    if r.status_code not in (200, 201):
        raise NovaPublishError(f"Nova refused the course ({r.status_code}): {str(data.get('message') or r.text)[:300]}")
    public = (os.getenv("NOVA_PUBLIC_URL") or DEFAULT_PUBLIC_URL).rstrip("/")
    return {"course_id": data["course_id"], "created": bool(data.get("created")), "status": data.get("status"), "lessons": data.get("lessons"),
            "test_questions": data.get("test_questions"), "url": f"{public}/course/{data['course_id']}"}
