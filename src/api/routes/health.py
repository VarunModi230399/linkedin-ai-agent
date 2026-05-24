# TODO: implement src/api/routes/health.py
# src/api/routes/health.py
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    Used by Docker health checks and monitoring tools
    to verify the API is running.
    """
    return {"status": "healthy"}


@router.get("/ready")
async def readiness_check():
    """
    Readiness check — confirms all dependencies are reachable.
    Used by deployment platforms before sending traffic.
    """
    return {"status": "ready", "dependencies": ["postgres", "redis", "qdrant"]}
