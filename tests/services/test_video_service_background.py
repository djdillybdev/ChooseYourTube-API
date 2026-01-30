"""
Tests for video service background task functions.

Tests the background tasks that fetch and refresh videos from YouTube,
including RSS feed parsing, pagination, and bulk video creation.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.video_service import (
    fetch_and_store_all_channel_videos_task,
    refresh_latest_channel_videos_task,
    refresh_latest_channel_videos,
    create_and_update_videos,
)
from app.db.models.channel import Channel
from app.db.models.video import Video
from app.schemas.video import VideoCreate


@pytest_asyncio.fixture
async def sample_channel(db_session):
    """Create a sample channel for testing."""
    channel = Channel(
        id="UC_test_channel",
        handle="testchannel",
        title="Test Channel",
        uploads_playlist_id="UU_test_uploads",
    )
    db_session.add(channel)
    await db_session.commit()
    await db_session.refresh(channel)
    return channel


@pytest.fixture
def mock_ctx():
    """Mock arq context for background tasks."""
    return {"redis": AsyncMock()}


@pytest.mark.asyncio
class TestFetchAndStoreAllChannelVideosTask:
    """Test fetch_and_store_all_channel_videos_task background task."""

    async def test_fetch_all_videos_success_single_page(
        self, db_session, sample_channel, mock_ctx, mock_youtube_api
    ):
        """Test successful fetch with a single page of videos."""
        # Mock playlist response (single page, no nextPageToken)
        mock_youtube_api.playlist_items_list_async.return_value = {
            "items": [
                {
                    "snippet": {"title": "Video 1"},
                    "contentDetails": {"videoId": "video_1"},
                },
                {
                    "snippet": {"title": "Video 2"},
                    "contentDetails": {"videoId": "video_2"},
                },
            ],
            "nextPageToken": None,
        }

        # Mock videos_list response
        mock_youtube_api.videos_list_async.return_value = {
            "items": [
                {
                    "id": "video_1",
                    "snippet": {
                        "title": "Video 1",
                        "description": "Desc 1",
                        "publishedAt": "2024-01-01T00:00:00Z",
                        "thumbnails": {"high": {"url": "http://thumb1.jpg"}},
                        "tags": [],
                    },
                    "contentDetails": {"duration": "PT5M30S"},
                },
                {
                    "id": "video_2",
                    "snippet": {
                        "title": "Video 2",
                        "description": "Desc 2",
                        "publishedAt": "2024-01-02T00:00:00Z",
                        "thumbnails": {"high": {"url": "http://thumb2.jpg"}},
                        "tags": [],
                    },
                    "contentDetails": {"duration": "PT10M"},
                },
            ]
        }

        with patch(
            "app.services.video_service.YouTubeAPI", return_value=mock_youtube_api
        ):
            with patch("app.services.video_service.sessionmanager.session") as mock_sm:
                mock_sm.return_value.__aenter__.return_value = db_session

                await fetch_and_store_all_channel_videos_task(
                    mock_ctx, sample_channel.id
                )

        # Verify videos were created
        from app.db.crud.crud_video import get_videos

        videos = await get_videos(db_session, channel_id=sample_channel.id)
        assert len(videos) == 2

    async def test_fetch_all_videos_channel_not_found(self, db_session, mock_ctx):
        """Test task exits gracefully when channel doesn't exist."""
        mock_youtube_api = AsyncMock()

        with patch(
            "app.services.video_service.YouTubeAPI", return_value=mock_youtube_api
        ):
            with patch("app.services.video_service.sessionmanager.session") as mock_sm:
                mock_sm.return_value.__aenter__.return_value = db_session

                # Should not raise, just exit
                await fetch_and_store_all_channel_videos_task(
                    mock_ctx, "UC_nonexistent"
                )

        # Verify no API calls were made
        mock_youtube_api.playlist_items_list_async.assert_not_called()

    async def test_fetch_all_videos_pagination_multiple_pages(
        self, db_session, sample_channel, mock_ctx, mock_youtube_api
    ):
        """Test pagination handling with multiple pages."""
        # First page with nextPageToken
        first_page = {
            "items": [
                {"snippet": {}, "contentDetails": {"videoId": "video_1"}},
            ],
            "nextPageToken": "page2_token",
        }

        # Second page without nextPageToken
        second_page = {
            "items": [
                {"snippet": {}, "contentDetails": {"videoId": "video_2"}},
            ],
            "nextPageToken": None,
        }

        mock_youtube_api.playlist_items_list_async.side_effect = [
            first_page,
            second_page,
        ]

        # Mock videos_list response
        mock_youtube_api.videos_list_async.return_value = {
            "items": [
                {
                    "id": "video_1",
                    "snippet": {
                        "title": "Video 1",
                        "publishedAt": "2024-01-01T00:00:00Z",
                        "thumbnails": {},
                        "tags": [],
                    },
                    "contentDetails": {"duration": "PT5M"},
                },
                {
                    "id": "video_2",
                    "snippet": {
                        "title": "Video 2",
                        "publishedAt": "2024-01-02T00:00:00Z",
                        "thumbnails": {},
                        "tags": [],
                    },
                    "contentDetails": {"duration": "PT10M"},
                },
            ]
        }

        with patch(
            "app.services.video_service.YouTubeAPI", return_value=mock_youtube_api
        ):
            with patch("app.services.video_service.sessionmanager.session") as mock_sm:
                mock_sm.return_value.__aenter__.return_value = db_session

                await fetch_and_store_all_channel_videos_task(
                    mock_ctx, sample_channel.id
                )

        # Verify playlist_items_list_async was called twice (pagination)
        assert mock_youtube_api.playlist_items_list_async.call_count == 2

    async def test_fetch_all_videos_deduplicates_video_ids(
        self, db_session, sample_channel, mock_ctx, mock_youtube_api
    ):
        """Test that duplicate video IDs are deduplicated."""
        # Mock playlist with duplicate video IDs
        mock_youtube_api.playlist_items_list_async.return_value = {
            "items": [
                {"snippet": {}, "contentDetails": {"videoId": "video_1"}},
                {"snippet": {}, "contentDetails": {"videoId": "video_1"}},  # Duplicate
                {"snippet": {}, "contentDetails": {"videoId": "video_2"}},
            ],
            "nextPageToken": None,
        }

        mock_youtube_api.videos_list_async.return_value = {
            "items": [
                {
                    "id": "video_1",
                    "snippet": {
                        "title": "Video 1",
                        "publishedAt": "2024-01-01T00:00:00Z",
                        "thumbnails": {},
                        "tags": [],
                    },
                    "contentDetails": {"duration": "PT5M"},
                },
                {
                    "id": "video_2",
                    "snippet": {
                        "title": "Video 2",
                        "publishedAt": "2024-01-02T00:00:00Z",
                        "thumbnails": {},
                        "tags": [],
                    },
                    "contentDetails": {"duration": "PT10M"},
                },
            ]
        }

        with patch(
            "app.services.video_service.YouTubeAPI", return_value=mock_youtube_api
        ):
            with patch("app.services.video_service.sessionmanager.session") as mock_sm:
                mock_sm.return_value.__aenter__.return_value = db_session

                await fetch_and_store_all_channel_videos_task(
                    mock_ctx, sample_channel.id
                )

        # Verify videos_list was called with deduplicated IDs (video_1,video_2)
        call_args = mock_youtube_api.videos_list_async.call_args
        assert "video_1,video_2" in call_args[1]["id"]

    async def test_fetch_all_videos_no_videos_found(
        self, db_session, sample_channel, mock_ctx, mock_youtube_api
    ):
        """Test task exits when playlist is empty."""
        mock_youtube_api.playlist_items_list_async.return_value = {
            "items": [],
            "nextPageToken": None,
        }

        with patch(
            "app.services.video_service.YouTubeAPI", return_value=mock_youtube_api
        ):
            with patch("app.services.video_service.sessionmanager.session") as mock_sm:
                mock_sm.return_value.__aenter__.return_value = db_session

                await fetch_and_store_all_channel_videos_task(
                    mock_ctx, sample_channel.id
                )

        # Verify videos_list was NOT called (no video IDs)
        mock_youtube_api.videos_list_async.assert_not_called()


@pytest.mark.asyncio
class TestRefreshLatestChannelVideosTask:
    """Test refresh_latest_channel_videos_task wrapper."""

    async def test_refresh_task_calls_service_function(
        self, db_session, sample_channel, mock_ctx, mock_youtube_api, mock_feedparser
    ):
        """Test that task wrapper calls the refresh service function."""
        # Mock feedparser to return empty feed (no new videos)
        empty_feed = MagicMock()
        empty_feed.entries = []
        mock_feedparser.return_value = empty_feed

        with patch(
            "app.services.video_service.YouTubeAPI", return_value=mock_youtube_api
        ):
            with patch("app.services.video_service.sessionmanager.session") as mock_sm:
                mock_sm.return_value.__aenter__.return_value = db_session

                await refresh_latest_channel_videos_task(mock_ctx, sample_channel.id)

        # Verify feedparser was called
        mock_feedparser.assert_called_once()


@pytest.mark.asyncio
class TestRefreshLatestChannelVideos:
    """Test refresh_latest_channel_videos service function."""

    async def test_refresh_parses_rss_feed(
        self,
        db_session,
        sample_channel,
        mock_youtube_api,
        mock_feedparser,
        sample_rss_feed,
    ):
        """Test that RSS feed is parsed correctly."""
        mock_feedparser.return_value = sample_rss_feed

        # Mock that all videos are already seen (no update needed)
        from app.db.crud.crud_video import create_videos_bulk
        from app.schemas.video import VideoCreate

        existing_videos = [
            VideoCreate(
                id="rss_video_1",
                channel_id=sample_channel.id,
                title="RSS Video 1",
                description="Description 1",
                published_at=datetime.now(timezone.utc),
                duration_seconds=300,
                is_short=False,
            ),
            VideoCreate(
                id="rss_video_2",
                channel_id=sample_channel.id,
                title="RSS Video 2",
                description="Description 2",
                published_at=datetime.now(timezone.utc),
                duration_seconds=400,
                is_short=False,
            ),
        ]
        await create_videos_bulk(db_session, existing_videos)

        await refresh_latest_channel_videos(
            sample_channel.id, db_session, mock_youtube_api
        )

        # Verify feedparser was called with correct URL
        expected_url = (
            f"https://www.youtube.com/feeds/videos.xml?channel_id={sample_channel.id}"
        )
        mock_feedparser.assert_called_once_with(expected_url)

    async def test_refresh_filters_shorts_from_rss(
        self, db_session, sample_channel, mock_youtube_api, mock_feedparser
    ):
        """Test that shorts are filtered from RSS feed entries."""
        # RSS feed with shorts and regular videos
        rss_feed_with_shorts = MagicMock()
        rss_feed_with_shorts.entries = [
            MagicMock(
                yt_videoid="regular_1", link="https://youtube.com/watch?v=regular_1"
            ),
            MagicMock(
                yt_videoid="short_1", link="https://youtube.com/shorts/short_1"
            ),  # Short
            MagicMock(
                yt_videoid="regular_2", link="https://youtube.com/watch?v=regular_2"
            ),
        ]
        mock_feedparser.return_value = rss_feed_with_shorts

        # No existing videos (will trigger API fallback)
        mock_youtube_api.playlist_items_list_async.return_value = {
            "items": [],
            "nextPageToken": None,
        }

        await refresh_latest_channel_videos(
            sample_channel.id, db_session, mock_youtube_api
        )

        # RSS should have filtered shorts, leaving only regular_1 and regular_2
        # Since no overlap, API is called
        mock_youtube_api.playlist_items_list_async.assert_called_once()

    async def test_refresh_detects_no_new_videos(
        self, db_session, sample_channel, mock_youtube_api, mock_feedparser
    ):
        """Test early return when all RSS videos are already in database."""
        rss_feed = MagicMock()
        rss_feed.entries = [
            MagicMock(yt_videoid="video_1", link="https://youtube.com/watch?v=video_1"),
            MagicMock(yt_videoid="video_2", link="https://youtube.com/watch?v=video_2"),
        ]
        mock_feedparser.return_value = rss_feed

        # Create existing videos
        from app.db.crud.crud_video import create_videos_bulk
        from app.schemas.video import VideoCreate

        existing_videos = [
            VideoCreate(
                id="video_1",
                channel_id=sample_channel.id,
                title="Video 1",
                description="Description 1",
                published_at=datetime.now(timezone.utc),
                duration_seconds=300,
                is_short=False,
            ),
            VideoCreate(
                id="video_2",
                channel_id=sample_channel.id,
                title="Video 2",
                description="Description 2",
                published_at=datetime.now(timezone.utc),
                duration_seconds=400,
                is_short=False,
            ),
        ]
        await create_videos_bulk(db_session, existing_videos)

        await refresh_latest_channel_videos(
            sample_channel.id, db_session, mock_youtube_api
        )

        # Should early return without calling YouTube API
        mock_youtube_api.playlist_items_list_async.assert_not_called()
        mock_youtube_api.videos_list_async.assert_not_called()

    async def test_refresh_detects_some_new_videos(
        self, db_session, sample_channel, mock_youtube_api, mock_feedparser
    ):
        """Test partial overlap - some videos new, some existing."""
        rss_feed = MagicMock()
        rss_feed.entries = [
            MagicMock(
                yt_videoid="new_video", link="https://youtube.com/watch?v=new_video"
            ),
            MagicMock(
                yt_videoid="existing_video",
                link="https://youtube.com/watch?v=existing_video",
            ),
        ]
        mock_feedparser.return_value = rss_feed

        # Create one existing video
        from app.db.crud.crud_video import create_videos_bulk
        from app.schemas.video import VideoCreate

        existing_videos = [
            VideoCreate(
                id="existing_video",
                channel_id=sample_channel.id,
                title="Existing Video",
                description="Existing description",
                published_at=datetime.now(timezone.utc),
                duration_seconds=300,
                is_short=False,
            ),
        ]
        await create_videos_bulk(db_session, existing_videos)

        # Mock videos_list response for new video
        mock_youtube_api.videos_list_async.return_value = {
            "items": [
                {
                    "id": "new_video",
                    "snippet": {
                        "title": "New Video",
                        "publishedAt": "2024-01-01T00:00:00Z",
                        "thumbnails": {},
                        "tags": [],
                    },
                    "contentDetails": {"duration": "PT5M"},
                },
                {
                    "id": "existing_video",
                    "snippet": {
                        "title": "Existing Video",
                        "publishedAt": "2024-01-02T00:00:00Z",
                        "thumbnails": {},
                        "tags": [],
                    },
                    "contentDetails": {"duration": "PT5M"},
                },
            ]
        }

        await refresh_latest_channel_videos(
            sample_channel.id, db_session, mock_youtube_api
        )

        # Should use RSS IDs for update (partial overlap)
        mock_youtube_api.videos_list_async.assert_called_once()

    async def test_refresh_falls_back_to_api(
        self, db_session, sample_channel, mock_youtube_api, mock_feedparser
    ):
        """Test fallback to API when no overlap with RSS feed."""
        rss_feed = MagicMock()
        rss_feed.entries = [
            MagicMock(yt_videoid="video_1", link="https://youtube.com/watch?v=video_1"),
        ]
        mock_feedparser.return_value = rss_feed

        # No existing videos in database
        mock_youtube_api.playlist_items_list_async.return_value = {
            "items": [{"snippet": {}, "contentDetails": {"videoId": "video_1"}}],
            "nextPageToken": None,
        }

        mock_youtube_api.videos_list_async.return_value = {
            "items": [
                {
                    "id": "video_1",
                    "snippet": {
                        "title": "Video 1",
                        "publishedAt": "2024-01-01T00:00:00Z",
                        "thumbnails": {},
                        "tags": [],
                    },
                    "contentDetails": {"duration": "PT5M"},
                },
            ]
        }

        await refresh_latest_channel_videos(
            sample_channel.id, db_session, mock_youtube_api
        )

        # Should call playlist API (no overlap)
        mock_youtube_api.playlist_items_list_async.assert_called_once()

    async def test_refresh_channel_not_found(
        self, db_session, mock_youtube_api, mock_feedparser
    ):
        """Test refresh exits when channel not found in database."""
        rss_feed = MagicMock()
        rss_feed.entries = [
            MagicMock(yt_videoid="video_1", link="https://youtube.com/watch?v=video_1"),
        ]
        mock_feedparser.return_value = rss_feed

        # No channel exists
        await refresh_latest_channel_videos(
            "UC_nonexistent", db_session, mock_youtube_api
        )

        # Should not call API (channel not found in DB)
        mock_youtube_api.playlist_items_list_async.assert_not_called()


@pytest.mark.asyncio
class TestCreateAndUpdateVideos:
    """Test create_and_update_videos bulk video creation function."""

    async def test_create_and_update_batches_api_requests(
        self, db_session, sample_channel, mock_youtube_api
    ):
        """Test that video IDs are batched into chunks of 50."""
        # Create 75 video IDs (should make 2 API calls: 50 + 25)
        video_ids = [f"video_{i}" for i in range(75)]

        # Mock videos_list to return matching items
        mock_youtube_api.videos_list_async.return_value = {
            "items": [
                {
                    "id": f"video_{i}",
                    "snippet": {
                        "title": f"Video {i}",
                        "publishedAt": "2024-01-01T00:00:00Z",
                        "thumbnails": {},
                        "tags": [],
                    },
                    "contentDetails": {"duration": "PT5M"},
                }
                for i in range(50)  # First batch
            ]
        }

        await create_and_update_videos(
            video_ids, sample_channel.id, db_session, mock_youtube_api
        )

        # Verify videos_list_async was called twice (2 batches)
        assert mock_youtube_api.videos_list_async.call_count == 2

    async def test_create_and_update_parses_duration(
        self, db_session, sample_channel, mock_youtube_api
    ):
        """Test that ISO8601 duration is parsed correctly."""
        video_ids = ["video_1"]

        mock_youtube_api.videos_list_async.return_value = {
            "items": [
                {
                    "id": "video_1",
                    "snippet": {
                        "title": "Video 1",
                        "publishedAt": "2024-01-01T00:00:00Z",
                        "thumbnails": {},
                        "tags": [],
                    },
                    "contentDetails": {"duration": "PT10M30S"},  # 10 minutes 30 seconds
                }
            ]
        }

        await create_and_update_videos(
            video_ids, sample_channel.id, db_session, mock_youtube_api
        )

        # Verify video was created with parsed duration (630 seconds)
        from app.db.crud.crud_video import get_videos

        videos = await get_videos(db_session, id="video_1", first=True)
        assert videos.duration_seconds == 630

    async def test_create_and_update_classifies_shorts(
        self, db_session, sample_channel, mock_youtube_api
    ):
        """Test that videos are classified as shorts based on duration and tags."""
        video_ids = ["short_video", "regular_video"]

        mock_youtube_api.videos_list_async.return_value = {
            "items": [
                {
                    "id": "short_video",
                    "snippet": {
                        "title": "My Short #shorts",
                        "publishedAt": "2024-01-01T00:00:00Z",
                        "thumbnails": {},
                        "tags": [],
                    },
                    "contentDetails": {
                        "duration": "PT30S"
                    },  # 30 seconds with #shorts tag
                },
                {
                    "id": "regular_video",
                    "snippet": {
                        "title": "Regular Video",
                        "publishedAt": "2024-01-02T00:00:00Z",
                        "thumbnails": {},
                        "tags": [],
                    },
                    "contentDetails": {"duration": "PT10M"},  # 10 minutes
                },
            ]
        }

        await create_and_update_videos(
            video_ids, sample_channel.id, db_session, mock_youtube_api
        )

        # Verify classification
        from app.db.crud.crud_video import get_videos

        short_video = await get_videos(db_session, id="short_video", first=True)
        regular_video = await get_videos(db_session, id="regular_video", first=True)

        assert short_video.is_short is True  # Short duration + #shorts tag
        assert regular_video.is_short is False  # Long duration

    async def test_create_and_update_handles_missing_video_id(
        self, db_session, sample_channel, mock_youtube_api
    ):
        """Test that videos without IDs are skipped."""
        video_ids = ["video_1"]

        # Mock response with item missing 'id' field
        mock_youtube_api.videos_list_async.return_value = {
            "items": [
                {
                    # Missing 'id' field
                    "snippet": {
                        "title": "Video without ID",
                        "publishedAt": "2024-01-01T00:00:00Z",
                        "thumbnails": {},
                        "tags": [],
                    },
                    "contentDetails": {"duration": "PT5M"},
                }
            ]
        }

        await create_and_update_videos(
            video_ids, sample_channel.id, db_session, mock_youtube_api
        )

        # Verify no videos were created (invalid item was skipped)
        from app.db.crud.crud_video import get_videos

        videos = await get_videos(db_session, channel_id=sample_channel.id)
        assert len(videos) == 0
