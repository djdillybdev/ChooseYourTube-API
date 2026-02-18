"""
Tests for playlist service layer.

Tests business logic, validation, and HTTPException handling for
all playlist service functions.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from fastapi import HTTPException

from app.services.playlist_service import (
    get_all_playlists,
    get_playlist_by_id,
    get_playlist_detail,
    create_new_playlist,
    update_playlist,
    delete_playlist_by_id,
    set_playlist_videos,
    add_video_to_playlist,
    add_videos_to_playlist,
    move_video_in_playlist,
    set_playlist_position,
    remove_video_from_playlist,
    clear_playlist,
    shuffle_playlist,
)
from app.schemas.playlist import (
    PlaylistCreate,
    PlaylistUpdate,
    PlaylistSetVideos,
    PlaylistAddVideo,
    PlaylistAddVideos,
    PlaylistMoveVideo,
    PlaylistSetPosition,
)
from app.db.models.playlist import Playlist
from app.db.models.channel import Channel
from app.db.models.video import Video
from app.db.crud.crud_playlist import set_playlist_videos as crud_set_videos


@pytest_asyncio.fixture
async def sample_channel(db_session):
    """Create a sample channel for video FK requirements."""
    channel = Channel(
        id="CH_service_test",
        handle="servicetest",
        title="Service Test Channel",
        uploads_playlist_id="UU_service_test",
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
            id=f"SV{i:03d}",
            channel_id=sample_channel.id,
            title=f"Service Video {i}",
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
        id="PL_service_1",
        name="Service Test Playlist",
        description="Service test",
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
        id="PL_with_vids",
        name="Playlist With Videos",
        is_system=False,
    )
    db_session.add(playlist)

    videos = []
    for i in range(1, 4):
        video = Video(
            id=f"SPV{i:03d}",
            channel_id=sample_channel.id,
            title=f"Service PL Video {i}",
            published_at=datetime.now(timezone.utc),
            duration_seconds=300,
            is_short=False,
        )
        db_session.add(video)
        videos.append(video)

    await db_session.commit()
    await db_session.refresh(playlist)

    # Add videos to playlist
    await crud_set_videos(db_session, playlist.id, [v.id for v in videos])

    return playlist


@pytest_asyncio.fixture
async def channel_sourced_playlist(db_session):
    """Create a read-only channel-sourced playlist."""
    playlist = Playlist(
        id="PL_channel_1",
        name="Channel Playlist",
        is_system=True,
        source_type="channel",
        source_channel_id="CH_service_test",
        source_youtube_playlist_id="PL_yt_channel_1",
    )
    db_session.add(playlist)
    await db_session.commit()
    await db_session.refresh(playlist)
    return playlist


@pytest.mark.asyncio
class TestGetAllPlaylists:
    """Tests for get_all_playlists() service function."""

    async def test_returns_paginated_response(self, db_session, sample_playlist):
        """Should return PaginatedResponse with playlists."""
        response = await get_all_playlists(db_session)

        assert response.total == 1
        assert len(response.items) == 1
        assert response.items[0].id == sample_playlist.id
        assert response.has_more is False

    async def test_filters_by_is_system(self, db_session):
        """Should filter by is_system flag."""
        # Create system and non-system playlists
        system_pl = Playlist(id="PL_sys", name="System", is_system=True)
        user_pl = Playlist(id="PL_user", name="User", is_system=False)
        db_session.add(system_pl)
        db_session.add(user_pl)
        await db_session.commit()

        response = await get_all_playlists(db_session, is_system=True)

        assert response.total == 1
        assert response.items[0].is_system is True

    async def test_empty_result(self, db_session):
        """Should return empty items list when no playlists."""
        response = await get_all_playlists(db_session)

        assert response.total == 0
        assert response.items == []


@pytest.mark.asyncio
class TestGetPlaylistById:
    """Tests for get_playlist_by_id() service function."""

    async def test_returns_playlist(self, db_session, sample_playlist):
        """Should return playlist by ID."""
        playlist = await get_playlist_by_id(sample_playlist.id, db_session)

        assert playlist.id == sample_playlist.id
        assert playlist.name == sample_playlist.name

    async def test_raises_404_for_missing_id(self, db_session):
        """Should raise HTTPException 404 when playlist not found."""
        with pytest.raises(HTTPException) as exc_info:
            await get_playlist_by_id("nonexistent", db_session)

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()


@pytest.mark.asyncio
class TestGetPlaylistDetail:
    """Tests for get_playlist_detail() service function."""

    async def test_returns_detail_with_video_ids(
        self, db_session, sample_playlist_with_videos
    ):
        """Should return PlaylistDetailOut with video_ids."""
        detail = await get_playlist_detail(sample_playlist_with_videos.id, db_session)

        assert detail.id == sample_playlist_with_videos.id
        assert detail.total_videos == 3
        assert len(detail.video_ids) == 3
        assert detail.video_ids == ["SPV001", "SPV002", "SPV003"]

    async def test_returns_detail_with_current_position(
        self, db_session, sample_playlist_with_videos
    ):
        """Should include current_position in detail."""
        # Set current position
        sample_playlist_with_videos.current_position = 1
        db_session.add(sample_playlist_with_videos)
        await db_session.commit()

        detail = await get_playlist_detail(sample_playlist_with_videos.id, db_session)

        assert detail.current_position == 1


@pytest.mark.asyncio
class TestCreateNewPlaylist:
    """Tests for create_new_playlist() service function."""

    async def test_creates_with_uuid(self, db_session):
        """Should create playlist with generated UUID."""
        payload = PlaylistCreate(
            name="New Playlist",
            description="New desc",
            is_system=False,
        )

        playlist = await create_new_playlist(payload, db_session)

        assert playlist.id is not None
        assert len(playlist.id) == 36  # UUID format
        assert playlist.name == "New Playlist"
        assert playlist.description == "New desc"

    async def test_sets_is_system_flag(self, db_session):
        """Should respect is_system flag from payload."""
        payload = PlaylistCreate(
            name="System Queue",
            is_system=True,
        )

        playlist = await create_new_playlist(payload, db_session)

        assert playlist.is_system is True


@pytest.mark.asyncio
class TestUpdatePlaylist:
    """Tests for update_playlist() service function."""

    async def test_updates_name(self, db_session, sample_playlist):
        """Should update playlist name."""
        payload = PlaylistUpdate(name="Updated Name")

        updated = await update_playlist(sample_playlist.id, payload, db_session)

        assert updated.name == "Updated Name"

    async def test_updates_description(self, db_session, sample_playlist):
        """Should update playlist description."""
        payload = PlaylistUpdate(description="New description")

        updated = await update_playlist(sample_playlist.id, payload, db_session)

        assert updated.description == "New description"

    async def test_raises_404_for_missing_playlist(self, db_session):
        """Should raise HTTPException 404 when playlist not found."""
        payload = PlaylistUpdate(name="Won't work")

        with pytest.raises(HTTPException) as exc_info:
            await update_playlist("nonexistent", payload, db_session)

        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
class TestDeletePlaylistById:
    """Tests for delete_playlist_by_id() service function."""

    async def test_deletes_existing_playlist(self, db_session, sample_playlist):
        """Should delete playlist by ID."""
        await delete_playlist_by_id(sample_playlist.id, db_session)

        # Verify it's gone
        with pytest.raises(HTTPException) as exc_info:
            await get_playlist_by_id(sample_playlist.id, db_session)

        assert exc_info.value.status_code == 404

    async def test_raises_404_for_missing_playlist(self, db_session):
        """Should raise HTTPException 404 when playlist not found."""
        with pytest.raises(HTTPException) as exc_info:
            await delete_playlist_by_id("nonexistent", db_session)

        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
class TestSetPlaylistVideos:
    """Tests for set_playlist_videos() service function."""

    async def test_sets_videos(self, db_session, sample_playlist, sample_videos):
        """Should set videos in playlist."""
        payload = PlaylistSetVideos(
            video_ids=[sample_videos[0].id, sample_videos[1].id]
        )

        detail = await set_playlist_videos(sample_playlist.id, payload, db_session)

        assert detail.total_videos == 2
        assert detail.video_ids == [sample_videos[0].id, sample_videos[1].id]

    async def test_validates_missing_video_ids(self, db_session, sample_playlist):
        """Should raise 400 when video IDs don't exist."""
        payload = PlaylistSetVideos(video_ids=["missing1", "missing2"])

        with pytest.raises(HTTPException) as exc_info:
            await set_playlist_videos(sample_playlist.id, payload, db_session)

        assert exc_info.value.status_code == 400
        assert "not found" in exc_info.value.detail.lower()

    async def test_resets_current_position_when_out_of_bounds(
        self, db_session, sample_playlist_with_videos
    ):
        """Should reset current_position when new list is shorter."""
        # Set position to 2 (last video)
        sample_playlist_with_videos.current_position = 2
        db_session.add(sample_playlist_with_videos)
        await db_session.commit()

        # Set only 1 video
        payload = PlaylistSetVideos(video_ids=["SPV001"])

        detail = await set_playlist_videos(
            sample_playlist_with_videos.id, payload, db_session
        )

        assert detail.current_position is None

    async def test_clears_position_when_emptied(
        self, db_session, sample_playlist_with_videos
    ):
        """Should clear current_position when playlist is emptied."""
        sample_playlist_with_videos.current_position = 1
        db_session.add(sample_playlist_with_videos)
        await db_session.commit()

        payload = PlaylistSetVideos(video_ids=[])

        detail = await set_playlist_videos(
            sample_playlist_with_videos.id, payload, db_session
        )

        assert detail.current_position is None


@pytest.mark.asyncio
class TestAddVideoToPlaylist:
    """Tests for add_video_to_playlist() service function."""

    async def test_adds_valid_video(self, db_session, sample_playlist, sample_videos):
        """Should add video to playlist."""
        payload = PlaylistAddVideo(video_id=sample_videos[0].id)

        detail = await add_video_to_playlist(sample_playlist.id, payload, db_session)

        assert detail.total_videos == 1
        assert sample_videos[0].id in detail.video_ids

    async def test_raises_404_for_missing_playlist(self, db_session, sample_videos):
        """Should raise 404 when playlist not found."""
        payload = PlaylistAddVideo(video_id=sample_videos[0].id)

        with pytest.raises(HTTPException) as exc_info:
            await add_video_to_playlist("nonexistent", payload, db_session)

        assert exc_info.value.status_code == 404

    async def test_raises_400_for_missing_video(self, db_session, sample_playlist):
        """Should raise 400 when video not found."""
        payload = PlaylistAddVideo(video_id="missing_video")

        with pytest.raises(HTTPException) as exc_info:
            await add_video_to_playlist(sample_playlist.id, payload, db_session)

        assert exc_info.value.status_code == 400
        assert "not found" in exc_info.value.detail.lower()


@pytest.mark.asyncio
class TestAddVideosToPlaylist:
    """Tests for add_videos_to_playlist() service function."""

    async def test_bulk_adds_valid_videos(
        self, db_session, sample_playlist, sample_videos
    ):
        """Should add multiple videos to playlist."""
        payload = PlaylistAddVideos(
            video_ids=[sample_videos[0].id, sample_videos[1].id]
        )

        detail = await add_videos_to_playlist(sample_playlist.id, payload, db_session)

        assert detail.total_videos == 2

    async def test_raises_400_for_any_missing_video_ids(
        self, db_session, sample_playlist, sample_videos
    ):
        """Should raise 400 if any video ID is missing."""
        payload = PlaylistAddVideos(video_ids=[sample_videos[0].id, "missing"])

        with pytest.raises(HTTPException) as exc_info:
            await add_videos_to_playlist(sample_playlist.id, payload, db_session)

        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
class TestMoveVideoInPlaylist:
    """Tests for move_video_in_playlist() service function."""

    async def test_moves_video(self, db_session, sample_playlist_with_videos):
        """Should move video to new position."""
        payload = PlaylistMoveVideo(
            video_id="SPV001",
            new_position=2,
        )

        detail = await move_video_in_playlist(
            sample_playlist_with_videos.id, payload, db_session
        )

        assert detail.video_ids[2] == "SPV001"

    async def test_raises_404_for_video_not_in_playlist(
        self, db_session, sample_playlist_with_videos
    ):
        """Should raise 404 when video not in playlist."""
        payload = PlaylistMoveVideo(
            video_id="missing",
            new_position=0,
        )

        with pytest.raises(HTTPException) as exc_info:
            await move_video_in_playlist(
                sample_playlist_with_videos.id, payload, db_session
            )

        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
class TestSetPlaylistPosition:
    """Tests for set_playlist_position() service function."""

    async def test_sets_valid_position(self, db_session, sample_playlist_with_videos):
        """Should set current position to valid value."""
        payload = PlaylistSetPosition(current_position=1)

        detail = await set_playlist_position(
            sample_playlist_with_videos.id, payload, db_session
        )

        assert detail.current_position == 1

    async def test_clears_position_with_null(
        self, db_session, sample_playlist_with_videos
    ):
        """Should clear position when set to None."""
        sample_playlist_with_videos.current_position = 1
        db_session.add(sample_playlist_with_videos)
        await db_session.commit()

        payload = PlaylistSetPosition(current_position=None)

        detail = await set_playlist_position(
            sample_playlist_with_videos.id, payload, db_session
        )

        assert detail.current_position is None

    async def test_raises_400_for_empty_playlist(self, db_session, sample_playlist):
        """Should raise 400 when trying to set position on empty playlist."""
        payload = PlaylistSetPosition(current_position=0)

        with pytest.raises(HTTPException) as exc_info:
            await set_playlist_position(sample_playlist.id, payload, db_session)

        assert exc_info.value.status_code == 400
        assert "empty" in exc_info.value.detail.lower()

    async def test_raises_400_for_out_of_bounds(
        self, db_session, sample_playlist_with_videos
    ):
        """Should raise 400 when position is out of bounds."""
        payload = PlaylistSetPosition(current_position=99)

        with pytest.raises(HTTPException) as exc_info:
            await set_playlist_position(
                sample_playlist_with_videos.id, payload, db_session
            )

        assert exc_info.value.status_code == 400
        assert "out of bounds" in exc_info.value.detail.lower()


@pytest.mark.asyncio
class TestRemoveVideoFromPlaylist:
    """Tests for remove_video_from_playlist() service function."""

    async def test_removes_video(self, db_session, sample_playlist_with_videos):
        """Should remove video from playlist."""
        await remove_video_from_playlist(
            sample_playlist_with_videos.id, "SPV002", db_session
        )

        detail = await get_playlist_detail(sample_playlist_with_videos.id, db_session)
        assert detail.total_videos == 2
        assert "SPV002" not in detail.video_ids

    async def test_raises_404_for_missing_video(
        self, db_session, sample_playlist_with_videos
    ):
        """Should raise 404 when video not in playlist."""
        with pytest.raises(HTTPException) as exc_info:
            await remove_video_from_playlist(
                sample_playlist_with_videos.id, "missing", db_session
            )

        assert exc_info.value.status_code == 404

    async def test_adjusts_current_position_when_before_current(
        self, db_session, sample_playlist_with_videos
    ):
        """Should decrement current_position when removing video before it."""
        # Set position to 2
        sample_playlist_with_videos.current_position = 2
        db_session.add(sample_playlist_with_videos)
        await db_session.commit()

        # Remove video at position 0
        await remove_video_from_playlist(
            sample_playlist_with_videos.id, "SPV001", db_session
        )

        detail = await get_playlist_detail(sample_playlist_with_videos.id, db_session)
        assert detail.current_position == 1

    async def test_resets_position_when_playlist_empties(
        self, db_session, sample_playlist_with_videos
    ):
        """Should clear current_position when last video removed."""
        sample_playlist_with_videos.current_position = 0
        db_session.add(sample_playlist_with_videos)
        await db_session.commit()

        # Remove all videos
        await remove_video_from_playlist(
            sample_playlist_with_videos.id, "SPV001", db_session
        )
        await remove_video_from_playlist(
            sample_playlist_with_videos.id, "SPV002", db_session
        )
        await remove_video_from_playlist(
            sample_playlist_with_videos.id, "SPV003", db_session
        )

        detail = await get_playlist_detail(sample_playlist_with_videos.id, db_session)
        assert detail.current_position is None


@pytest.mark.asyncio
class TestClearPlaylist:
    """Tests for clear_playlist() service function."""

    async def test_clears_videos_and_resets_position(
        self, db_session, sample_playlist_with_videos
    ):
        """Should clear all videos and reset position."""
        sample_playlist_with_videos.current_position = 1
        db_session.add(sample_playlist_with_videos)
        await db_session.commit()

        detail = await clear_playlist(sample_playlist_with_videos.id, db_session)

        assert detail.total_videos == 0
        assert detail.video_ids == []
        assert detail.current_position is None

    async def test_no_error_on_empty_playlist(self, db_session, sample_playlist):
        """Should work without error on already empty playlist."""
        detail = await clear_playlist(sample_playlist.id, db_session)

        assert detail.total_videos == 0


@pytest.mark.asyncio
class TestShufflePlaylist:
    """Tests for shuffle_playlist() service function."""

    async def test_shuffles_preserving_current_video(
        self, db_session, sample_playlist_with_videos
    ):
        """Should shuffle videos after current position, preserving current."""
        # Set current position to 0
        sample_playlist_with_videos.current_position = 0
        db_session.add(sample_playlist_with_videos)
        await db_session.commit()

        original_ids = ["SPV001", "SPV002", "SPV003"]

        detail = await shuffle_playlist(sample_playlist_with_videos.id, db_session)

        # First video should stay the same
        assert detail.video_ids[0] == original_ids[0]
        # Should have same videos (just reordered)
        assert set(detail.video_ids) == set(original_ids)
        assert detail.total_videos == 3

    async def test_shuffles_all_when_no_position(
        self, db_session, sample_playlist_with_videos
    ):
        """Should shuffle all videos when no current position."""
        detail = await shuffle_playlist(sample_playlist_with_videos.id, db_session)

        # Should have same videos
        assert set(detail.video_ids) == {"SPV001", "SPV002", "SPV003"}
        assert detail.total_videos == 3

    async def test_no_op_for_single_or_empty_playlist(
        self, db_session, sample_playlist, sample_videos
    ):
        """Should return unchanged for single video or empty playlist."""
        # Test empty
        detail = await shuffle_playlist(sample_playlist.id, db_session)
        assert detail.total_videos == 0

        # Add one video
        from app.db.crud.crud_playlist import add_video_to_playlist as crud_add

        await crud_add(db_session, sample_playlist.id, sample_videos[0].id)

        # Test single video
        detail = await shuffle_playlist(sample_playlist.id, db_session)
        assert detail.total_videos == 1


@pytest.mark.asyncio
class TestReadOnlyChannelPlaylists:
    """Channel-sourced playlists should not allow structural mutation."""

    async def test_update_playlist_forbidden(self, db_session, channel_sourced_playlist):
        with pytest.raises(HTTPException) as exc_info:
            await update_playlist(
                channel_sourced_playlist.id,
                PlaylistUpdate(name="nope"),
                db_session,
            )

        assert exc_info.value.status_code == 403

    async def test_set_playlist_videos_forbidden(
        self, db_session, channel_sourced_playlist
    ):
        with pytest.raises(HTTPException) as exc_info:
            await set_playlist_videos(
                channel_sourced_playlist.id,
                PlaylistSetVideos(video_ids=[]),
                db_session,
            )

        assert exc_info.value.status_code == 403
