from __future__ import annotations

from app.exceptions.base import AppException


class NotFoundError(AppException):
    def __init__(self, message: str = "یافت نشد."):
        super().__init__(message, status_code=404)
