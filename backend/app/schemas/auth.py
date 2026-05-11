from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    basalam_user_id: int
    vendor_id: int | None
    name: str
    username: str
    avatar_url: str | None
    balance: int
