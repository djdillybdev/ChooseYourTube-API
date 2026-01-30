"""
Tests for the arq worker module.

Tests worker configuration, lifecycle functions (startup/shutdown),
and the cron job that enqueues channel refresh tasks.
"""

import pytest
from datetime import timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from zoneinfo import ZoneInfo

from app.worker import (
    WorkerSettings,
    startup,
    shutdown,
    enqueue_channel_refreshes,
)
from app.services import video_service


class TestWorkerSettings:
    """Test WorkerSettings configuration."""

    def test_worker_settings_functions_list(self):
        """Verify WorkerSettings includes all task functions."""
        assert len(WorkerSettings.functions) == 2
        assert (
            video_service.fetch_and_store_all_channel_videos_task
            in WorkerSettings.functions
        )
        assert (
            video_service.refresh_latest_channel_videos_task in WorkerSettings.functions
        )

    def test_worker_settings_cron_jobs(self):
        """Verify WorkerSettings includes cron job configuration."""
        assert len(WorkerSettings.cron_jobs) == 1
        # Verify the cron job runs hourly (minute=0)
        cron_job = WorkerSettings.cron_jobs[0]
        assert cron_job.minute == 0

    def test_worker_settings_redis_settings(self):
        """Verify WorkerSettings has Redis configuration."""
        assert WorkerSettings.redis_settings is not None
        assert hasattr(WorkerSettings, "redis_settings")

    def test_worker_settings_timezone(self):
        """Verify WorkerSettings has timezone configuration."""
        assert WorkerSettings.timezone == ZoneInfo("Europe/Madrid")

    def test_worker_settings_max_jobs(self):
        """Verify WorkerSettings max_jobs is configured."""
        assert WorkerSettings.max_jobs == 10

    def test_worker_settings_keep_result(self):
        """Verify WorkerSettings keep_result is configured."""
        assert WorkerSettings.keep_result == 0

    def test_worker_settings_lifecycle_hooks(self):
        """Verify WorkerSettings has startup and shutdown hooks."""
        assert WorkerSettings.on_startup == startup
        assert WorkerSettings.on_shutdown == shutdown


@pytest.mark.asyncio
class TestStartup:
    """Test worker startup function."""

    async def test_startup_creates_redis_pool(self, mock_arq_pool):
        """Verify startup creates Redis pool and stores in context."""
        ctx = {}

        await startup(ctx)

        assert "redis" in ctx
        assert ctx["redis"] == mock_arq_pool


@pytest.mark.asyncio
class TestShutdown:
    """Test worker shutdown function."""

    async def test_shutdown_does_not_error(self):
        """Verify shutdown executes without errors."""
        ctx = {"redis": MagicMock()}

        # Should not raise any exceptions
        await shutdown(ctx)


@pytest.mark.asyncio
class TestEnqueueChannelRefreshes:
    """Test the cron job that enqueues channel refresh tasks."""

    async def test_enqueue_channel_refreshes_empty_db(self, mock_sessionmanager):
        """When no channels exist, no jobs should be enqueued."""
        # Mock get_all_channels to return empty list
        with patch("app.worker.channel_service.get_all_channels") as mock_get_channels:
            mock_get_channels.return_value = []

            mock_redis = AsyncMock()
            ctx = {"redis": mock_redis}

            await enqueue_channel_refreshes(ctx)

            # Verify no jobs were enqueued
            mock_redis.enqueue_job.assert_not_called()

    async def test_enqueue_channel_refreshes_single_channel(self, mock_sessionmanager):
        """With one channel, one job should be enqueued with no delay."""
        # Create a mock channel
        mock_channel = MagicMock()
        mock_channel.id = "UC_test_channel_1"

        with patch("app.worker.channel_service.get_all_channels") as mock_get_channels:
            mock_get_channels.return_value = [mock_channel]

            mock_redis = AsyncMock()
            ctx = {"redis": mock_redis}

            await enqueue_channel_refreshes(ctx)

            # Verify one job was enqueued with 0 delay (i * 3 where i=0)
            mock_redis.enqueue_job.assert_called_once_with(
                "refresh_latest_channel_videos_task",
                channel_id="UC_test_channel_1",
                _defer_by=timedelta(seconds=0),
            )

    async def test_enqueue_channel_refreshes_multiple_channels(
        self, mock_sessionmanager
    ):
        """With multiple channels, jobs should be staggered by 3 seconds."""
        # Create mock channels
        mock_channels = [
            MagicMock(id="UC_channel_1"),
            MagicMock(id="UC_channel_2"),
            MagicMock(id="UC_channel_3"),
        ]

        with patch("app.worker.channel_service.get_all_channels") as mock_get_channels:
            mock_get_channels.return_value = mock_channels

            mock_redis = AsyncMock()
            ctx = {"redis": mock_redis}

            await enqueue_channel_refreshes(ctx)

            # Verify all jobs were enqueued
            assert mock_redis.enqueue_job.call_count == 3

            # Verify delays are staggered by 3 seconds
            calls = mock_redis.enqueue_job.call_args_list
            assert calls[0][1]["_defer_by"] == timedelta(seconds=0)
            assert calls[1][1]["_defer_by"] == timedelta(seconds=3)
            assert calls[2][1]["_defer_by"] == timedelta(seconds=6)

            # Verify correct channel IDs
            assert calls[0][1]["channel_id"] == "UC_channel_1"
            assert calls[1][1]["channel_id"] == "UC_channel_2"
            assert calls[2][1]["channel_id"] == "UC_channel_3"

    async def test_enqueue_channel_refreshes_uses_session(self, mock_sessionmanager):
        """Verify sessionmanager.session() context manager is used."""
        with patch("app.worker.channel_service.get_all_channels") as mock_get_channels:
            mock_get_channels.return_value = []

            mock_redis = AsyncMock()
            ctx = {"redis": mock_redis}

            await enqueue_channel_refreshes(ctx)

            # Verify sessionmanager.session() was called
            mock_sessionmanager.session.assert_called_once()
