from __future__ import annotations

import logging
import sys
from typing import Optional


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging. Mirrors app.core.logging.configure_logging."""
    log_format = "%(asctime)s %(levelname)s %(name)s %(message)s"
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=log_format,
        stream=sys.stdout,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)


class LoggerMixin:
    """Add a ``self.logger`` property backed by the class name."""

    @property
    def logger(self) -> logging.Logger:
        if not hasattr(self, "_logger"):
            self._logger = logging.getLogger(self.__class__.__name__)
        return self._logger
