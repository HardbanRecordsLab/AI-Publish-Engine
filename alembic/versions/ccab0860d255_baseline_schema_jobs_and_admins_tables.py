"""baseline schema: jobs and admins tables

This is a *baseline* migration: it captures the schema that
backend/core/database.py and backend/routers/auth.py already assume,
reverse-engineered from every column referenced in their SQL (there was
previously no migration that created these tables at all — alembic/versions
was accidentally a placeholder *file*, not a directory, so `alembic upgrade
head` was always silently a no-op; see alembic/versions/.gitkeep).

- Fresh environment (new VPS, CI, local dev): `alembic upgrade head` creates
  both tables from scratch.
- Existing production database (tables already created manually): do NOT
  run `upgrade` — it will fail on the already-existing tables. Instead run
  `alembic stamp head` once to tell Alembic "this schema is already here",
  so *future* migrations apply cleanly on top of it.

Column types/nullability are inferred from usage (e.g. progress is read/
written as an int, updated_at is compared with `NOW() - interval` so it
must never be NULL for an active job). Verify against the real production
schema (`\\d jobs` / `\\d admins` in psql) before relying on this for
disaster recovery, since it was written without access to that database.

Revision ID: ccab0860d255
Revises:
Create Date: 2026-07-25 07:21:50.901483
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'ccab0860d255'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("style", sa.String(length=64)),
        sa.Column("content_type", sa.String(length=64)),
        sa.Column("audience", sa.String(length=256)),
        sa.Column("tone", sa.String(length=64)),
        sa.Column("chapters", sa.String(length=32)),
        sa.Column("keywords", sa.Text()),
        sa.Column("language", sa.String(length=32)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("output_path", sa.Text()),
        sa.Column("epub_path", sa.Text()),
        sa.Column("docx_path", sa.Text()),
        sa.Column("html", sa.Text()),
        sa.Column("website_path", sa.Text()),
        sa.Column("error", sa.Text()),
        sa.Column("topic", sa.Text()),
        sa.Column("book_data", sa.Text()),
        sa.Column("build_params", sa.Text()),
    )
    # Supports: get_all_jobs's ORDER BY created_at DESC, and
    # fail_stale_jobs's WHERE status IN (...) AND updated_at < ...
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])
    op.create_index("ix_jobs_status_updated_at", "jobs", ["status", "updated_at"])

    op.create_table(
        "admins",
        sa.Column("email", sa.String(length=256), primary_key=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("admins")
    op.drop_index("ix_jobs_status_updated_at", table_name="jobs")
    op.drop_index("ix_jobs_created_at", table_name="jobs")
    op.drop_table("jobs")
