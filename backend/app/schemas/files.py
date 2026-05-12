from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# The five allowed upload kinds for this platform
FileKind = Literal[
    "product_image",
    "bulk_sheet",
    "bulk_zip",
    "support_attachment",
    "misc",
]


class FileOut(BaseModel):
    """Serialisation schema for a persisted File row.

    Used as the response body for all file-related endpoints.

    The ORM column is named ``metadata`` in the database but the Python
    attribute is ``file_metadata`` (to avoid a clash with SQLAlchemy's
    reserved ``metadata`` attribute on the declarative base).  We expose it
    as ``metadata`` in the JSON output via the ``alias`` / ``validation_alias``
    mechanism.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    kind: str
    target_type: str | None
    target_id: uuid.UUID | None
    mime: str
    size_bytes: int
    filename: str
    public_url: str | None
    status: str
    created_at: datetime
    # Read from the ORM attribute ``file_metadata``; serialise as ``metadata``
    metadata: dict = Field(default_factory=dict, validation_alias="file_metadata")
