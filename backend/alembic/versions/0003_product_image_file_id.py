"""Add file_id FK column to product_images.

Revision ID: 0003_product_image_file_id
Revises: 0002_files
Create Date: 2026-05-12 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_product_image_file_id"
down_revision = "0002_files"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "product_images",
        sa.Column("file_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_product_images_file_id",
        "product_images",
        "files",
        ["file_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_product_images_file_id",
        "product_images",
        ["file_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_product_images_file_id", table_name="product_images")
    op.drop_constraint(
        "fk_product_images_file_id",
        "product_images",
        type_="foreignkey",
    )
    op.drop_column("product_images", "file_id")
