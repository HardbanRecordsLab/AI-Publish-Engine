"""PostgreSQL connection manager for job storage."""
import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
import psycopg2.pool
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "")

_pool = None


def get_pool():
    global _pool
    if _pool is None:
        try:
            _pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1, maxconn=5, dsn=DATABASE_URL,
            )
            logger.info(f"PostgreSQL pool created ({DATABASE_URL[:40]}...)")
        except Exception as e:
            logger.warning(f"PostgreSQL pool failed: {e}")
            _pool = None
    return _pool


@contextmanager
def get_conn():
    pool = get_pool()
    if pool is None:
        raise RuntimeError("No database pool available")
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def init_db():
    """Run Alembic migrations. Falls back to JSON storage if no DB URL."""
    if not DATABASE_URL:
        return False
    try:
        from alembic.config import Config

        from alembic import command
        alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini"))
        alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations complete")
        return True
    except Exception as e:
        logger.warning(f"Database init failed: {e}")
        return False


def create_job(style="minimal", content_type="ebook", audience="", tone="", chapters="", keywords="", language=""):
    import uuid
    from datetime import datetime
    job_id = str(uuid.uuid4())
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO jobs (id, status, progress, style, content_type, audience, tone, chapters, keywords, language, created_at)
                       VALUES (%s, 'queued', 0, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (job_id, style, content_type, audience, tone, chapters, keywords, language, datetime.now()),
                )
    except Exception as e:
        logger.warning(f"create_job DB failed: {e}, falling back to memory")
        from backend.core.jobs_fallback import create_job as fb
        return fb(style, content_type, audience, tone, chapters, keywords, language)
    return job_id


def update_job(job_id, status, progress=None, output_path=None, epub_path=None, docx_path=None,
               html=None, website_path=None, error=None, topic=None,
               book_data=None, build_params=None):
    if not job_id:
        return
    try:
        with get_conn() as conn, conn.cursor() as cur:
            sets = ["status = %s", "updated_at = NOW()"]
            params = [status]
            if progress is not None:
                sets.append("progress = %s")
                params.append(progress)
            if output_path is not None:
                sets.append("output_path = %s")
                params.append(output_path)
            if epub_path is not None:
                sets.append("epub_path = %s")
                params.append(epub_path)
            if docx_path is not None:
                sets.append("docx_path = %s")
                params.append(docx_path)
            if html is not None:
                sets.append("html = %s")
                params.append(html)
            if website_path is not None:
                sets.append("website_path = %s")
                params.append(website_path)
            if error is not None:
                sets.append("error = %s")
                params.append(error)
            if topic is not None:
                sets.append("topic = %s")
                params.append(topic)
            if book_data is not None:
                sets.append("book_data = %s")
                params.append(book_data)
            if build_params is not None:
                sets.append("build_params = %s")
                params.append(build_params)
            params.append(job_id)
            cur.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id = %s", params)
    except Exception as e:
        logger.warning(f"update_job DB failed: {e}")
        from backend.core.jobs_fallback import update_job as fb
        fb(job_id, status, progress, output_path, epub_path, docx_path, html, website_path, error, topic, book_data, build_params)


def get_job(job_id):
    if not job_id:
        return None
    try:
        with get_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM jobs WHERE id = %s", (job_id,))
            row = cur.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logger.warning(f"get_job DB failed: {e}")
        from backend.core.jobs_fallback import get_job as fb
        return fb(job_id)


def get_all_jobs(offset: int = 0, limit: int = 50):
    try:
        with get_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT %s OFFSET %s", (limit, offset))
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"get_all_jobs DB failed: {e}")
        from backend.core.jobs_fallback import get_all_jobs as fb
        return fb(offset, limit)


def count_jobs():
    """Return total job count for pagination."""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM jobs")
            return cur.fetchone()[0]
    except Exception as e:
        logger.warning(f"count_jobs DB failed: {e}")
        return len(get_all_jobs())


def delete_job(job_id):
    if not job_id:
        return
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
    except Exception as e:
        logger.warning(f"delete_job DB failed: {e}")
        from backend.core.jobs_fallback import delete_job as fb
        fb(job_id)


def fail_stale_jobs(timeout_minutes: int):
    """Mark jobs stuck in 'queued'/'processing' with no update for too long as failed.

    Returns the list of job ids that were marked failed. This protects against
    jobs left forever spinning when the worker thread/process dies mid-job
    (e.g. server restart, deploy, crash) without ever writing an error.
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE jobs SET status = 'failed',
                           error = 'Przekroczono limit czasu — proces prawdopodobnie został przerwany (np. restart serwera).',
                           updated_at = NOW()
                       WHERE status IN ('queued', 'processing')
                         AND updated_at < NOW() - (%s || ' minutes')::interval
                       RETURNING id""",
                    (timeout_minutes,),
                )
                ids = [row[0] for row in cur.fetchall()]
                return ids
    except Exception as e:
        logger.warning(f"fail_stale_jobs DB failed: {e}")
        from backend.core.jobs_fallback import fail_stale_jobs as fb
        return fb(timeout_minutes)


# Try to init on import
init_db()
