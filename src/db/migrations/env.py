# src/db/migrations/env.py
import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from src.db import models  # noqa: F401

# Import all models so Alembic can detect them
from src.db.models import Base

config = context.config
fileConfig(config.config_file_name)

# This tells Alembic what tables to track
target_metadata = Base.metadata

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://app:changeme@localhost:5432/linkedin_agent"
)


def run_migrations_offline():
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
