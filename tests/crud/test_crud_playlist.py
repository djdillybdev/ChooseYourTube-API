"""
Comprehensive tests for playlist CRUD operations.

Tests all playlist CRUD functions including:
- Basic get/create/delete operations
- Video associations (add, remove, move, bulk operations)
- Position management and ordering
- Edge cases and error handling
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from app.db.crud.crud_playlist import (
    get_playlists,
    count_playlists,
    create_playlist,
    delete_playlist,
    get_playlist_video_ids,
    get_max_position,
    set_playlist_videos,
    add_video_to_playlist,
    remove_video_from_playlist,
    move_video_in_playlist,
    bulk_add_videos_to_playlist,
    clear_playlist_videos,
)
from app.db.models.playlist import Playlist
from app.db.models.channel import Channel
from app.db.models.video import Video


@pytest_asyncio.fixture
async def sample_channel(db_session):
    """Create a sample channel for video FK requirements."""
    channel = Channel(
        id="CH_playlist_test",
        handle="playlisttest",
        title="Playlist Test Channel",
        uploads_playlist_id="UU_playlist_test",
    )
    db_session.add(channel)
    await db_session.commit()
    await db_session.refresh(channel)
    return channel


@pytest_asyncio.fixture
async def sample_videos(db_session, sample_channel):
    """Create 5 sample videos for testing playlist operations."""
    videos = []
    for i in range(1, 6):
        video = Video(
            id=f"VID{i:03d}",
            channel_id=sample_channel.id,
            title=f"Video {i}",
            description=f"Description {i}",
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
        id="PL_test_1",
        name="Test Playlist",
        description="A test playlist",
        is_system=False,
    )
    db_session.add(playlist)
    await db_session.commit()
    await db_session.refresh(playlist)
    return playlist


@pytest_asyncio.fixture
async def sample_playlist_with_videos(db_session, sample_channel):
    """Create a playlist with 3 videos at positions 0, 1, 2."""
    playlist = Playlist(
        id="PL_with_videos",
        name="Playlist With Videos",
        description="Has videos",
        is_system=False,
    )
    db_session.add(playlist)

    # Create 3 videos
    videos = []
    for i in range(1, 4):
        video = Video(
            id=f"VID_PL{i:03d}",
            channel_id=sample_channel.id,
            title=f"Playlist Video {i}",
            published_at=datetime.now(timezone.utc),
            duration_seconds=300,
            is_short=False,
        )
        db_session.add(video)
        videos.append(video)

    await db_session.commit()
    await db_session.refresh(playlist)

    # Add videos to playlist at positions 0, 1, 2
    await set_playlist_videos(db_session, playlist.id, [v.id for v in videos])

    return playlist


# Basic Filtering Tests


@pytest.mark.asyncio
class TestGetPlaylists:
    """Tests for get_playlists() function."""

    async def test_get_all_playlists(self, db_session, sample_playlist):
        """Should return all playlists when no filters applied."""
        playlists = await get_playlists(db_session)

        assert len(playlists) == 1
        assert playlists[0].id == sample_playlist.id
        assert playlists[0].name == "Test Playlist"

    async def test_filter_by_id(self, db_session, sample_playlist):
        """Should filter playlists by single ID."""
        playlist = await get_playlists(db_session, id=sample_playlist.id, first=True)

        assert playlist is not None
        assert playlist.id == sample_playlist.id

    async def test_filter_by_id_list(self, db_session, sample_playlist):
        """Should filter playlists by list of IDs."""
        # Create another playlist
        playlist2 = Playlist(
            id="PL_test_2",
            name="Test Playlist 2",
            is_system=False,
        )
        db_session.add(playlist2)
        await db_session.commit()

        playlists = await get_playlists(
            db_session, id=[sample_playlist.id, playlist2.id]
        )

        assert len(playlists) == 2
        ids = {p.id for p in playlists}
        assert ids == {sample_playlist.id, playlist2.id}

    async def test_filter_by_name(self, db_session, sample_playlist):
        """Should filter playlists by name."""
        playlists = await get_playlists(db_session, name="Test Playlist")

        assert len(playlists) == 1
        assert playlists[0].name == "Test Playlist"

    async def test_filter_by_is_system_false(self, db_session, sample_playlist):
        """Should filter non-system playlists."""
        playlists = await get_playlists(db_session, is_system=False)

        assert len(playlists) == 1
        assert playlists[0].is_system is False

    async def test_filter_by_is_system_true(self, db_session):
        """Should filter system playlists."""
        # Create a system playlist
        system_pl = Playlist(
            id="PL_system",
            name="System Playlist",
            is_system=True,
        )
        db_session.add(system_pl)
        await db_session.commit()

        playlists = await get_playlists(db_session, is_system=True)

        assert len(playlists) == 1
        assert playlists[0].is_system is True

    async def test_pagination_limit(self, db_session):
        """Should respect limit parameter."""
        # Create 3 playlists
        for i in range(3):
            pl = Playlist(id=f"PL_{i}", name=f"Playlist {i}", is_system=False)
            db_session.add(pl)
        await db_session.commit()

        playlists = await get_playlists(db_session, limit=2)

        assert len(playlists) == 2

    async def test_pagination_offset(self, db_session):
        """Should respect offset parameter."""
        # Create 3 playlists with predictable names
        pls = []
        for i in range(3):
            pl = Playlist(id=f"PL_{i}", name=f"PL{i}", is_system=False)
            db_session.add(pl)
            pls.append(pl)
        await db_session.commit()

        playlists = await get_playlists(
            db_session, limit=2, offset=1, order_by="name", order_direction="asc"
        )

        assert len(playlists) == 2
        # Should skip first playlist
        assert playlists[0].name != "PL0"

    async def test_order_by_name_asc(self, db_session):
        """Should order playlists by name ascending."""
        # Create playlists in reverse order
        for name in ["Zebra", "Alpha", "Middle"]:
            pl = Playlist(id=f"PL_{name}", name=name, is_system=False)
            db_session.add(pl)
        await db_session.commit()

        playlists = await get_playlists(
            db_session, order_by="name", order_direction="asc"
        )

        assert playlists[0].name == "Alpha"
        assert playlists[1].name == "Middle"
        assert playlists[2].name == "Zebra"

    async def test_order_by_name_desc(self, db_session):
        """Should order playlists by name descending."""
        for name in ["Alpha", "Middle", "Zebra"]:
            pl = Playlist(id=f"PL_{name}", name=name, is_system=False)
            db_session.add(pl)
        await db_session.commit()

        playlists = await get_playlists(
            db_session, order_by="name", order_direction="desc"
        )

        assert playlists[0].name == "Zebra"
        assert playlists[1].name == "Middle"
        assert playlists[2].name == "Alpha"

    async def test_first_returns_single_object(self, db_session, sample_playlist):
        """Should return single playlist object when first=True."""
        playlist = await get_playlists(db_session, first=True)

        assert isinstance(playlist, Playlist)
        assert playlist.id == sample_playlist.id

    async def test_first_returns_none_when_empty(self, db_session):
        """Should return None when no results and first=True."""
        playlist = await get_playlists(db_session, id="nonexistent", first=True)

        assert playlist is None

    async def test_empty_result_returns_empty_list(self, db_session):
        """Should return empty list when no results."""
        playlists = await get_playlists(db_session, name="nonexistent")

        assert playlists == []


@pytest.mark.asyncio
class TestCountPlaylists:
    """Tests for count_playlists() function."""

    async def test_count_all_playlists(self, db_session):
        """Should count all playlists when no filters."""
        # Create 3 playlists
        for i in range(3):
            pl = Playlist(id=f"PL_{i}", name=f"Playlist {i}", is_system=False)
            db_session.add(pl)
        await db_session.commit()

        count = await count_playlists(db_session)

        assert count == 3

    async def test_count_with_is_system_filter(self, db_session):
        """Should count only matching is_system playlists."""
        # Create 2 system, 3 non-system
        for i in range(2):
            pl = Playlist(id=f"PL_sys_{i}", name=f"System {i}", is_system=True)
            db_session.add(pl)
        for i in range(3):
            pl = Playlist(id=f"PL_user_{i}", name=f"User {i}", is_system=False)
            db_session.add(pl)
        await db_session.commit()

        count = await count_playlists(db_session, is_system=True)

        assert count == 2

    async def test_count_with_id_list_filter(self, db_session):
        """Should count playlists matching ID list."""
        # Create 5 playlists
        ids = []
        for i in range(5):
            pl = Playlist(id=f"PL_{i}", name=f"Playlist {i}", is_system=False)
            db_session.add(pl)
            ids.append(pl.id)
        await db_session.commit()

        # Count only 3 of them
        count = await count_playlists(db_session, id=ids[:3])

        assert count == 3

    async def test_count_zero_when_empty(self, db_session):
        """Should return 0 when no playlists match."""
        count = await count_playlists(db_session)

        assert count == 0


@pytest.mark.asyncio
class TestCreateDeletePlaylist:
    """Tests for create_playlist() and delete_playlist() functions."""

    async def test_create_playlist(self, db_session):
        """Should create playlist with all fields."""
        playlist = Playlist(
            id="PL_new",
            name="New Playlist",
            description="New description",
            is_system=False,
        )

        created = await create_playlist(db_session, playlist)

        assert created.id == "PL_new"
        assert created.name == "New Playlist"
        assert created.description == "New description"
        assert created.is_system is False
        assert created.created_at is not None

    async def test_create_playlist_persisted(self, db_session):
        """Should persist playlist to database."""
        playlist = Playlist(
            id="PL_persist",
            name="Persist Test",
            is_system=False,
        )

        await create_playlist(db_session, playlist)

        # Query it back
        result = await get_playlists(db_session, id="PL_persist", first=True)
        assert result is not None
        assert result.name == "Persist Test"

    async def test_delete_playlist(self, db_session, sample_playlist):
        """Should delete playlist from database."""
        await delete_playlist(db_session, sample_playlist)

        # Verify it's gone
        result = await get_playlists(db_session, id=sample_playlist.id, first=True)
        assert result is None

    async def test_delete_playlist_returns_deleted_object(
        self, db_session, sample_playlist
    ):
        """Should return the deleted playlist object."""
        deleted = await delete_playlist(db_session, sample_playlist)

        assert deleted.id == sample_playlist.id


@pytest.mark.asyncio
class TestGetPlaylistVideoIds:
    """Tests for get_playlist_video_ids() function."""

    async def test_returns_ordered_video_ids(
        self, db_session, sample_playlist_with_videos
    ):
        """Should return video IDs in position order."""
        video_ids = await get_playlist_video_ids(
            db_session, sample_playlist_with_videos.id
        )

        assert len(video_ids) == 3
        assert video_ids == ["VID_PL001", "VID_PL002", "VID_PL003"]

    async def test_returns_empty_list_for_empty_playlist(
        self, db_session, sample_playlist
    ):
        """Should return empty list when playlist has no videos."""
        video_ids = await get_playlist_video_ids(db_session, sample_playlist.id)

        assert video_ids == []

    async def test_correct_order_after_modifications(
        self, db_session, sample_playlist, sample_videos
    ):
        """Should maintain correct order after add/remove operations."""
        # Add videos in specific order
        await set_playlist_videos(
            db_session,
            sample_playlist.id,
            [sample_videos[2].id, sample_videos[0].id, sample_videos[4].id],
        )

        video_ids = await get_playlist_video_ids(db_session, sample_playlist.id)

        assert video_ids == ["VID003", "VID001", "VID005"]


@pytest.mark.asyncio
class TestGetMaxPosition:
    """Tests for get_max_position() function."""

    async def test_returns_max_position(self, db_session, sample_playlist_with_videos):
        """Should return the highest position value."""
        max_pos = await get_max_position(db_session, sample_playlist_with_videos.id)

        assert max_pos == 2  # 3 videos at positions 0, 1, 2

    async def test_returns_minus_one_for_empty_playlist(
        self, db_session, sample_playlist
    ):
        """Should return -1 when playlist is empty."""
        max_pos = await get_max_position(db_session, sample_playlist.id)

        assert max_pos == -1


@pytest.mark.asyncio
class TestSetPlaylistVideos:
    """Tests for set_playlist_videos() function."""

    async def test_set_videos_on_empty_playlist(
        self, db_session, sample_playlist, sample_videos
    ):
        """Should add videos to empty playlist in correct order."""
        video_ids = [sample_videos[0].id, sample_videos[1].id, sample_videos[2].id]

        await set_playlist_videos(db_session, sample_playlist.id, video_ids)

        result_ids = await get_playlist_video_ids(db_session, sample_playlist.id)
        assert result_ids == video_ids

    async def test_replace_existing_videos(
        self, db_session, sample_playlist_with_videos
    ):
        """Should replace all existing videos with new list."""
        new_ids = ["VID_PL003", "VID_PL001"]

        await set_playlist_videos(db_session, sample_playlist_with_videos.id, new_ids)

        result_ids = await get_playlist_video_ids(
            db_session, sample_playlist_with_videos.id
        )
        assert result_ids == new_ids

    async def test_set_empty_list_clears_playlist(
        self, db_session, sample_playlist_with_videos
    ):
        """Should clear all videos when given empty list."""
        await set_playlist_videos(db_session, sample_playlist_with_videos.id, [])

        result_ids = await get_playlist_video_ids(
            db_session, sample_playlist_with_videos.id
        )
        assert result_ids == []

    async def test_verify_position_ordering(
        self, db_session, sample_playlist, sample_videos
    ):
        """Should assign positions 0, 1, 2, ... in order."""
        video_ids = [v.id for v in sample_videos[:4]]

        await set_playlist_videos(db_session, sample_playlist.id, video_ids)

        result_ids = await get_playlist_video_ids(db_session, sample_playlist.id)
        assert result_ids == video_ids


@pytest.mark.asyncio
class TestAddVideoToPlaylist:
    """Tests for add_video_to_playlist() function."""

    async def test_append_to_end_when_no_position(
        self, db_session, sample_playlist_with_videos
    ):
        """Should append video to end when position is None."""
        await add_video_to_playlist(
            db_session, sample_playlist_with_videos.id, "VID001"
        )

        video_ids = await get_playlist_video_ids(
            db_session, sample_playlist_with_videos.id
        )
        assert video_ids[-1] == "VID001"
        assert len(video_ids) == 4

    async def test_insert_at_specific_position(
        self, db_session, sample_playlist_with_videos
    ):
        """Should insert video at specified position and shift others."""
        await add_video_to_playlist(
            db_session, sample_playlist_with_videos.id, "VID001", position=1
        )

        video_ids = await get_playlist_video_ids(
            db_session, sample_playlist_with_videos.id
        )
        assert video_ids[1] == "VID001"
        assert len(video_ids) == 4

    async def test_adding_duplicate_moves_it(
        self, db_session, sample_playlist_with_videos
    ):
        """Should move video if it already exists in playlist."""
        # VID_PL001 is at position 0
        await add_video_to_playlist(
            db_session, sample_playlist_with_videos.id, "VID_PL001", position=2
        )

        video_ids = await get_playlist_video_ids(
            db_session, sample_playlist_with_videos.id
        )
        # Should still have 3 videos
        assert len(video_ids) == 3
        assert video_ids[2] == "VID_PL001"

    async def test_append_duplicate_to_end(
        self, db_session, sample_playlist_with_videos
    ):
        """Should move duplicate to end when position is None."""
        await add_video_to_playlist(
            db_session, sample_playlist_with_videos.id, "VID_PL002"
        )

        video_ids = await get_playlist_video_ids(
            db_session, sample_playlist_with_videos.id
        )
        assert len(video_ids) == 3
        assert video_ids[-1] == "VID_PL002"

    async def test_add_to_empty_playlist(
        self, db_session, sample_playlist, sample_videos
    ):
        """Should add first video to empty playlist at position 0."""
        await add_video_to_playlist(db_session, sample_playlist.id, sample_videos[0].id)

        video_ids = await get_playlist_video_ids(db_session, sample_playlist.id)
        assert video_ids == [sample_videos[0].id]


@pytest.mark.asyncio
class TestRemoveVideoFromPlaylist:
    """Tests for remove_video_from_playlist() function."""

    async def test_remove_middle_video_compacts_positions(
        self, db_session, sample_playlist_with_videos
    ):
        """Should remove video and compact positions."""
        rows = await remove_video_from_playlist(
            db_session, sample_playlist_with_videos.id, "VID_PL002"
        )

        assert rows == 1
        video_ids = await get_playlist_video_ids(
            db_session, sample_playlist_with_videos.id
        )
        assert video_ids == ["VID_PL001", "VID_PL003"]

    async def test_remove_nonexistent_returns_zero(
        self, db_session, sample_playlist_with_videos
    ):
        """Should return 0 when video not in playlist."""
        rows = await remove_video_from_playlist(
            db_session, sample_playlist_with_videos.id, "VID999"
        )

        assert rows == 0

    async def test_remove_last_video(self, db_session, sample_playlist_with_videos):
        """Should remove last video without errors."""
        await remove_video_from_playlist(
            db_session, sample_playlist_with_videos.id, "VID_PL003"
        )

        video_ids = await get_playlist_video_ids(
            db_session, sample_playlist_with_videos.id
        )
        assert video_ids == ["VID_PL001", "VID_PL002"]


@pytest.mark.asyncio
class TestMoveVideoInPlaylist:
    """Tests for move_video_in_playlist() function."""

    async def test_move_video_forward(self, db_session, sample_playlist_with_videos):
        """Should move video from earlier position to later position."""
        # Move VID_PL001 from position 0 to position 2
        await move_video_in_playlist(
            db_session, sample_playlist_with_videos.id, "VID_PL001", 2
        )

        video_ids = await get_playlist_video_ids(
            db_session, sample_playlist_with_videos.id
        )
        assert video_ids == ["VID_PL002", "VID_PL003", "VID_PL001"]

    async def test_move_video_backward(self, db_session, sample_playlist_with_videos):
        """Should move video from later position to earlier position."""
        # Move VID_PL003 from position 2 to position 0
        await move_video_in_playlist(
            db_session, sample_playlist_with_videos.id, "VID_PL003", 0
        )

        video_ids = await get_playlist_video_ids(
            db_session, sample_playlist_with_videos.id
        )
        assert video_ids == ["VID_PL003", "VID_PL001", "VID_PL002"]

    async def test_move_to_same_position_is_noop(
        self, db_session, sample_playlist_with_videos
    ):
        """Should do nothing when moving to same position."""
        original_ids = await get_playlist_video_ids(
            db_session, sample_playlist_with_videos.id
        )

        await move_video_in_playlist(
            db_session, sample_playlist_with_videos.id, "VID_PL002", 1
        )

        video_ids = await get_playlist_video_ids(
            db_session, sample_playlist_with_videos.id
        )
        assert video_ids == original_ids

    async def test_move_nonexistent_raises_error(
        self, db_session, sample_playlist_with_videos
    ):
        """Should raise ValueError when video not in playlist."""
        with pytest.raises(ValueError, match="not found in playlist"):
            await move_video_in_playlist(
                db_session, sample_playlist_with_videos.id, "VID999", 0
            )


@pytest.mark.asyncio
class TestBulkAddVideos:
    """Tests for bulk_add_videos_to_playlist() function."""

    async def test_bulk_append(self, db_session, sample_playlist, sample_videos):
        """Should append multiple videos to empty playlist."""
        video_ids = [v.id for v in sample_videos[:3]]

        await bulk_add_videos_to_playlist(db_session, sample_playlist.id, video_ids)

        result_ids = await get_playlist_video_ids(db_session, sample_playlist.id)
        assert result_ids == video_ids

    async def test_bulk_insert_at_position(
        self, db_session, sample_playlist_with_videos, sample_videos
    ):
        """Should insert multiple videos at specified position."""
        new_ids = ["VID001", "VID002"]

        await bulk_add_videos_to_playlist(
            db_session, sample_playlist_with_videos.id, new_ids, start_position=1
        )

        result_ids = await get_playlist_video_ids(
            db_session, sample_playlist_with_videos.id
        )
        assert result_ids[1:3] == new_ids
        assert len(result_ids) == 5

    async def test_bulk_with_duplicates_removes_and_reinserts(
        self, db_session, sample_playlist_with_videos
    ):
        """Should remove duplicates first then re-insert at new positions."""
        # VID_PL001 and VID_PL002 already in playlist
        new_ids = ["VID_PL001", "VID_PL002", "VID001"]

        await bulk_add_videos_to_playlist(
            db_session, sample_playlist_with_videos.id, new_ids
        )

        result_ids = await get_playlist_video_ids(
            db_session, sample_playlist_with_videos.id
        )
        # Should have VID_PL003 first (not in new_ids), then the new_ids
        assert result_ids == ["VID_PL003", "VID_PL001", "VID_PL002", "VID001"]

    async def test_bulk_with_duplicate_ids_in_input(
        self, db_session, sample_playlist, sample_videos
    ):
        """Should deduplicate input IDs, keeping last occurrence."""
        # Same ID appears twice
        video_ids = ["VID001", "VID002", "VID001", "VID003"]

        await bulk_add_videos_to_playlist(db_session, sample_playlist.id, video_ids)

        result_ids = await get_playlist_video_ids(db_session, sample_playlist.id)
        # Should only have 3 videos, VID001 deduplicated
        assert len(result_ids) == 3
        assert result_ids == ["VID001", "VID002", "VID003"]


@pytest.mark.asyncio
class TestClearPlaylistVideos:
    """Tests for clear_playlist_videos() function."""

    async def test_clear_populated_playlist(
        self, db_session, sample_playlist_with_videos
    ):
        """Should remove all videos from playlist."""
        await clear_playlist_videos(db_session, sample_playlist_with_videos.id)

        video_ids = await get_playlist_video_ids(
            db_session, sample_playlist_with_videos.id
        )
        assert video_ids == []

    async def test_clear_empty_playlist_no_error(self, db_session, sample_playlist):
        """Should not error when clearing already empty playlist."""
        await clear_playlist_videos(db_session, sample_playlist.id)

        video_ids = await get_playlist_video_ids(db_session, sample_playlist.id)
        assert video_ids == []
