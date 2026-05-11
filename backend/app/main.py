from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.exceptions import AppException, app_exception_handler
from app.core.logging import configure_logging
from app.services.jobs import start_worker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    start_worker()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Product Importer",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.app_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(AppException, app_exception_handler)
    app.include_router(api_router)
    return app


app = create_app()
