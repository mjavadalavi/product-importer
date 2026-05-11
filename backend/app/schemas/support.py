from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.support_ticket import TicketStatus


class SupportTicketCreate(BaseModel):
    subject: str = Field(..., min_length=2, max_length=512)
    body: str = Field(..., min_length=2)


class SupportTicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject: str
    body: str
    status: TicketStatus
    created_at: datetime
    updated_at: datetime
