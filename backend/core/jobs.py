"""Job storage — PostgreSQL with automatic fallback to JSON file."""
import logging

logger = logging.getLogger(__name__)

# Try PostgreSQL first
try:
    from backend.core.database import create_job, update_job, get_job, init_db, get_all_jobs, count_jobs, delete_job, fail_stale_jobs  # noqa: F401
    logger.info("Using PostgreSQL for job storage")
except Exception as e:
    logger.warning(f"PostgreSQL not available, using JSON fallback: {e}")
    from backend.core.jobs_fallback import create_job, update_job, get_job, get_all_jobs, count_jobs, delete_job, fail_stale_jobs  # noqa: F401
