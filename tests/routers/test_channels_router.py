"""
Tests for channels router endpoints.

Tests the API endpoints for channel management, including
listing, creating, updating, refreshing, and deleting channels.
"""

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
class TestChannelsRouter:
    """Test channels router endpoints."""

    async def test_read_all_channels_empty(self, test_client, db_session):
        """Test GET /channels/ returns empty list when no channels exist."""
        response = test_client.get("/channels/")

        assert response.status_code == 200
        assert response.json()["total"] == 0

    async def test_read_all_channels_with_data(self, test_client, db_session):
        """Test GET /channels/ returns list of channels."""
        # Create sample channels
        from app.db.models.channel import Channel

        channel1 = Channel(
            id="UC_test_1",
            handle="testchannel1",
            title="Test Channel 1",
            uploads_playlist_id="UU_test_1",
        )
        channel2 = Channel(
            id="UC_test_2",
            handle="testchannel2",
            title="Test Channel 2",
            uploads_playlist_id="UU_test_2",
        )

        db_session.add(channel1)
        db_session.add(channel2)
        await db_session.commit()

        response = test_client.get("/channels/")

        assert response.status_code == 200
        data = response.json()
        data = data["items"]
        assert len(data) == 2
        assert data[0]["id"] == "UC_test_1"
        assert data[1]["id"] == "UC_test_2"

    async def test_read_channel_by_id_success(self, test_client, db_session):
        """Test GET /channels/{id} returns channel by ID."""
        from app.db.models.channel import Channel

        channel = Channel(
            id="UC_test_channel",
            handle="testchannel",
            title="Test Channel",
            uploads_playlist_id="UU_test",
        )
        db_session.add(channel)
        await db_session.commit()

        response = test_client.get("/channels/UC_test_channel")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "UC_test_channel"
        assert data["handle"] == "testchannel"
        assert data["title"] == "Test Channel"

    async def test_read_channel_by_id_not_found(self, test_client, db_session):
        """Test GET /channels/{id} returns 404 for non-existent channel."""
        response = test_client.get("/channels/UC_nonexistent")

        assert response.status_code == 404

    async def test_create_channel_enqueues_background_job(
        self, test_client, mock_youtube_api, mock_arq_redis
    ):
        """Test POST /channels/ creates channel and enqueues background job."""
        # Mock YouTube API response
        youtube_response = {
            "items": [{
                "id": "UC_new_channel",
                "snippet": {
                    "title": "New Channel",
                    "description": "Test Description",
                    "thumbnails": {
                        "high": {"url": "https://example.com/thumb.jpg"}
                    }
                },
                "contentDetails": {
                    "relatedPlaylists": {
                        "uploads": "UU_new_uploads"
                    }
                }
            }]
        }

        # Mock asyncio.to_thread to return the YouTube response
        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = youtube_response

            response = test_client.post(
                "/channels/",
                json={"handle": "@newchannel"}
            )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "UC_new_channel"
        assert data["handle"] == "newchannel"  # @ stripped

        # Verify background job was enqueued
        mock_arq_redis.enqueue_job.assert_called_once_with(
            "fetch_and_store_all_channel_videos_task",
            channel_id="UC_new_channel"
        )

    async def test_create_channel_with_folder(
        self, test_client, mock_youtube_api, db_session
    ):
        """Test POST /channels/ creates channel with folder assignment."""
        # Create a folder first
        from app.db.models.folder import Folder
        folder = Folder(id=1, name="Test Folder", parent_id=None)
        db_session.add(folder)
        await db_session.commit()

        # Mock YouTube API response
        youtube_response = {
            "items": [{
                "id": "UC_with_folder",
                "snippet": {
                    "title": "Channel with Folder",
                    "thumbnails": {}
                },
                "contentDetails": {
                    "relatedPlaylists": {
                        "uploads": "UU_with_folder"
                    }
                }
            }]
        }

        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = youtube_response

            response = test_client.post(
                "/channels/",
                json={"handle": "@channelwithfolder", "folder_id": 1}
            )

        assert response.status_code == 201
        data = response.json()
        assert data["folder_id"] == 1

    async def test_update_channel_favorite_status(self, test_client, db_session):
        """Test PATCH /channels/{id} updates channel favorite status."""
        from app.db.models.channel import Channel

        channel = Channel(
            id="UC_update_test",
            handle="updatetest",
            title="Update Test",
            uploads_playlist_id="UU_update_test",
            is_favorited=False
        )
        db_session.add(channel)
        await db_session.commit()

        response = test_client.patch(
            "/channels/UC_update_test",
            json={"is_favorited": True}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_favorited"] is True

    async def test_update_channel_move_to_folder(self, test_client, db_session):
        """Test PATCH /channels/{id} moves channel to folder."""
        from app.db.models.channel import Channel
        from app.db.models.folder import Folder

        # Create folder and channel
        folder = Folder(id=1, name="Test Folder", parent_id=None)
        channel = Channel(
            id="UC_move_test",
            handle="movetest",
            title="Move Test",
            uploads_playlist_id="UU_move_test",
            folder_id=None
        )
        db_session.add(folder)
        db_session.add(channel)
        await db_session.commit()

        response = test_client.patch(
            "/channels/UC_move_test",
            json={"folder_id": 1}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["folder_id"] == 1

    async def test_refresh_channel_endpoint(
        self, test_client, db_session, mock_youtube_api, mock_feedparser
    ):
        """Test POST /channels/{id}/refresh refreshes channel videos."""
        from app.db.models.channel import Channel
        from unittest.mock import MagicMock

        # Create channel
        channel = Channel(
            id="UC_refresh_test",
            handle="refreshtest",
            title="Refresh Test",
            uploads_playlist_id="UU_refresh_test",
        )
        db_session.add(channel)
        await db_session.commit()

        # Mock empty RSS feed (refresh_latest_channel_videos will be called)
        empty_feed = MagicMock()
        empty_feed.entries = []
        mock_feedparser.return_value = empty_feed

        # Mock refresh function to avoid actual API calls
        with patch('app.services.channel_service.refresh_latest_channel_videos') as mock_refresh:
            mock_refresh.return_value = None

            response = test_client.post("/channels/UC_refresh_test/refresh")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "UC_refresh_test"

        # Verify refresh was called
        mock_refresh.assert_called_once()

    async def test_delete_channel_by_id(self, test_client, db_session):
        """Test DELETE /channels/{id} deletes channel."""
        from app.db.models.channel import Channel

        channel = Channel(
            id="UC_delete_test",
            handle="deletetest",
            title="Delete Test",
            uploads_playlist_id="UU_delete_test",
        )
        db_session.add(channel)
        await db_session.commit()

        response = test_client.delete("/channels/UC_delete_test")

        assert response.status_code == 204
        # assert "deleted" in response.json()["message"].lower()

        # Verify channel is gone
        from sqlalchemy import select
        result = await db_session.execute(
            select(Channel).where(Channel.id == "UC_delete_test")
        )
        assert result.scalar_one_or_none() is None

    async def test_delete_all_channels(self, test_client, db_session):
        """Test DELETE /channels/ deletes all channels."""
        from app.db.models.channel import Channel

        # Create multiple channels
        channel1 = Channel(
            id="UC_delete_1",
            handle="delete1",
            title="Delete 1",
            uploads_playlist_id="UU_delete_1",
        )
        channel2 = Channel(
            id="UC_delete_2",
            handle="delete2",
            title="Delete 2",
            uploads_playlist_id="UU_delete_2",
        )
        db_session.add(channel1)
        db_session.add(channel2)
        await db_session.commit()

        response = test_client.delete("/channels/?confirm=DELETE_ALL_CHANNELS")

        assert response.status_code == 204
        # assert "2 channels" in response.json()["message"]

        # Verify all channels are gone
        from sqlalchemy import select
        result = await db_session.execute(select(Channel))
        assert len(result.scalars().all()) == 0
