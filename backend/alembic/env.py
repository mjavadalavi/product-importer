from __future__ import annotations

import asyncio
import logging
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ---------------------------------------------------------------------------
# Load application settings so we can resolve the real database URL at
# runtime rather than hard-coding it in alembic.ini.
# ---------------------------------------------------------------------------
from app.core.config import get_settings

# Import Base *and* all models so that every table/enum is registered in
# Base.metadata before Alembic inspects it.
from app.db.base import Base
from app.db.models import *  # noqa: F401, F403

# ---------------------------------------------------------------------------
# Alembic Config object, which provides access to the values within
# the current alembic.ini file.
# ---------------------------------------------------------------------------
config = context.config

# Interpret the alembic.ini logging configuration section.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

# Override the sqlalchemy.url from application settings so that we have a
# single source of truth (environment variables / .env file).
_settings = get_settings()
config.set_main_option("sqlalchemy.url", _settings.database_url)

# The metadata object that autogenerate uses as the reference schema.
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline migrations (no live DB connection required)
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine; calls to
    context.execute() emit the given string to the script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online migrations (uses an actual async engine)
# ---------------------------------------------------------------------------

def do_run_migrations(connection: Connection) -> None:
    """Synchronous callback that runs the migrations on a real connection.

    This is called by ``run_migrations_online`` via ``connection.run_sync``.
    """
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and drive migrations through it."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for 'online' migration mode."""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    logger.info("Running migrations in offline mode")
    run_migrations_offline()
else:
    logger.info("Running migrations in online mode")
    run_migrations_online()
