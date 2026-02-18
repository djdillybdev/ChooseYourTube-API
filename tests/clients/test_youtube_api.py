"""
Tests for YouTube API client.

Tests the YouTubeAPI class and YouTubeAPIManager for interacting
with the YouTube Data API, including OAuth and API key authentication.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.clients.youtube import YouTubeAPI, YouTubeAPIManager, get_youtube_api


class TestYouTubeAPIInit:
    """Test YouTubeAPI initialization with different auth methods."""

    def test_init_with_api_key(self):
        """Test initialization with API key only."""
        with patch("app.clients.youtube.googleapiclient.discovery.build") as mock_build:
            mock_youtube = MagicMock()
            mock_build.return_value = mock_youtube

            client = YouTubeAPI(api_key="test_api_key")

            # Verify build was called with API key
            mock_build.assert_called_once_with(
                "youtube", "v3", developerKey="test_api_key"
            )
            assert client.youtube == mock_youtube

    def test_init_with_client_secrets_oauth(self):
        """Test initialization with OAuth client secrets."""
        with patch(
            "app.clients.youtube.google_auth_oauthlib.flow.InstalledAppFlow"
        ) as mock_flow_cls:
            with patch(
                "app.clients.youtube.googleapiclient.discovery.build"
            ) as mock_build:
                # Mock OAuth flow
                mock_flow = MagicMock()
                mock_credentials = MagicMock()
                mock_flow.run_console.return_value = mock_credentials
                mock_flow_cls.from_client_secrets_file.return_value = mock_flow

                # Mock youtube client
                mock_youtube = MagicMock()
                mock_build.return_value = mock_youtube

                client = YouTubeAPI(
                    client_secrets_file="client_secrets.json",
                    scopes=["https://www.googleapis.com/auth/youtube.readonly"],
                )

                # Verify OAuth flow was used
                mock_flow_cls.from_client_secrets_file.assert_called_once_with(
                    "client_secrets.json",
                    scopes=["https://www.googleapis.com/auth/youtube.readonly"],
                )
                mock_flow.run_console.assert_called_once()

                # Verify build was called with credentials
                mock_build.assert_called_once_with(
                    "youtube", "v3", credentials=mock_credentials
                )
                assert client.youtube == mock_youtube

    def test_init_with_client_secrets_default_scopes(self):
        """Test that OAuth defaults to readonly scope if not provided."""
        with patch(
            "app.clients.youtube.google_auth_oauthlib.flow.InstalledAppFlow"
        ) as mock_flow_cls:
            with patch("app.clients.youtube.googleapiclient.discovery.build"):
                mock_flow = MagicMock()
                mock_flow_cls.from_client_secrets_file.return_value = mock_flow

                YouTubeAPI(client_secrets_file="client_secrets.json")

                # Verify default scope was used
                call_args = mock_flow_cls.from_client_secrets_file.call_args
                assert call_args[1]["scopes"] == [
                    "https://www.googleapis.com/auth/youtube.readonly"
                ]

    def test_init_without_credentials_raises(self):
        """Test that initialization without credentials raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            YouTubeAPI()

        assert "Must provide either" in str(exc_info.value)

    def test_init_with_both_credentials_prefers_oauth(self):
        """Test that OAuth is preferred when both credentials are provided."""
        with patch(
            "app.clients.youtube.google_auth_oauthlib.flow.InstalledAppFlow"
        ) as mock_flow_cls:
            with patch(
                "app.clients.youtube.googleapiclient.discovery.build"
            ) as mock_build:
                mock_flow = MagicMock()
                mock_credentials = MagicMock()
                mock_flow.run_console.return_value = mock_credentials
                mock_flow_cls.from_client_secrets_file.return_value = mock_flow

                YouTubeAPI(
                    client_secrets_file="client_secrets.json", api_key="test_api_key"
                )

                # Verify OAuth was used (not API key)
                mock_build.assert_called_once_with(
                    "youtube", "v3", credentials=mock_credentials
                )


class TestYouTubeAPISyncMethods:
    """Test synchronous YouTube API methods."""

    def test_channels_list_executes_request(self):
        """Test that channels_list executes the API request."""
        with patch("app.clients.youtube.googleapiclient.discovery.build") as mock_build:
            # Mock the chained API calls: youtube.channels().list().execute()
            mock_execute = MagicMock(return_value={"items": []})
            mock_list = MagicMock(return_value=MagicMock(execute=mock_execute))
            mock_channels = MagicMock(return_value=MagicMock(list=mock_list))
            mock_youtube = MagicMock(channels=mock_channels)
            mock_build.return_value = mock_youtube

            client = YouTubeAPI(api_key="test_key")
            result = client.channels_list(part="snippet", id="UC123")

            # Verify the chain was called correctly
            mock_channels.assert_called_once()
            mock_list.assert_called_once_with(part="snippet", id="UC123")
            mock_execute.assert_called_once()
            assert result == {"items": []}

    def test_playlist_items_list_executes_request(self):
        """Test that playlist_items_list executes the API request."""
        with patch("app.clients.youtube.googleapiclient.discovery.build") as mock_build:
            mock_execute = MagicMock(return_value={"items": []})
            mock_list = MagicMock(return_value=MagicMock(execute=mock_execute))
            mock_playlist_items = MagicMock(return_value=MagicMock(list=mock_list))
            mock_youtube = MagicMock(playlistItems=mock_playlist_items)
            mock_build.return_value = mock_youtube

            client = YouTubeAPI(api_key="test_key")
            result = client.playlist_items_list(part="snippet", playlistId="PL123")

            mock_playlist_items.assert_called_once()
            mock_list.assert_called_once_with(part="snippet", playlistId="PL123")
            mock_execute.assert_called_once()
            assert result == {"items": []}

    def test_playlists_list_executes_request(self):
        """Test that playlists_list executes the API request."""
        with patch("app.clients.youtube.googleapiclient.discovery.build") as mock_build:
            mock_execute = MagicMock(return_value={"items": []})
            mock_list = MagicMock(return_value=MagicMock(execute=mock_execute))
            mock_playlists = MagicMock(return_value=MagicMock(list=mock_list))
            mock_youtube = MagicMock(playlists=mock_playlists)
            mock_build.return_value = mock_youtube

            client = YouTubeAPI(api_key="test_key")
            result = client.playlists_list(part="snippet", channelId="UC123")

            mock_playlists.assert_called_once()
            mock_list.assert_called_once_with(part="snippet", channelId="UC123")
            mock_execute.assert_called_once()
            assert result == {"items": []}

    def test_videos_list_executes_request(self):
        """Test that videos_list executes the API request."""
        with patch("app.clients.youtube.googleapiclient.discovery.build") as mock_build:
            mock_execute = MagicMock(return_value={"items": []})
            mock_list = MagicMock(return_value=MagicMock(execute=mock_execute))
            mock_videos = MagicMock(return_value=MagicMock(list=mock_list))
            mock_youtube = MagicMock(videos=mock_videos)
            mock_build.return_value = mock_youtube

            client = YouTubeAPI(api_key="test_key")
            result = client.videos_list(part="snippet", id="video123")

            mock_videos.assert_called_once()
            mock_list.assert_called_once_with(part="snippet", id="video123")
            mock_execute.assert_called_once()
            assert result == {"items": []}


@pytest.mark.asyncio
class TestYouTubeAPIAsyncMethods:
    """Test asynchronous YouTube API methods."""

    async def test_channels_list_async_wraps_in_thread(self):
        """Test that channels_list_async uses asyncio.to_thread."""
        with patch("app.clients.youtube.googleapiclient.discovery.build") as mock_build:
            with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = {"items": []}

                # Setup mock chain
                mock_execute = MagicMock()
                mock_list = MagicMock(return_value=MagicMock(execute=mock_execute))
                mock_channels = MagicMock(return_value=MagicMock(list=mock_list))
                mock_youtube = MagicMock(channels=mock_channels)
                mock_build.return_value = mock_youtube

                client = YouTubeAPI(api_key="test_key")
                result = await client.channels_list_async(part="snippet")

                # Verify asyncio.to_thread was called
                mock_to_thread.assert_called_once()
                assert result == {"items": []}

    async def test_playlist_items_list_async_wraps_in_thread(self):
        """Test that playlist_items_list_async uses asyncio.to_thread."""
        with patch("app.clients.youtube.googleapiclient.discovery.build") as mock_build:
            with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = {"items": []}

                mock_execute = MagicMock()
                mock_list = MagicMock(return_value=MagicMock(execute=mock_execute))
                mock_playlist_items = MagicMock(return_value=MagicMock(list=mock_list))
                mock_youtube = MagicMock(playlistItems=mock_playlist_items)
                mock_build.return_value = mock_youtube

                client = YouTubeAPI(api_key="test_key")
                result = await client.playlist_items_list_async(part="snippet")

                mock_to_thread.assert_called_once()
                assert result == {"items": []}

    async def test_playlists_list_async_wraps_in_thread(self):
        """Test that playlists_list_async uses asyncio.to_thread."""
        with patch("app.clients.youtube.googleapiclient.discovery.build") as mock_build:
            with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = {"items": []}

                mock_execute = MagicMock()
                mock_list = MagicMock(return_value=MagicMock(execute=mock_execute))
                mock_playlists = MagicMock(return_value=MagicMock(list=mock_list))
                mock_youtube = MagicMock(playlists=mock_playlists)
                mock_build.return_value = mock_youtube

                client = YouTubeAPI(api_key="test_key")
                result = await client.playlists_list_async(part="snippet")

                mock_to_thread.assert_called_once()
                assert result == {"items": []}

    async def test_videos_list_async_wraps_in_thread(self):
        """Test that videos_list_async uses asyncio.to_thread."""
        with patch("app.clients.youtube.googleapiclient.discovery.build") as mock_build:
            with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = {"items": []}

                mock_execute = MagicMock()
                mock_list = MagicMock(return_value=MagicMock(execute=mock_execute))
                mock_videos = MagicMock(return_value=MagicMock(list=mock_list))
                mock_youtube = MagicMock(videos=mock_videos)
                mock_build.return_value = mock_youtube

                client = YouTubeAPI(api_key="test_key")
                result = await client.videos_list_async(part="snippet")

                mock_to_thread.assert_called_once()
                assert result == {"items": []}


class TestYouTubeAPIGetChannelInfo:
    """Test get_channel_info method with different parameters."""

    def test_get_channel_info_by_channel_id(self):
        """Test getting channel info by channel ID."""
        with patch("app.clients.youtube.googleapiclient.discovery.build") as mock_build:
            mock_execute = MagicMock(return_value={"items": [{"id": "UC123"}]})
            mock_list = MagicMock(return_value=MagicMock(execute=mock_execute))
            mock_channels = MagicMock(return_value=MagicMock(list=mock_list))
            mock_youtube = MagicMock(channels=mock_channels)
            mock_build.return_value = mock_youtube

            client = YouTubeAPI(api_key="test_key")
            result = client.get_channel_info(channel_id="UC123")

            # Verify list was called with channel_id
            mock_list.assert_called_once()
            call_kwargs = mock_list.call_args[1]
            assert call_kwargs["id"] == "UC123"
            assert result == {"items": [{"id": "UC123"}]}

    def test_get_channel_info_by_handle(self):
        """Test getting channel info by handle."""
        with patch("app.clients.youtube.googleapiclient.discovery.build") as mock_build:
            mock_execute = MagicMock(return_value={"items": [{"handle": "@test"}]})
            mock_list = MagicMock(return_value=MagicMock(execute=mock_execute))
            mock_channels = MagicMock(return_value=MagicMock(list=mock_list))
            mock_youtube = MagicMock(channels=mock_channels)
            mock_build.return_value = mock_youtube

            client = YouTubeAPI(api_key="test_key")
            result = client.get_channel_info(handle="@test")

            # Verify list was called with forHandle
            call_kwargs = mock_list.call_args[1]
            assert call_kwargs["forHandle"] == "@test"
            assert result == {"items": [{"handle": "@test"}]}

    def test_get_channel_info_by_username(self):
        """Test getting channel info by username (legacy) with handle."""
        with patch("app.clients.youtube.googleapiclient.discovery.build") as mock_build:
            mock_execute = MagicMock(return_value={"items": [{"username": "testuser"}]})
            mock_list = MagicMock(return_value=MagicMock(execute=mock_execute))
            mock_channels = MagicMock(return_value=MagicMock(list=mock_list))
            mock_youtube = MagicMock(channels=mock_channels)
            mock_build.return_value = mock_youtube

            client = YouTubeAPI(api_key="test_key")
            # Note: username alone doesn't pass validation, need handle or channel_id
            result = client.get_channel_info(handle="@testuser", username="testuser")

            # Verify list was called with forUsername
            call_kwargs = mock_list.call_args[1]
            assert call_kwargs["forUsername"] == "testuser"
            assert call_kwargs["forHandle"] == "@testuser"
            assert result == {"items": [{"username": "testuser"}]}

    def test_get_channel_info_no_params_raises(self):
        """Test that get_channel_info without params raises ValueError."""
        with patch("app.clients.youtube.googleapiclient.discovery.build") as mock_build:
            mock_youtube = MagicMock()
            mock_build.return_value = mock_youtube

            client = YouTubeAPI(api_key="test_key")

            with pytest.raises(ValueError) as exc_info:
                client.get_channel_info()

            assert "must provide either" in str(exc_info.value).lower()


class TestYouTubeAPIManager:
    """Test YouTubeAPIManager for lazy client initialization."""

    def test_init_client_creates_youtube_api(self):
        """Test that init_client creates a YouTubeAPI instance."""
        with patch("app.clients.youtube.YouTubeAPI") as mock_youtube_api_cls:
            mock_client = MagicMock()
            mock_youtube_api_cls.return_value = mock_client

            manager = YouTubeAPIManager(api_key="test_key")
            manager.init_client()

            # Verify YouTubeAPI was created with API key
            mock_youtube_api_cls.assert_called_once_with(api_key="test_key")
            assert manager._client == mock_client

    def test_init_client_without_api_key_raises(self):
        """Test that init_client without API key raises ValueError."""
        manager = YouTubeAPIManager(api_key=None)

        with pytest.raises(ValueError) as exc_info:
            manager.init_client()

        assert "No YOUTUBE_API_KEY" in str(exc_info.value)

    def test_get_client_lazy_initialization(self):
        """Test that get_client initializes client lazily."""
        with patch("app.clients.youtube.YouTubeAPI") as mock_youtube_api_cls:
            mock_client = MagicMock()
            mock_youtube_api_cls.return_value = mock_client

            manager = YouTubeAPIManager(api_key="test_key")
            assert manager._client is None  # Not initialized yet

            # Use context manager
            with manager.get_client() as client:
                assert client == mock_client

            # Verify client was created
            assert manager._client == mock_client

    def test_get_client_reuses_existing_client(self):
        """Test that get_client reuses existing client."""
        with patch("app.clients.youtube.YouTubeAPI") as mock_youtube_api_cls:
            mock_client = MagicMock()
            mock_youtube_api_cls.return_value = mock_client

            manager = YouTubeAPIManager(api_key="test_key")
            manager.init_client()  # Initialize first time

            # Use context manager multiple times
            with manager.get_client():
                pass
            with manager.get_client():
                pass

            # Should only be called once (reused)
            mock_youtube_api_cls.assert_called_once()


class TestGetYouTubeApiDependency:
    """Test get_youtube_api dependency injection helper."""

    def test_get_youtube_api_returns_client(self):
        """Test that get_youtube_api returns initialized client."""
        with patch("app.clients.youtube.youtube_api_manager") as mock_manager:
            mock_client = MagicMock()
            mock_manager._client = mock_client

            result = get_youtube_api()

            assert result == mock_client

    def test_get_youtube_api_initializes_if_needed(self):
        """Test that get_youtube_api initializes manager if client is None."""
        with patch("app.clients.youtube.youtube_api_manager") as mock_manager:
            mock_manager._client = None
            mock_client = MagicMock()
            mock_manager.init_client = MagicMock()

            # After init_client is called, set the client
            def set_client():
                mock_manager._client = mock_client

            mock_manager.init_client.side_effect = set_client

            result = get_youtube_api()

            mock_manager.init_client.assert_called_once()
            assert result == mock_client
