import arq
from .core.config import settings


# This function will be used as a dependency to get the arq client
async def get_arq_redis():
    """
    Creates and returns an arq Redis client.
    This will be used via dependency injection in your routes.
    """
    return await arq.create_pool(settings.get_redis_settings())
