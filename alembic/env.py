"""Alembic migrations environment."""
import os
import sys
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL:
    config.set_main_option("sqlalchemy.url", DATABASE_URL)

target_metadata = None


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        print("No DATABASE_URL set — skipping migrations (using JSON fallback)")
        return
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        print("No DATABASE_URL set — skipping migrations (using JSON fallback)")
        return
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
