from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    def __init__(self, message: str, status_code: int = 400, detail: Any | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail


class InsufficientBalance(AppException):
    def __init__(self, required: int | None = None, available: int | None = None):
        msg = "موجودی کافی نیست."
        super().__init__(msg, status_code=402, detail={"required": required, "available": available})
        self.required = required
        self.available = available


class BasalamError(AppException):
    def __init__(self, message: str, status_code: int = 502, detail: Any | None = None):
        super().__init__(message, status_code=status_code, detail=detail)


class OpenRouterError(AppException):
    def __init__(self, message: str, status_code: int = 502, detail: Any | None = None):
        super().__init__(message, status_code=status_code, detail=detail)


class NotFoundError(AppException):
    def __init__(self, message: str = "یافت نشد."):
        super().__init__(message, status_code=404)


class AuthError(AppException):
    def __init__(self, message: str = "احراز هویت الزامی است."):
        super().__init__(message, status_code=401)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    content: dict[str, Any] = {"message": exc.message}
    if exc.detail is not None:
        content["detail"] = exc.detail
    return JSONResponse(status_code=exc.status_code, content=content)
