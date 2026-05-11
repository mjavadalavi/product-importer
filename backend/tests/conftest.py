"""
Test configuration and shared fixtures.

IMPORTANT: env vars must be set BEFORE any app module is imported so that
pydantic-settings picks them up when creating the Settings singleton.
"""
from __future__ import annotations

import os
import secrets

from cryptography.fernet import Fernet

# ---------------------------------------------------------------------------
# Inject test environment variables before any app code is imported.
# ---------------------------------------------------------------------------
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_pi.db")
os.environ.setdefault("SESSION_SECRET", secrets.token_urlsafe(48))
os.environ.setdefault("FERNET_KEY", Fernet.generate_key().decode())
os.environ.setdefault("APP_ORIGIN", "http://localhost:3000")

# ---------------------------------------------------------------------------
# Now it is safe to import app modules.
# ---------------------------------------------------------------------------
import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Callable

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings, get_settings

# Clear any cached settings so the new env vars take effect.
get_settings.cache_clear()

from app.db.base import Base
# Import all models so their metadata is registered with Base.
import app.db.models  # noqa: F401  — registers all ORM classes on Base.metadata
from app.db.session import get_db

# Use a persistent file-based SQLite DB so multiple sessions in the same test
# run see the same schema and data.
_TEST_DB_URL = "sqlite+aiosqlite:///./test_pi.db"

_test_engine = create_async_engine(
    _TEST_DB_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

_TestSessionLocal = async_sessionmaker(
    bind=_test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ---------------------------------------------------------------------------
# Session-scoped: create / drop all tables once per pytest session.
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db() -> AsyncGenerator[None, None]:
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _test_engine.dispose()
    # Remove the DB file after the session.
    import os as _os
    try:
        _os.remove("./test_pi.db")
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# Function-scoped DB session wrapped in a savepoint that is rolled back after
# each test so tests remain isolated.
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    # Use a connection-level transaction + SAVEPOINT for rollback isolation.
    async with _test_engine.connect() as conn:
        await conn.begin()
        # Nested / SAVEPOINT transaction for test isolation.
        await conn.begin_nested()

        session = AsyncSession(bind=conn, expire_on_commit=False, autoflush=False)
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()


# ---------------------------------------------------------------------------
# App + HTTP client fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(monkeypatch):
    """Return the FastAPI application with the background worker disabled."""
    # Patch start_worker to a no-op so lifespan does not spawn the worker.
    import app.services.jobs as _jobs
    monkeypatch.setattr(_jobs, "start_worker", lambda: None)

    from app.main import app as _app
    return _app


@pytest_asyncio.fixture
async def client(app, db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient wired to the FastAPI app, using the test DB session."""

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        follow_redirects=False,
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def make_user(db_session: AsyncSession):
    """Factory that inserts a User row and returns it."""

    async def _factory(
        basalam_user_id: int | None = None,
        username: str | None = None,
        name: str = "Test User",
        vendor_id: int | None = 999,
    ) -> "User":
        from app.db.models.user import User

        if basalam_user_id is None:
            basalam_user_id = int(uuid.uuid4()) % 10_000_000 + 1
        if username is None:
            username = f"user_{basalam_user_id}"

        user = User(
            basalam_user_id=basalam_user_id,
            name=name,
            username=username,
            vendor_id=vendor_id,
        )
        db_session.add(user)
        await db_session.flush()
        return user

    return _factory


@pytest.fixture
def auth_cookie(make_user):
    """
    Factory that, given a User instance, returns a dict suitable for passing
    as ``cookies=`` to the test client.
    """

    def _factory(user) -> dict:
        settings = get_settings()
        from app.auth.jwt import encode_session
        token = encode_session(user.id)
        return {settings.session_cookie_name: token}

    return _factory
