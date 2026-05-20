# TODO: implement src/db/session.py
import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")

# Create async engine — this is the connection to PostgreSQL
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # set True to see SQL queries in terminal (useful for debugging)
    pool_size=10,  # max 10 simultaneous DB connections
    max_overflow=20,  # allow 20 extra connections if pool is full
)

# Session factory — creates individual DB sessions
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# Base class all models inherit from
class Base(DeclarativeBase):
    pass


# Dependency for FastAPI routes
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
