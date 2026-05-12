"""Initial schema — create all tables and enum types.

Revision ID: 0001_init
Revises:
Create Date: 2026-05-11 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_postgresql() -> bool:
    """Return True when the migration is running against a PostgreSQL database."""
    bind = op.get_bind()
    return bind.dialect.name == "postgresql"


def _now() -> sa.TextClause:
    """Return the appropriate SQL expression for the current timestamp,
    compatible with both PostgreSQL and SQLite."""
    if _is_postgresql():
        return sa.text("now()")
    return sa.text("CURRENT_TIMESTAMP")


# ---------------------------------------------------------------------------
# Enum definitions
# These names must match the ``name=`` argument in the SQLAlchemy column
# definitions inside the model files.
# ---------------------------------------------------------------------------

general_type_enum = sa.Enum(
    "WITHDRAW", "DEPOSIT",
    name="general_type_enum",
    create_type=False,
)

reference_type_enum = sa.Enum(
    "PRODUCT", "SUBSCRIPTION", "PAYMENT", "REFERRAL", "GIFT", "REQUEST_AMOUNT",
    name="reference_type_enum",
    create_type=False,
)

transaction_status_enum = sa.Enum(
    "PENDING", "COMPLETED", "FAILED", "REVERSED",
    name="transaction_status_enum",
    create_type=False,
)

product_status_enum = sa.Enum(
    "DRAFT", "PROCESSING", "READY", "SUBMITTED", "FAILED",
    name="product_status_enum",
    create_type=False,
)

job_status_enum = sa.Enum(
    "QUEUED", "RUNNING", "SUCCEEDED", "FAILED",
    name="job_status_enum",
    create_type=False,
)

ticket_status_enum = sa.Enum(
    "OPEN", "IN_PROGRESS", "CLOSED",
    name="ticket_status_enum",
    create_type=False,
)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Create enum types explicitly on PostgreSQL so that they exist
    # before the tables that reference them are created.
    # On SQLite, Alembic renders enums as VARCHAR, so no pre-creation
    # step is needed.
    # ------------------------------------------------------------------
    # Note: enum types are auto-created by SQLAlchemy when their first
    # referencing column is created in op.create_table below.

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("basalam_user_id", sa.BigInteger(), nullable=False),
        sa.Column("vendor_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("avatar_url", sa.String(1024), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_basalam_user_id"), "users", ["basalam_user_id"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    # ------------------------------------------------------------------
    # oauth_accounts
    # ------------------------------------------------------------------
    # JSONType is JSON on non-PG, JSONB on PG.
    json_type = postgresql.JSONB(astext_type=sa.Text()) if _is_postgresql() else sa.JSON()

    op.create_table(
        "oauth_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False, server_default="basalam"),
        sa.Column("access_token_enc", sa.Text(), nullable=False),
        sa.Column("refresh_token_enc", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("raw_payload", json_type, nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=_now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_oauth_accounts_user_id"), "oauth_accounts", ["user_id"])

    # ------------------------------------------------------------------
    # transactions
    # ------------------------------------------------------------------
    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("general_type", general_type_enum, nullable=False),
        sa.Column("reference_type", reference_type_enum, nullable=False),
        sa.Column("reference_id", sa.BigInteger(), nullable=True),
        sa.Column("amount", sa.Numeric(14, 0), nullable=False),
        sa.Column("status", transaction_status_enum, nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
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
    op.create_index(op.f("ix_transactions_user_id"), "transactions", ["user_id"])
    # Composite index declared in __table_args__
    op.create_index("ix_transactions_user_status", "transactions", ["user_id", "status"])

    # Partial unique index on idempotency_key (only non-NULL rows).
    # PostgreSQL supports the WHERE clause natively; SQLite silently ignores
    # the postgresql_where keyword and creates a plain unique index, which is
    # also correct because NULL values are considered distinct in SQLite's
    # unique indexes.
    if _is_postgresql():
        op.create_index(
            "uq_transactions_idempotency_key",
            "transactions",
            ["idempotency_key"],
            unique=True,
            postgresql_where=sa.text("idempotency_key IS NOT NULL"),
        )
    else:
        # On SQLite a plain unique index over a nullable column works correctly:
        # multiple NULL values are allowed because NULLs are never considered
        # equal to each other.
        op.create_index(
            "uq_transactions_idempotency_key",
            "transactions",
            ["idempotency_key"],
            unique=True,
        )

    # ------------------------------------------------------------------
    # products
    # ------------------------------------------------------------------
    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", product_status_enum, nullable=False),
        sa.Column("name", sa.String(512), nullable=True),
        sa.Column("brief", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("category_title", sa.String(255), nullable=True),
        sa.Column("category_confidence", sa.Float(), nullable=True),
        sa.Column("price_final", sa.Numeric(14, 0), nullable=True),
        sa.Column("price_suggested", sa.Numeric(14, 0), nullable=True),
        sa.Column("price_meta", json_type, nullable=True),
        sa.Column("stock", sa.Integer(), nullable=True),
        sa.Column("weight", sa.Float(), nullable=True),
        sa.Column("package_weight", sa.Float(), nullable=True),
        sa.Column("preparation_days", sa.Integer(), nullable=True),
        sa.Column("unit_quantity", sa.Float(), nullable=True),
        sa.Column("unit_type", sa.Integer(), nullable=True),
        sa.Column("sku", sa.String(255), nullable=True),
        sa.Column("attributes", json_type, nullable=True),
        sa.Column("variants", json_type, nullable=True),
        sa.Column("ai_result", json_type, nullable=True),
        sa.Column("price_samples", json_type, nullable=True),
        sa.Column("basalam_product_id", sa.BigInteger(), nullable=True),
        sa.Column("errors", json_type, nullable=True),
        sa.Column("withdraw_tx_id", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(["withdraw_tx_id"], ["transactions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_products_user_id"), "products", ["user_id"])
    # Composite index declared in __table_args__
    op.create_index("ix_products_user_status", "products", ["user_id", "status"])

    # ------------------------------------------------------------------
    # product_images
    # ------------------------------------------------------------------
    op.create_table(
        "product_images",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("original_url", sa.Text(), nullable=True),
        sa.Column("enhanced_url", sa.Text(), nullable=True),
        sa.Column("use_enhanced", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("filename", sa.String(255), nullable=False, server_default="product.jpg"),
        sa.Column("enhancement_model", sa.String(128), nullable=True),
        sa.Column("enhancement_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_product_images_product_id"), "product_images", ["product_id"])

    # ------------------------------------------------------------------
    # import_jobs
    # ------------------------------------------------------------------
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("status", job_status_enum, nullable=False),
        sa.Column("step", sa.String(64), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_import_jobs_product_id"), "import_jobs", ["product_id"])
    op.create_index(op.f("ix_import_jobs_status"), "import_jobs", ["status"])

    # ------------------------------------------------------------------
    # support_tickets
    # ------------------------------------------------------------------
    op.create_table(
        "support_tickets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", ticket_status_enum, nullable=False),
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
    op.create_index(op.f("ix_support_tickets_user_id"), "support_tickets", ["user_id"])


def downgrade() -> None:
    # Drop tables in reverse dependency order.
    op.drop_index(op.f("ix_support_tickets_user_id"), table_name="support_tickets")
    op.drop_table("support_tickets")

    op.drop_index(op.f("ix_import_jobs_status"), table_name="import_jobs")
    op.drop_index(op.f("ix_import_jobs_product_id"), table_name="import_jobs")
    op.drop_table("import_jobs")

    op.drop_index(op.f("ix_product_images_product_id"), table_name="product_images")
    op.drop_table("product_images")

    op.drop_index("ix_products_user_status", table_name="products")
    op.drop_index(op.f("ix_products_user_id"), table_name="products")
    op.drop_table("products")

    op.drop_index("uq_transactions_idempotency_key", table_name="transactions")
    op.drop_index("ix_transactions_user_status", table_name="transactions")
    op.drop_index(op.f("ix_transactions_user_id"), table_name="transactions")
    op.drop_table("transactions")

    op.drop_index(op.f("ix_oauth_accounts_user_id"), table_name="oauth_accounts")
    op.drop_table("oauth_accounts")

    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_basalam_user_id"), table_name="users")
    op.drop_table("users")

    # Drop enum types (PostgreSQL only; on other dialects they are VARCHAR
    # columns and there is nothing to drop).
    if _is_postgresql():
        ticket_status_enum.drop(op.get_bind(), checkfirst=True)
        job_status_enum.drop(op.get_bind(), checkfirst=True)
        product_status_enum.drop(op.get_bind(), checkfirst=True)
        transaction_status_enum.drop(op.get_bind(), checkfirst=True)
        reference_type_enum.drop(op.get_bind(), checkfirst=True)
        general_type_enum.drop(op.get_bind(), checkfirst=True)
