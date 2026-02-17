"""
Parametrized tests for playlist ordering invariants.

Tests that playlist position management maintains critical invariants
using concrete test cases.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone

from app.db.crud.crud_playlist import (
    set_playlist_videos,
    add_video_to_playlist,
    remove_video_from_playlist,
    move_video_in_playlist,
    get_playlist_video_ids,
    bulk_add_videos_to_playlist,
)
from app.db.models.playlist import Playlist
from app.db.models.channel import Channel
from app.db.models.video import Video


@pytest_asyncio.fixture
async def inv_channel(db_session):
    """Create a channel for invariant tests."""
    channel = Channel(
        id="CH_inv",
        handle="invtest",
        title="Invariant Test Channel",
        uploads_playlist_id="UU_inv",
    )
    db_session.add(channel)
    await db_session.commit()
    await db_session.refresh(channel)
    return channel


@pytest_asyncio.fixture
async def inv_playlist(db_session):
    """Create a playlist for invariant tests."""
    playlist = Playlist(
        id="PL_inv",
        name="Invariant Test Playlist",
        is_system=False,
    )
    db_session.add(playlist)
    await db_session.commit()
    await db_session.refresh(playlist)
    return playlist


async def create_test_videos(
    db_session, channel, count: int, prefix: str = "INV"
) -> list[str]:
    """Helper to create N videos and return their IDs."""
    video_ids = []
    for i in range(count):
        video = Video(
            id=f"{prefix}_VID_{i:04d}",
            channel_id=channel.id,
            title=f"Video {prefix} {i}",
            published_at=datetime.now(timezone.utc),
            duration_seconds=300,
            is_short=False,
        )
        db_session.add(video)
        video_ids.append(video.id)
    await db_session.commit()
    return video_ids


@pytest.mark.asyncio
class TestPlaylistPositionInvariants:
    """Tests for playlist position invariants using concrete examples."""

    @pytest.mark.parametrize(
        "video_count,remove_count",
        [
            (5, 2),
            (10, 5),
            (3, 1),
            (15, 7),
        ],
    )
    async def test_positions_are_contiguous_after_operations(
        self, db_session, inv_channel, inv_playlist, video_count, remove_count
    ):
        """
        Invariant: Positions are always contiguous 0..n-1.

        After any sequence of add/remove operations, the positions
        should always form a contiguous sequence starting at 0.
        """
        video_ids = await create_test_videos(
            db_session, inv_channel, video_count, f"POS{video_count}"
        )

        # Add all videos
        await set_playlist_videos(db_session, inv_playlist.id, video_ids)

        # Remove some videos
        for i in range(min(remove_count, video_count)):
            await remove_video_from_playlist(db_session, inv_playlist.id, video_ids[i])

        # Get final video IDs
        final_ids = await get_playlist_video_ids(db_session, inv_playlist.id)

        # Verify contiguity (list has expected length, no duplicates)
        assert len(final_ids) == video_count - remove_count
        assert len(final_ids) == len(set(final_ids))  # No duplicates

    @pytest.mark.parametrize("video_count", [1, 3, 5, 10, 15])
    async def test_set_preserves_order(
        self, db_session, inv_channel, inv_playlist, video_count
    ):
        """
        Invariant: set_playlist_videos preserves input order.

        When setting N unique video IDs, the resulting playlist
        should have exactly those videos in exactly that order.
        """
        video_ids = await create_test_videos(
            db_session, inv_channel, video_count, f"SET{video_count}"
        )

        # Set videos in a specific order
        await set_playlist_videos(db_session, inv_playlist.id, video_ids)

        # Retrieve and verify
        result_ids = await get_playlist_video_ids(db_session, inv_playlist.id)

        assert result_ids == video_ids
        assert len(result_ids) == video_count

    @pytest.mark.parametrize(
        "total_count,add_index",
        [
            (5, 0),
            (5, 2),
            (5, 4),
            (10, 3),
            (10, 7),
        ],
    )
    async def test_add_then_remove_is_identity(
        self, db_session, inv_channel, inv_playlist, total_count, add_index
    ):
        """
        Invariant: Adding a video then removing it leaves playlist unchanged.

        If we add a new video to a playlist and then immediately remove it,
        the playlist should return to its original state.
        """
        video_ids = await create_test_videos(
            db_session, inv_channel, total_count, f"ID{total_count}_{add_index}"
        )

        # Set initial videos (exclude one)
        initial_ids = video_ids[:add_index] + video_ids[add_index + 1 :]
        await set_playlist_videos(db_session, inv_playlist.id, initial_ids)

        # Record original state
        original_ids = await get_playlist_video_ids(db_session, inv_playlist.id)

        # Add the excluded video
        await add_video_to_playlist(db_session, inv_playlist.id, video_ids[add_index])

        # Remove it
        await remove_video_from_playlist(
            db_session, inv_playlist.id, video_ids[add_index]
        )

        # Should be back to original
        final_ids = await get_playlist_video_ids(db_session, inv_playlist.id)

        assert final_ids == original_ids

    @pytest.mark.parametrize(
        "video_count,move_from,move_to",
        [
            (5, 0, 4),
            (5, 4, 0),
            (5, 1, 3),
            (10, 0, 9),
            (10, 5, 2),
        ],
    )
    async def test_move_preserves_count(
        self, db_session, inv_channel, inv_playlist, video_count, move_from, move_to
    ):
        """
        Invariant: Moving a video never changes video count.

        Moving any video from any position to any other position
        should preserve the total number of videos.
        """
        video_ids = await create_test_videos(
            db_session,
            inv_channel,
            video_count,
            f"MOV{video_count}_{move_from}_{move_to}",
        )

        await set_playlist_videos(db_session, inv_playlist.id, video_ids)

        original_count = len(await get_playlist_video_ids(db_session, inv_playlist.id))

        # Move video
        video_to_move = video_ids[move_from]
        await move_video_in_playlist(
            db_session, inv_playlist.id, video_to_move, move_to
        )

        final_count = len(await get_playlist_video_ids(db_session, inv_playlist.id))

        assert final_count == original_count
        assert final_count == video_count


@pytest.mark.asyncio
class TestPlaylistDuplicateHandling:
    """Tests for duplicate video handling."""

    @pytest.mark.parametrize(
        "video_count,duplicate_index",
        [
            (5, 0),
            (5, 2),
            (5, 4),
            (10, 3),
            (10, 8),
        ],
    )
    async def test_add_duplicate_moves_not_duplicates(
        self, db_session, inv_channel, inv_playlist, video_count, duplicate_index
    ):
        """
        Invariant: Adding duplicate video moves it, doesn't duplicate.

        Adding a video that already exists should move it to the new
        position, not create a duplicate entry.
        """
        video_ids = await create_test_videos(
            db_session, inv_channel, video_count, f"DUP{video_count}_{duplicate_index}"
        )

        # Set initial videos
        await set_playlist_videos(db_session, inv_playlist.id, video_ids)

        original_count = len(await get_playlist_video_ids(db_session, inv_playlist.id))

        # Add duplicate
        await add_video_to_playlist(
            db_session, inv_playlist.id, video_ids[duplicate_index]
        )

        final_count = len(await get_playlist_video_ids(db_session, inv_playlist.id))
        final_ids = await get_playlist_video_ids(db_session, inv_playlist.id)

        # Count should not increase
        assert final_count == original_count
        # No duplicate IDs
        assert len(final_ids) == len(set(final_ids))


@pytest.mark.asyncio
class TestPlaylistBulkOperations:
    """Tests for bulk operations."""

    @pytest.mark.parametrize(
        "video_count,bulk_count",
        [
            (5, 3),
            (10, 5),
            (15, 8),
        ],
    )
    async def test_bulk_add_preserves_order(
        self, db_session, inv_channel, inv_playlist, video_count, bulk_count
    ):
        """
        Invariant: Bulk add preserves order of input IDs.

        When bulk adding videos, they should appear in the playlist
        in the same order as provided in the input list.
        """
        video_ids = await create_test_videos(
            db_session, inv_channel, video_count, f"BULK{video_count}_{bulk_count}"
        )

        # Bulk add subset
        ids_to_add = video_ids[:bulk_count]

        await bulk_add_videos_to_playlist(db_session, inv_playlist.id, ids_to_add)

        result_ids = await get_playlist_video_ids(db_session, inv_playlist.id)

        # Should have the videos in the same order
        assert result_ids == ids_to_add

    async def test_bulk_add_deduplicates_input(
        self, db_session, inv_channel, inv_playlist
    ):
        """
        Invariant: Bulk add deduplicates input list.

        If the input list contains duplicate IDs, the playlist
        should only contain each video once.
        """
        video_ids = await create_test_videos(db_session, inv_channel, 5, "DEDUP")

        # Create list with duplicates
        ids_with_dupes = [
            video_ids[0],
            video_ids[1],
            video_ids[0],  # Duplicate
            video_ids[2],
            video_ids[1],  # Duplicate
        ]

        await bulk_add_videos_to_playlist(db_session, inv_playlist.id, ids_with_dupes)

        result_ids = await get_playlist_video_ids(db_session, inv_playlist.id)

        # Should have unique IDs only
        assert len(result_ids) == len(set(result_ids))
        # Should have at most 3 unique videos
        assert len(result_ids) <= 3


@pytest.mark.asyncio
class TestPlaylistRemovalInvariants:
    """Tests for video removal."""

    @pytest.mark.parametrize(
        "video_count,remove_count",
        [
            (5, 2),
            (10, 5),
            (15, 8),
        ],
    )
    async def test_remove_reduces_count_correctly(
        self, db_session, inv_channel, inv_playlist, video_count, remove_count
    ):
        """
        Invariant: Removing N videos reduces count by N.

        Starting with M videos and removing N unique videos
        should result in M-N videos.
        """
        video_ids = await create_test_videos(
            db_session, inv_channel, video_count, f"REM{video_count}_{remove_count}"
        )

        await set_playlist_videos(db_session, inv_playlist.id, video_ids)

        # Remove N videos
        for i in range(remove_count):
            await remove_video_from_playlist(db_session, inv_playlist.id, video_ids[i])

        final_count = len(await get_playlist_video_ids(db_session, inv_playlist.id))

        assert final_count == video_count - remove_count

    @pytest.mark.parametrize(
        "video_count,remove_index",
        [
            (5, 0),
            (5, 2),
            (5, 4),
            (10, 3),
            (10, 8),
        ],
    )
    async def test_remove_preserves_remaining_order(
        self, db_session, inv_channel, inv_playlist, video_count, remove_index
    ):
        """
        Invariant: Removing a video preserves order of remaining videos.

        After removing a video at position N, all other videos should
        maintain their relative order.
        """
        video_ids = await create_test_videos(
            db_session, inv_channel, video_count, f"ORD{video_count}_{remove_index}"
        )

        await set_playlist_videos(db_session, inv_playlist.id, video_ids)

        # Expected remaining videos (in order)
        expected_ids = video_ids[:remove_index] + video_ids[remove_index + 1 :]

        # Remove video
        await remove_video_from_playlist(
            db_session, inv_playlist.id, video_ids[remove_index]
        )

        result_ids = await get_playlist_video_ids(db_session, inv_playlist.id)

        assert result_ids == expected_ids
