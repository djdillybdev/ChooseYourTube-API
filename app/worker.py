from datetime import timedelta
from zoneinfo import ZoneInfo
import arq
from arq import cron

from .core.config import settings
from .db.session import sessionmanager
from .services import channel_service, video_service

REDIS_SETTINGS = settings.get_redis_settings()


async def startup(ctx):
    # Reuse a single ArqRedis connection for cron enqueues
    ctx["redis"] = await arq.create_pool(REDIS_SETTINGS)


async def shutdown(ctx):
    # ArqRedis uses a pool; nothing special required, but keep for symmetry
    pass


async def enqueue_channel_refreshes(ctx):
    """
    Hourly cron. Enqueue one refresh job per channel with a unique job id.
    """
    # Load channels (get the paginated response, then use its items list)
    async with sessionmanager.session() as db:
        paginated = await channel_service.get_all_channels(db)
        # `get_all_channels` may return a PaginatedResponse or a raw list
        channels = paginated.items if hasattr(paginated, "items") else paginated

    # Stagger enqueues to smooth load
    for i, ch in enumerate(channels):
        await ctx["redis"].enqueue_job(
            "refresh_latest_channel_videos_task",
            channel_id=ch.id,
            _defer_by=timedelta(seconds=i * 3),  # 3s spacing between jobs
        )


# This class defines the worker's configuration.
# The `arq` CLI will look for a class named `WorkerSettings`.
class WorkerSettings:
    """
    Defines the configuration for the arq worker.
    The `functions` list tells the worker which tasks it can execute.
    """

    # A list of all functions that the worker can run.
    # These must be async functions.
    functions = [
        video_service.fetch_and_store_all_channel_videos_task,
        video_service.refresh_latest_channel_videos_task,
    ]

    cron_jobs = [cron(enqueue_channel_refreshes, minute=0)]

    # Use the same Redis settings as our application
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = REDIS_SETTINGS
    timezone = ZoneInfo("Europe/Madrid")
    max_jobs = 10
    keep_result = 0
