"""Job storage — PostgreSQL with automatic fallback to JSON file."""
import logging

logger = logging.getLogger(__name__)

# Try PostgreSQL first
try:
    from backend.core.database import (  # noqa: F401
        count_jobs,
        create_job,
        delete_job,
        fail_stale_jobs,
        get_all_jobs,
        get_job,
        init_db,
        update_job,
    )
    logger.info("Using PostgreSQL for job storage")
except Exception as e:
    logger.warning(f"PostgreSQL not available, using JSON fallback: {e}")
    from backend.core.jobs_fallback import (  # noqa: F401
        count_jobs,
        create_job,
        delete_job,
        fail_stale_jobs,
        get_all_jobs,
        get_job,
        update_job,
    )
