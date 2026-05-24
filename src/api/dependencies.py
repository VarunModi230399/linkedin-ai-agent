# TODO: implement src/api/dependencies.py
# src/api/dependencies.py
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import AsyncSessionLocal


async def get_db() -> AsyncSession:
    """
    FastAPI dependency that provides a database session.
    Automatically commits on success, rolls back on error.

    Usage in routes:
        @app.get("/posts")
        async def get_posts(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
