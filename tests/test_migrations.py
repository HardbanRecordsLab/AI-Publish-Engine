"""Regression test for the Alembic migration baseline.

alembic/versions used to be a plain *file* (containing the text "versions
directory for Alembic migrations") instead of a directory, so `alembic
upgrade head` / init_db() were always a silent no-op — the production
Postgres schema exists only because someone created it by hand once,
and could not be reproduced from this repo. This test runs the real
migration against a throwaway SQLite database and asserts the resulting
schema matches what backend/core/database.py and backend/routers/auth.py
actually query.
"""
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

REPO_ROOT = Path(__file__).parent.parent


def test_versions_is_a_directory():
    versions_path = REPO_ROOT / "alembic" / "versions"
    assert versions_path.is_dir(), (
        "alembic/versions must be a directory, not a file — "
        "if it's a file again, `alembic upgrade head` silently does nothing"
    )


def test_baseline_migration_creates_expected_schema(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config

    db_path = tmp_path / "migration_smoke.db"
    # alembic/env.py reads DATABASE_URL from the environment and, if set,
    # uses it in preference to whatever sqlalchemy.url is set on the Config
    # object below — so this must override the env var too, not just the
    # Config, or a real DATABASE_URL loaded from .env by an earlier test
    # (via database.py's load_dotenv()) silently wins and this test tries
    # to migrate the real production database.
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    alembic_cfg = Config(str(REPO_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    alembic_cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))

    command.upgrade(alembic_cfg, "head")
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}
        assert {"jobs", "admins"}.issubset(tables)

        job_columns = {row[1] for row in cur.execute("PRAGMA table_info(jobs)")}
        # every column backend/core/database.py's update_job()/get_job() reads or writes
        expected_job_columns = {
            "id", "status", "progress", "style", "content_type", "audience", "tone",
            "chapters", "keywords", "language", "created_at", "updated_at",
            "output_path", "epub_path", "docx_path", "html", "website_path",
            "error", "topic", "book_data", "build_params",
        }
        assert expected_job_columns.issubset(job_columns)

        admin_columns = {row[1] for row in cur.execute("PRAGMA table_info(admins)")}
        assert {"email", "password_hash"}.issubset(admin_columns)
        conn.close()
    finally:
        command.downgrade(alembic_cfg, "base")


def test_downgrade_cleanly_removes_both_tables(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config

    db_path = tmp_path / "migration_downgrade.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    alembic_cfg = Config(str(REPO_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    alembic_cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))

    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "base")

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    conn.close()
    assert "jobs" not in tables
    assert "admins" not in tables
