from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CHAR, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import JSONType, UUIDType


class FileStatus:
    """String constants for the ``files.status`` column.

    Using a plain class (not Enum) keeps the database column type as plain
    VARCHAR, avoiding the need for a PostgreSQL enum type that would complicate
    future migrations.
    """

    READY = "READY"
    PROCESSING = "PROCESSING"
    FAILED = "FAILED"
    DELETED = "DELETED"


class File(Base):
    """Canonical file storage record.

    A single row represents one uploaded file regardless of which domain
    feature owns it.  The ``kind``, ``target_type``, and ``target_id``
    columns express domain ownership.
    """

    __tablename__ = "files"
    __table_args__ = (
        Index("ix_files_user_kind", "user_id", "kind"),
        Index("ix_files_target", "target_type", "target_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Semantic kind: product_image | bulk_sheet | bulk_zip | support_attachment | misc
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    # Domain binding — NULL when the file is not yet attached to a resource
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True)
    # Relative path under settings.file_storage_dir, e.g. ab/cd/<sha256>__<filename>
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    # Full public URL set after upload; None until the row is persisted
    public_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=FileStatus.READY
    )
    # Arbitrary JSON payload stored per-upload (caller-supplied).
    # The Python attribute is ``file_metadata`` because ``metadata`` is a
    # reserved name on SQLAlchemy's DeclarativeBase (it refers to MetaData).
    # The actual database column is still named ``metadata``.
    file_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONType, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User")  # noqa: F821
