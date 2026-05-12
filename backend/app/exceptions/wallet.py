from __future__ import annotations

from app.exceptions.base import AppException


class InsufficientBalance(AppException):
    def __init__(self, required: int | None = None, available: int | None = None):
        msg = "موجودی کافی نیست."
        super().__init__(msg, status_code=402, detail={"required": required, "available": available})
        self.required = required
        self.available = available
