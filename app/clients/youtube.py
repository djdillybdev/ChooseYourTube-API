import os
import asyncio
from typing import Dict, Any, Iterator, List, Optional
from contextlib import contextmanager

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors

from ..core.config import settings


class YouTubeAPI:
    """
    A helper class to interact with the YouTube Data API using the
    googleapiclient.discovery library.

    Supports two authentication methods:
    1) OAuth 2.0 client credentials (for private or user-specific data).
    2) API Key (for public data, read-only).
    """

    def __init__(
        self,
        api_service_name: str = "youtube",
        api_version: str = "v3",
        client_secrets_file: Optional[str] = None,
        api_key: Optional[str] = None,
        scopes: Optional[List[str]] = None,
    ):
        """
        Initialize a YouTube client using either OAuth 2.0 or an API key.

        :param api_service_name: The name of the Google API service, defaults to "youtube".
        :param api_version: The version of the API, defaults to "v3".
        :param client_secrets_file: Path to OAuth2 client secrets JSON file (from Google Cloud Console).
        :param api_key: A public API key for read-only access to public resources.
        :param scopes: List of OAuth scopes; e.g., ["https://www.googleapis.com/auth/youtube.readonly"].
        """
        # If BOTH api_key and client_secrets_file are provided, we'll just prefer OAuth2.
        if client_secrets_file is not None:
            if not scopes:
                scopes = ["https://www.googleapis.com/auth/youtube.readonly"]
            # For local development only (disables HTTPS verification).
            # Do NOT use this in production.
            os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

            # Run the OAuth flow
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                client_secrets_file,
                scopes=scopes,
            )
            credentials = flow.run_console()
            self.youtube = googleapiclient.discovery.build(
                api_service_name, api_version, credentials=credentials
            )
        elif api_key is not None:
            # Build using an API key (sufficient for public data).
            self.youtube = googleapiclient.discovery.build(
                api_service_name, api_version, developerKey=api_key
            )
        else:
            raise ValueError(
                "Must provide either a client_secrets_file (OAuth) or an api_key."
            )

    def channels_list(self, **kwargs):
        return self.youtube.channels().list(**kwargs).execute()

    def playlist_items_list(self, **kwargs):
        return self.youtube.playlistItems().list(**kwargs).execute()

    def playlists_list(self, **kwargs):
        return self.youtube.playlists().list(**kwargs).execute()

    def videos_list(self, **kwargs):
        return self.youtube.videos().list(**kwargs).execute()

    async def channels_list_async(self, **kwargs):
        response = await asyncio.to_thread(
            self.youtube.channels().list(**kwargs).execute
        )
        return response

    async def playlist_items_list_async(self, **kwargs):
        response = await asyncio.to_thread(
            self.youtube.playlistItems().list(**kwargs).execute
        )
        return response

    async def playlists_list_async(self, **kwargs):
        response = await asyncio.to_thread(
            self.youtube.playlists().list(**kwargs).execute
        )
        return response

    async def videos_list_async(self, **kwargs):
        response = await asyncio.to_thread(self.youtube.videos().list(**kwargs).execute)
        return response

    def get_channel_info(
        self,
        channel_id: str = None,
        handle: str = None,
        username: str = None,
        parts: str = "snippet,contentDetails,statistics",
    ) -> Dict[str, Any]:
        """
        Retrieves channel details for a given channel ID or username.

        :param channel_id: The channel ID (e.g., UC_xxx...).
        :param handle: The channel handle
        :param username: The channel username (legacy).
        :param parts: The parts to request, default snippet,contentDetails,statistics.
        :return: The API response dict for the channel.
        """
        if not channel_id and not handle:
            raise ValueError(
                "You must provide either channel_id or handle or username."
            )

        request = self.youtube.channels().list(
            part=parts, id=channel_id, forHandle=handle, forUsername=username
        )
        response = request.execute()
        return response


class YouTubeAPIManager:
    def __init__(self, api_key: Optional[str] = None):
        """
        For this example, we assume an API key only (for read-only public data).
        """
        self._api_key = api_key
        self._client: Optional[YouTubeAPI] = None

    def init_client(self):
        """
        Create a single YouTubeAPI instance, stored on the manager.
        """
        if not self._api_key:
            raise ValueError("No YOUTUBE_API_KEY provided.")
        self._client = YouTubeAPI(api_key=self._api_key)

    @contextmanager
    def get_client(self) -> Iterator[YouTubeAPI]:
        """
        Yield the YouTubeAPI client. This is a plain context manager, not async,
        because the google client library is generally not async.
        """
        if self._client is None:
            self.init_client()

        yield self._client


youtube_api_manager = YouTubeAPIManager(api_key=settings.YOUTUBE_API_KEY)


def get_youtube_api() -> YouTubeAPI:
    """
    A simple dependency that returns the global YouTubeAPI instance.
    """
    # Ensure the manager has been initialized
    if youtube_api_manager._client is None:
        youtube_api_manager.init_client()
    return youtube_api_manager._client
