from __future__ import annotations

from typing import Any

from app.exceptions.base import AppException


class BasalamError(AppException):
    def __init__(self, message: str, status_code: int = 502, detail: Any | None = None):
        super().__init__(message, status_code=status_code, detail=detail)
