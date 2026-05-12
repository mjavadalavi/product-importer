from __future__ import annotations

from app.exceptions.base import AppException


class AuthError(AppException):
    def __init__(self, message: str = "احراز هویت الزامی است."):
        super().__init__(message, status_code=401)
