"""
Tests for playlist router endpoints.

Tests API endpoints for playlist management, including HTTP status codes,
response shapes, and error handling.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone

from app.db.models.playlist import Playlist
from app.db.models.channel import Channel
from app.db.models.video import Video
from app.db.crud.crud_playlist import set_playlist_videos as crud_set_videos


@pytest_asyncio.fixture
async def sample_channel(db_session):
    """Create a sample channel for video FK requirements."""
    channel = Channel(
        id="CH_router_test",
        handle="routertest",
        title="Router Test Channel",
        uploads_playlist_id="UU_router_test",
    )
    db_session.add(channel)
    await db_session.commit()
    await db_session.refresh(channel)
    return channel


@pytest_asyncio.fixture
async def sample_videos(db_session, sample_channel):
    """Create 5 sample videos for testing."""
    videos = []
    for i in range(1, 6):
        video = Video(
            id=f"RV{i:03d}",
            channel_id=sample_channel.id,
            title=f"Router Video {i}",
            published_at=datetime.now(timezone.utc),
            duration_seconds=300,
            is_short=False,
        )
        db_session.add(video)
        videos.append(video)
    await db_session.commit()
    return videos


@pytest_asyncio.fixture
async def sample_playlist(db_session):
    """Create a sample empty playlist."""
    playlist = Playlist(
        id="PL_router_1",
        name="Router Test Playlist",
        description="Router test",
        is_system=False,
    )
    db_session.add(playlist)
    await db_session.commit()
    await db_session.refresh(playlist)
    return playlist


@pytest_asyncio.fixture
async def sample_playlist_with_videos(db_session, sample_channel):
    """Create a playlist with 3 videos."""
    playlist = Playlist(
        id="PL_router_vids",
        name="Router Playlist With Videos",
        is_system=False,
    )
    db_session.add(playlist)

    videos = []
    for i in range(1, 4):
        video = Video(
            id=f"RPV{i:03d}",
            channel_id=sample_channel.id,
            title=f"Router PL Video {i}",
            published_at=datetime.now(timezone.utc),
            duration_seconds=300,
            is_short=False,
        )
        db_session.add(video)
        videos.append(video)

    await db_session.commit()
    await db_session.refresh(playlist)

    # Add videos to playlist
    await crud_set_videos(
        db_session, playlist.id, [v.id for v in videos], owner_id=playlist.owner_id
    )

    return playlist


@pytest.mark.asyncio
class TestListPlaylists:
    """Tests for GET /playlists/ endpoint."""

    async def test_returns_200_with_paginated_response(
        self, test_client, db_session, sample_playlist
    ):
        """Should return 200 with paginated response structure."""
        response = test_client.get("/playlists/")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "items" in data
        assert "limit" in data
        assert "offset" in data
        assert "has_more" in data
        assert data["total"] == 1

    async def test_filter_by_is_system(self, test_client, db_session):
        """Should filter by is_system query parameter."""
        # Create system and non-system playlists
        system_pl = Playlist(id="PL_sys", name="System", is_system=True)
        user_pl = Playlist(id="PL_user", name="User", is_system=False)
        db_session.add(system_pl)
        db_session.add(user_pl)
        await db_session.commit()

        response = test_client.get("/playlists/?is_system=true")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["is_system"] is True

    async def test_empty_list(self, test_client, db_session):
        """Should return empty items list when no playlists."""
        response = test_client.get("/playlists/")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []


@pytest.mark.asyncio
class TestGetPlaylist:
    """Tests for GET /playlists/{playlist_id} endpoint."""

    async def test_returns_200_with_detail_response(
        self, test_client, db_session, sample_playlist_with_videos
    ):
        """Should return 200 with PlaylistDetailOut structure."""
        response = test_client.get(f"/playlists/{sample_playlist_with_videos.id}")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "name" in data
        assert "video_ids" in data
        assert "total_videos" in data
        assert "current_position" in data
        assert data["total_videos"] == 3
        assert len(data["video_ids"]) == 3

    async def test_returns_404_for_missing_playlist(self, test_client, db_session):
        """Should return 404 when playlist not found."""
        response = test_client.get("/playlists/nonexistent")

        assert response.status_code == 404


@pytest.mark.asyncio
class TestCreatePlaylist:
    """Tests for POST /playlists/ endpoint."""

    async def test_returns_201_with_playlist_out(self, test_client, db_session):
        """Should return 201 with PlaylistOut structure."""
        payload = {
            "name": "New Playlist",
            "description": "New description",
            "is_system": False,
        }

        response = test_client.post("/playlists/", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == "New Playlist"
        assert data["description"] == "New description"
        assert data["is_system"] is False

    async def test_validates_required_name_field(self, test_client, db_session):
        """Should return 422 when name is missing."""
        payload = {"description": "Missing name"}

        response = test_client.post("/playlists/", json=payload)

        assert response.status_code == 422


@pytest.mark.asyncio
class TestUpdatePlaylist:
    """Tests for PATCH /playlists/{playlist_id} endpoint."""

    async def test_returns_200_with_updated_fields(
        self, test_client, db_session, sample_playlist
    ):
        """Should return 200 with updated fields."""
        payload = {"name": "Updated Name"}

        response = test_client.patch(f"/playlists/{sample_playlist.id}", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"

    async def test_returns_404_for_missing_playlist(self, test_client, db_session):
        """Should return 404 when playlist not found."""
        payload = {"name": "Won't work"}

        response = test_client.patch("/playlists/nonexistent", json=payload)

        assert response.status_code == 404


@pytest.mark.asyncio
class TestDeletePlaylist:
    """Tests for DELETE /playlists/{playlist_id} endpoint."""

    async def test_returns_204_no_content(
        self, test_client, db_session, sample_playlist
    ):
        """Should return 204 with no content."""
        response = test_client.delete(f"/playlists/{sample_playlist.id}")

        assert response.status_code == 204
        assert response.content == b""

    async def test_returns_404_for_missing_playlist(self, test_client, db_session):
        """Should return 404 when playlist not found."""
        response = test_client.delete("/playlists/nonexistent")

        assert response.status_code == 404


@pytest.mark.asyncio
class TestSetPlaylistVideos:
    """Tests for PUT /playlists/{playlist_id}/videos endpoint."""

    async def test_returns_200_with_video_ids(
        self, test_client, db_session, sample_playlist, sample_videos
    ):
        """Should return 200 with video_ids in response."""
        payload = {"video_ids": [sample_videos[0].id, sample_videos[1].id]}

        response = test_client.put(
            f"/playlists/{sample_playlist.id}/videos", json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["video_ids"] == payload["video_ids"]
        assert data["total_videos"] == 2

    async def test_returns_400_for_invalid_video_ids(
        self, test_client, db_session, sample_playlist
    ):
        """Should return 400 when video IDs don't exist."""
        payload = {"video_ids": ["missing1", "missing2"]}

        response = test_client.put(
            f"/playlists/{sample_playlist.id}/videos", json=payload
        )

        assert response.status_code == 400

    async def test_returns_404_for_missing_playlist(
        self, test_client, db_session, sample_videos
    ):
        """Should return 404 when playlist not found."""
        payload = {"video_ids": [sample_videos[0].id]}

        response = test_client.put("/playlists/nonexistent/videos", json=payload)

        assert response.status_code == 404


@pytest.mark.asyncio
class TestAddVideoToPlaylist:
    """Tests for POST /playlists/{playlist_id}/videos endpoint."""

    async def test_returns_201_with_detail_response(
        self, test_client, db_session, sample_playlist, sample_videos
    ):
        """Should return 201 with detail response."""
        payload = {"video_id": sample_videos[0].id}

        response = test_client.post(
            f"/playlists/{sample_playlist.id}/videos", json=payload
        )

        assert response.status_code == 201
        data = response.json()
        assert data["total_videos"] == 1
        assert sample_videos[0].id in data["video_ids"]

    async def test_returns_400_for_nonexistent_video(
        self, test_client, db_session, sample_playlist
    ):
        """Should return 400 when video doesn't exist."""
        payload = {"video_id": "missing"}

        response = test_client.post(
            f"/playlists/{sample_playlist.id}/videos", json=payload
        )

        assert response.status_code == 400


@pytest.mark.asyncio
class TestBulkAddVideos:
    """Tests for POST /playlists/{playlist_id}/videos/bulk endpoint."""

    async def test_returns_201_with_detail_response(
        self, test_client, db_session, sample_playlist, sample_videos
    ):
        """Should return 201 with detail response."""
        payload = {"video_ids": [sample_videos[0].id, sample_videos[1].id]}

        response = test_client.post(
            f"/playlists/{sample_playlist.id}/videos/bulk", json=payload
        )

        assert response.status_code == 201
        data = response.json()
        assert data["total_videos"] == 2

    async def test_returns_400_for_missing_videos(
        self, test_client, db_session, sample_playlist, sample_videos
    ):
        """Should return 400 when any video is missing."""
        payload = {"video_ids": [sample_videos[0].id, "missing"]}

        response = test_client.post(
            f"/playlists/{sample_playlist.id}/videos/bulk", json=payload
        )

        assert response.status_code == 400


@pytest.mark.asyncio
class TestMoveVideo:
    """Tests for PATCH /playlists/{playlist_id}/videos/move endpoint."""

    async def test_returns_200_with_updated_order(
        self, test_client, db_session, sample_playlist_with_videos
    ):
        """Should return 200 with updated video order."""
        payload = {
            "video_id": "RPV001",
            "new_position": 2,
        }

        response = test_client.patch(
            f"/playlists/{sample_playlist_with_videos.id}/videos/move",
            json=payload,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["video_ids"][2] == "RPV001"

    async def test_returns_404_for_video_not_in_playlist(
        self, test_client, db_session, sample_playlist_with_videos
    ):
        """Should return 404 when video not in playlist."""
        payload = {
            "video_id": "missing",
            "new_position": 0,
        }

        response = test_client.patch(
            f"/playlists/{sample_playlist_with_videos.id}/videos/move",
            json=payload,
        )

        assert response.status_code == 404


@pytest.mark.asyncio
class TestSetPosition:
    """Tests for PATCH /playlists/{playlist_id}/position endpoint."""

    async def test_returns_200_with_updated_position(
        self, test_client, db_session, sample_playlist_with_videos
    ):
        """Should return 200 with updated current_position."""
        payload = {"current_position": 1}

        response = test_client.patch(
            f"/playlists/{sample_playlist_with_videos.id}/position",
            json=payload,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["current_position"] == 1

    async def test_returns_400_for_out_of_bounds(
        self, test_client, db_session, sample_playlist_with_videos
    ):
        """Should return 400 when position is out of bounds."""
        payload = {"current_position": 99}

        response = test_client.patch(
            f"/playlists/{sample_playlist_with_videos.id}/position",
            json=payload,
        )

        assert response.status_code == 400


@pytest.mark.asyncio
class TestShufflePlaylist:
    """Tests for POST /playlists/{playlist_id}/shuffle endpoint."""

    async def test_returns_200_with_shuffled_videos(
        self, test_client, db_session, sample_playlist_with_videos
    ):
        """Should return 200 with same video count."""
        response = test_client.post(
            f"/playlists/{sample_playlist_with_videos.id}/shuffle"
        )

        assert response.status_code == 200
        data = response.json()
        # Should have same videos
        assert data["total_videos"] == 3
        assert set(data["video_ids"]) == {"RPV001", "RPV002", "RPV003"}


@pytest.mark.asyncio
class TestClearPlaylistVideos:
    """Tests for DELETE /playlists/{playlist_id}/videos endpoint."""

    async def test_returns_200_with_empty_video_ids(
        self, test_client, db_session, sample_playlist_with_videos
    ):
        """Should return 200 with empty video_ids."""
        response = test_client.delete(
            f"/playlists/{sample_playlist_with_videos.id}/videos"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_videos"] == 0
        assert data["video_ids"] == []

    async def test_returns_404_for_missing_playlist(self, test_client, db_session):
        """Should return 404 when playlist not found."""
        response = test_client.delete("/playlists/nonexistent/videos")

        assert response.status_code == 404


@pytest.mark.asyncio
class TestRemoveVideo:
    """Tests for DELETE /playlists/{playlist_id}/videos/{video_id} endpoint."""

    async def test_returns_204_no_content(
        self, test_client, db_session, sample_playlist_with_videos
    ):
        """Should return 204 with no content."""
        response = test_client.delete(
            f"/playlists/{sample_playlist_with_videos.id}/videos/RPV002"
        )

        assert response.status_code == 204
        assert response.content == b""

    async def test_returns_404_for_missing_video(
        self, test_client, db_session, sample_playlist_with_videos
    ):
        """Should return 404 when video not in playlist."""
        response = test_client.delete(
            f"/playlists/{sample_playlist_with_videos.id}/videos/missing"
        )

        assert response.status_code == 404
