from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """Base class for domain-level errors."""


class AppException(Exception):
    """Application-level exception that carries an HTTP status code."""

    def __init__(self, message: str, status_code: int = 400, detail: Any | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    content: dict[str, Any] = {"message": exc.message}
    if exc.detail is not None:
        content["detail"] = exc.detail
    return JSONResponse(status_code=exc.status_code, content=content)
