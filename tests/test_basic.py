"""Basic tests for core modules."""
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.jobs_fallback import create_job, update_job, get_job, get_all_jobs, delete_job
from backend.themes import get_theme, list_themes, generate_theme_css


def test_create_job():
    jid = create_job("minimal", "ebook", "general", "professional", "5", "ai", "English")
    assert jid and len(jid) > 10
    job = get_job(jid)
    assert job is not None
    assert job["status"] == "queued"
    assert job["style"] == "minimal"
    delete_job(jid)


def test_update_job():
    jid = create_job("modern")
    update_job(jid, "processing", 50)
    job = get_job(jid)
    assert job["status"] == "processing"
    assert job["progress"] == 50
    update_job(jid, "done", 100, topic="AI")
    job = get_job(jid)
    assert job["status"] == "done"
    assert job["topic"] == "AI"
    delete_job(jid)


def test_get_all_jobs():
    jid1 = create_job("minimal")
    jid2 = create_job("dark")
    jobs = get_all_jobs()
    ids = [j["id"] for j in jobs]
    assert jid1 in ids
    assert jid2 in ids
    delete_job(jid1)
    delete_job(jid2)


def test_themes():
    themes = list_themes()
    assert len(themes) >= 20
    minimal = get_theme("minimal")
    assert minimal["colors"]["accent"] == "#4A4A4A"
    css = generate_theme_css("minimal")
    assert "--color-accent: #4A4A4A" in css


def test_theme_registry_consistency():
    """Every listed theme must resolve to itself (no silent fallback to
    'minimal') and expose a complete, well-formed color palette.

    Regression test for a bug where 5 themes had cover-icon entries but no
    actual templates/themes/<name>/theme.css, so get_theme() silently
    returned "minimal" instead of raising or 404ing.
    """
    required_colors = {
        "background", "surface", "text", "heading", "accent",
        "secondary", "muted", "border", "highlight",
        "success", "warning", "error", "info",
    }
    for summary in list_themes():
        theme_id = summary["id"]
        theme = get_theme(theme_id)
        assert theme["id"] == theme_id, f"get_theme({theme_id!r}) silently fell back to {theme['id']!r}"
        assert required_colors.issubset(theme["colors"].keys()), f"{theme_id} missing color keys: {required_colors - theme['colors'].keys()}"


def test_theme_fallback():
    theme = get_theme("nonexistent")
    assert theme["id"] == "minimal"


if __name__ == "__main__":
    test_create_job()
    print("OK test_create_job")
    test_update_job()
    print("OK test_update_job")
    test_get_all_jobs()
    print("OK test_get_all_jobs")
    test_themes()
    print("OK test_themes")
    test_theme_registry_consistency()
    print("OK test_theme_registry_consistency")
    test_theme_fallback()
    print("OK test_theme_fallback")
    print("\nAll tests passed")
