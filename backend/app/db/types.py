from __future__ import annotations

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import Uuid as _Uuid

UUIDType = _Uuid

JSONType = JSON().with_variant(JSONB(), "postgresql")
