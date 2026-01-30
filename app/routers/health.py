"""
Health check endpoints for monitoring service status.
"""

from fastapi import APIRouter, status
from sqlalchemy import text
from ..dependencies import DBSessionDep, ArqDep

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Basic health check endpoint.
    Returns 200 if the API is running.
    """
    return {
        "status": "healthy",
        "service": "ChooseYourTube API"
    }


@router.get("/db", status_code=status.HTTP_200_OK)
async def health_check_database(db_session: DBSessionDep):
    """
    Check database connectivity.
    Returns 200 if database connection is healthy.
    """
    try:
        # Execute a simple query to test the connection
        result = await db_session.execute(text("SELECT 1"))
        result.scalar()
        return {
            "status": "healthy",
            "service": "database",
            "type": "PostgreSQL"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "database",
            "error": str(e)
        }


@router.get("/redis", status_code=status.HTTP_200_OK)
async def health_check_redis(redis: ArqDep):
    """
    Check Redis/queue connectivity.
    Returns 200 if Redis connection is healthy.
    """
    try:
        # Test Redis connection by pinging
        await redis.ping()
        return {
            "status": "healthy",
            "service": "redis",
            "type": "arq queue"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "redis",
            "error": str(e)
        }
