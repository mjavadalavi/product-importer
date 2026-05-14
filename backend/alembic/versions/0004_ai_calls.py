"""Add ai_calls table for per-request AI cost tracking.

Revision ID: 0004_ai_calls
Revises: 0003_product_image_file_id
Create Date: 2026-05-14 15:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_ai_calls"
down_revision = "0003_product_image_file_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_calls",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column(
            "kind",
            sa.Enum("ANALYZE", "ENHANCE", "OTHER", name="ai_call_kind_enum"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("SUCCESS", "ERROR", name="ai_call_status_enum"),
            nullable=False,
        ),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column(
            "cost_usd",
            sa.Numeric(precision=14, scale=8),
            nullable=False,
            server_default="0",
        ),
        sa.Column("generation_id", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_ai_calls_user_id",
        "ai_calls",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_ai_calls_product_id",
        "ai_calls",
        "products",
        ["product_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_ai_calls_user_created", "ai_calls", ["user_id", "created_at"]
    )
    op.create_index("ix_ai_calls_product_id", "ai_calls", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_calls_product_id", table_name="ai_calls")
    op.drop_index("ix_ai_calls_user_created", table_name="ai_calls")
    op.drop_constraint("fk_ai_calls_product_id", "ai_calls", type_="foreignkey")
    op.drop_constraint("fk_ai_calls_user_id", "ai_calls", type_="foreignkey")
    op.drop_table("ai_calls")
    sa.Enum(name="ai_call_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="ai_call_kind_enum").drop(op.get_bind(), checkfirst=True)
