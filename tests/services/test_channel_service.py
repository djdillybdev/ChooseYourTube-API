"""
Tests for channel service integration.

Tests the channel service functions that interact with YouTube API
and the database, including adding channels and refreshing data.
"""

import pytest
import pytest_asyncio
from fastapi import HTTPException
from unittest.mock import patch, AsyncMock

from app.services.channel_service import (
    create_channel,
    refresh_channel_by_id,
    _get_best_thumbnail_url,
)
from app.schemas.channel import ChannelCreate
from app.db.models.channel import Channel


@pytest_asyncio.fixture
async def sample_channel(db_session):
    """Create a sample channel for testing."""
    channel = Channel(
        id="UC_existing_channel",
        handle="existingchannel",
        title="Existing Channel",
        uploads_playlist_id="UU_existing_uploads",
    )
    db_session.add(channel)
    await db_session.commit()
    await db_session.refresh(channel)
    return channel


@pytest.fixture
def sample_youtube_channel_response():
    """Sample YouTube API channel response."""
    return {
        "items": [
            {
                "id": "UC_new_channel_123",
                "snippet": {
                    "title": "Test Channel",
                    "description": "Test Description",
                    "thumbnails": {
                        "high": {"url": "https://example.com/high.jpg"},
                        "medium": {"url": "https://example.com/medium.jpg"},
                        "default": {"url": "https://example.com/default.jpg"},
                    },
                },
                "contentDetails": {
                    "relatedPlaylists": {"uploads": "UU_new_uploads_123"}
                },
            }
        ]
    }


class TestGetBestThumbnailUrl:
    """Test _get_best_thumbnail_url helper function."""

    def test_get_best_thumbnail_url_prefers_high(self):
        """Test that high quality thumbnail is preferred."""
        thumbnails = {
            "high": {"url": "https://example.com/high.jpg"},
            "medium": {"url": "https://example.com/medium.jpg"},
            "default": {"url": "https://example.com/default.jpg"},
        }

        url = _get_best_thumbnail_url(thumbnails)
        assert url == "https://example.com/high.jpg"

    def test_get_best_thumbnail_url_fallback_to_medium(self):
        """Test fallback to medium quality when high is not available."""
        thumbnails = {
            "medium": {"url": "https://example.com/medium.jpg"},
            "default": {"url": "https://example.com/default.jpg"},
        }

        url = _get_best_thumbnail_url(thumbnails)
        assert url == "https://example.com/medium.jpg"

    def test_get_best_thumbnail_url_fallback_to_default(self):
        """Test fallback to default quality when only default is available."""
        thumbnails = {
            "default": {"url": "https://example.com/default.jpg"},
        }

        url = _get_best_thumbnail_url(thumbnails)
        assert url == "https://example.com/default.jpg"

    def test_get_best_thumbnail_url_all_missing(self):
        """Test that None is returned when no thumbnails are available."""
        thumbnails = {}

        url = _get_best_thumbnail_url(thumbnails)
        assert url is None


@pytest.mark.asyncio
class TestCreateChannel:
    """Test create_channel function."""

    async def test_create_channel_success(
        self, db_session, mock_youtube_api, sample_youtube_channel_response
    ):
        """Test successful channel addition."""
        # Mock asyncio.to_thread to return the YouTube response
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = sample_youtube_channel_response

            payload = ChannelCreate(handle="@testchannel")

            channel = await create_channel(payload, db_session, mock_youtube_api)

            # Verify channel was created with correct data
            assert channel.id == "UC_new_channel_123"
            assert channel.handle == "testchannel"  # @ stripped
            assert channel.title == "Test Channel"
            assert channel.description == "Test Description"
            assert channel.thumbnail_url == "https://example.com/high.jpg"
            assert channel.uploads_playlist_id == "UU_new_uploads_123"

    async def test_create_channel_strips_at_symbol(
        self, db_session, mock_youtube_api, sample_youtube_channel_response
    ):
        """Test that @ symbol is stripped from handle."""
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = sample_youtube_channel_response

            payload = ChannelCreate(handle="@testchannel")

            await create_channel(payload, db_session, mock_youtube_api)

            # Verify get_channel_info was called with handle without @
            call_kwargs = mock_to_thread.call_args[1]
            assert call_kwargs["handle"] == "testchannel"

    async def test_create_channel_extracts_handle_from_url(
        self, db_session, mock_youtube_api, sample_youtube_channel_response
    ):
        """Test that @handle is extracted when user provides a channel URL."""
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = sample_youtube_channel_response

            payload = ChannelCreate(
                handle="https://www.youtube.com/@testchannel/videos"
            )

            channel = await create_channel(payload, db_session, mock_youtube_api)

            assert channel.handle == "testchannel"
            call_kwargs = mock_to_thread.call_args[1]
            assert call_kwargs["handle"] == "testchannel"

    async def test_create_channel_not_found_on_youtube_raises_500(
        self, db_session, mock_youtube_api
    ):
        """Test that 500 is raised when channel not found on YouTube (404 wrapped in 500)."""
        # Mock empty response from YouTube
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = {"items": []}

            payload = ChannelCreate(handle="@nonexistent")

            with pytest.raises(HTTPException) as exc_info:
                await create_channel(payload, db_session, mock_youtube_api)

            # The code catches the 404 and re-raises as 500
            assert exc_info.value.status_code == 500
            assert "YouTube API" in exc_info.value.detail

    async def test_create_channel_already_exists_raises_409(
        self, db_session, mock_youtube_api, sample_channel
    ):
        """Test that 409 is raised when channel already exists in database."""
        # Mock YouTube response with existing channel ID
        response = {
            "items": [
                {
                    "id": "UC_existing_channel",  # Same as sample_channel
                    "snippet": {"title": "Test"},
                    "contentDetails": {"relatedPlaylists": {"uploads": "UU_test"}},
                }
            ]
        }

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = response

            payload = ChannelCreate(handle="@existingchannel")

            with pytest.raises(HTTPException) as exc_info:
                await create_channel(payload, db_session, mock_youtube_api)

            assert exc_info.value.status_code == 409
            assert "already been added" in exc_info.value.detail

    async def test_create_channel_youtube_api_error_raises_500(
        self, db_session, mock_youtube_api
    ):
        """Test that 500 is raised when YouTube API errors."""
        # Mock YouTube API error
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.side_effect = Exception("API quota exceeded")

            payload = ChannelCreate(handle="@testchannel")

            with pytest.raises(HTTPException) as exc_info:
                await create_channel(payload, db_session, mock_youtube_api)

            assert exc_info.value.status_code == 500
            assert "YouTube API" in exc_info.value.detail

    async def test_create_channel_with_folder_assignment(
        self, db_session, mock_youtube_api, sample_youtube_channel_response
    ):
        """Test adding channel with folder assignment."""
        # First create a folder
        from app.db.models.folder import Folder

        folder = Folder(id="f1", name="Test Folder", parent_id=None)
        db_session.add(folder)
        await db_session.commit()

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = sample_youtube_channel_response

            payload = ChannelCreate(handle="@testchannel", folder_id="f1")

            channel = await create_channel(payload, db_session, mock_youtube_api)

            assert channel.folder_id == "f1"

    async def test_create_channel_with_missing_optional_fields(
        self, db_session, mock_youtube_api
    ):
        """Test adding channel when YouTube response has missing optional fields."""
        # Response with minimal data
        minimal_response = {
            "items": [
                {
                    "id": "UC_minimal_123",
                    "snippet": {
                        "title": "Minimal Channel",
                        # No description, no thumbnails
                    },
                    "contentDetails": {
                        "relatedPlaylists": {"uploads": "UU_minimal_uploads"}
                    },
                }
            ]
        }

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = minimal_response

            payload = ChannelCreate(handle="@minimal")

            channel = await create_channel(payload, db_session, mock_youtube_api)

            assert channel.id == "UC_minimal_123"
            assert channel.description is None
            assert channel.thumbnail_url is None


@pytest.mark.asyncio
class TestRefreshChannelById:
    """Test refresh_channel_by_id function."""

    async def test_refresh_channel_success(
        self, db_session, sample_channel, mock_youtube_api, mock_feedparser
    ):
        """Test successful channel refresh."""
        # Mock empty RSS feed (no new videos)
        from unittest.mock import MagicMock

        empty_feed = MagicMock()
        empty_feed.entries = []
        mock_feedparser.return_value = empty_feed

        # Mock the refresh_latest_channel_videos function
        with patch(
            "app.services.channel_service.refresh_latest_channel_videos"
        ) as mock_refresh:
            mock_refresh.return_value = None

            channel = await refresh_channel_by_id(
                sample_channel.id, db_session, mock_youtube_api
            )

            # Verify refresh was called
            mock_refresh.assert_called_once_with(
                sample_channel.id, db_session, mock_youtube_api, owner_id="test-user"
            )

            # Verify channel was returned
            assert channel.id == sample_channel.id

    async def test_refresh_nonexistent_channel_raises_404(
        self, db_session, mock_youtube_api
    ):
        """Test that refreshing non-existent channel raises 404."""
        with pytest.raises(HTTPException) as exc_info:
            await refresh_channel_by_id("UC_nonexistent", db_session, mock_youtube_api)

        assert exc_info.value.status_code == 404
        assert "Channel not found" in exc_info.value.detail
