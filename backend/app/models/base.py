"""
Base model, TimestampMixin, and SoftDeleteMixin for all ORM models.

Design choices for this project:
- Primary keys are UUIDs (not auto-increment integers) — see existing models.
- Subclasses MUST define __tablename__ explicitly (we do not auto-derive it).
- TimestampMixin / SoftDeleteMixin can be mixed in independently.
- SoftDeleteMixin.deleted_at is NOT present on most current models; the
  repository layer guards against calling soft-delete queries on models that
  lack the column.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Mixins
# ---------------------------------------------------------------------------


class TimestampMixin:
    """
    Adds ``created_at`` / ``updated_at`` columns.

    Models that already define these columns manually should **not** inherit
    from this mixin to avoid duplicate-column errors.  Once a model's manual
    declarations are removed, it can inherit this instead.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Record creation timestamp",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Record last update timestamp",
    )


class SoftDeleteMixin:
    """
    Adds an optional ``deleted_at`` column for soft-delete functionality.

    Most current models do not use soft-delete; this mixin is here for future
    use.  The repository layer checks ``hasattr(model, "deleted_at")`` before
    adding soft-delete filters.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Record deletion timestamp (NULL if not deleted)",
    )

    def soft_delete(self) -> None:
        """Mark the record as deleted."""
        self.deleted_at = datetime.now(tz=timezone.utc)  # type: ignore[assignment]
        logger.info("Soft deleted %s id=%s", self.__class__.__name__, getattr(self, "id", "?"))

    def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.deleted_at = None  # type: ignore[assignment]
        logger.info("Restored %s id=%s", self.__class__.__name__, getattr(self, "id", "?"))

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


# ---------------------------------------------------------------------------
# BaseModel
# ---------------------------------------------------------------------------


class BaseModel(Base, TimestampMixin, SoftDeleteMixin):
    """
    Abstract base for all ORM models.

    Provides:
    - UUID primary key (``id``)
    - Timestamps via TimestampMixin
    - Soft-delete via SoftDeleteMixin
    - ``to_dict()`` helper

    Subclasses MUST define ``__tablename__`` explicitly — this class does NOT
    auto-derive it from the class name.
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.id})>"

    def to_dict(self) -> dict[str, Any]:
        """Convert the model instance to a plain dictionary."""
        result: dict[str, Any] = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            result[column.name] = value
        return result
