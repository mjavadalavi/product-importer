"""Create files table for canonical file storage.

Revision ID: 0002_files
Revises: 0001_init
Create Date: 2026-05-12 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_files"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def _is_postgresql() -> bool:
    """Return True when the migration is running against a PostgreSQL database."""
    bind = op.get_bind()
    return bind.dialect.name == "postgresql"


def _now() -> sa.TextClause:
    """Return the appropriate SQL expression for the current timestamp."""
    if _is_postgresql():
        return sa.text("now()")
    return sa.text("CURRENT_TIMESTAMP")


def upgrade() -> None:
    # JSONb on PostgreSQL, plain JSON everywhere else
    json_type = postgresql.JSONB(astext_type=sa.Text()) if _is_postgresql() else sa.JSON()

    op.create_table(
        "files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=True),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("public_url", sa.Text(), nullable=True),
        sa.Column("mime", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.CHAR(64), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="READY"),
        sa.Column("metadata", json_type, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=_now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Simple indexes
    op.create_index(op.f("ix_files_user_id"), "files", ["user_id"])
    op.create_index(op.f("ix_files_sha256"), "files", ["sha256"])

    # Composite indexes
    op.create_index("ix_files_user_kind", "files", ["user_id", "kind"])
    op.create_index("ix_files_target", "files", ["target_type", "target_id"])


def downgrade() -> None:
    op.drop_index("ix_files_target", table_name="files")
    op.drop_index("ix_files_user_kind", table_name="files")
    op.drop_index(op.f("ix_files_sha256"), table_name="files")
    op.drop_index(op.f("ix_files_user_id"), table_name="files")
    op.drop_table("files")
