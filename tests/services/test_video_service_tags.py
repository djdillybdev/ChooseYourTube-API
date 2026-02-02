"""
Tests for video tag management through the service layer.

Tests the update_video service method's tag synchronization functionality.
"""

import pytest
import pytest_asyncio
from fastapi import HTTPException
from datetime import datetime, timezone
from app.services.video_service import update_video
from app.db.crud.crud_video import get_videos, create_videos_bulk
from app.db.crud.crud_channel import create_channel
from app.db.crud.crud_tag import create_tag, get_tags
from app.db.models.channel import Channel
from app.db.models.tag import Tag
from app.schemas.video import VideoCreate, VideoUpdate


@pytest_asyncio.fixture
async def sample_channel(db_session):
    """Create a sample channel for testing."""
    channel = Channel(
        id="UC001",
        title="Python Tutorials",
        handle="@pythontutorials",
        uploads_playlist_id="UU001",
    )
    return await create_channel(db_session, channel)


@pytest_asyncio.fixture
async def sample_tags(db_session):
    """Create sample tags for testing."""
    import uuid
    tag_names = ["python", "javascript", "tutorial", "advanced", "beginner"]
    tags = []
    for name in tag_names:
        tag = Tag(id=str(uuid.uuid4()), name=name)
        created_tag = await create_tag(db_session, tag)
        tags.append(created_tag)
    return tags


@pytest_asyncio.fixture
async def sample_video(db_session, sample_channel):
    """Create a sample video for testing."""
    video = VideoCreate(
        id="dQw4w9WgXcQ",
        channel_id=sample_channel.id,
        title="Test Video",
        description="A test video",
        published_at=datetime.now(timezone.utc),
        duration_seconds=180,
        is_short=False,
    )
    await create_videos_bulk(db_session, [video])
    return await get_videos(db_session, id=video.id, first=True)


@pytest.mark.asyncio
class TestUpdateVideoWithTags:
    """Tests for updating video tags through the service layer."""

    async def test_add_tags_to_video(self, db_session, sample_video, sample_tags):
        """Add tags to a video using update_video."""
        tag_ids = [sample_tags[0].id, sample_tags[1].id]

        payload = VideoUpdate(tag_ids=tag_ids)
        await update_video(sample_video.id, payload, db_session)

        # Verify tags were added
        refreshed = await get_videos(db_session, id=sample_video.id, first=True)
        assert len(refreshed.tags) == 2

        result_tag_ids = {t.id for t in refreshed.tags}
        assert result_tag_ids == set(tag_ids)

    async def test_replace_video_tags(self, db_session, sample_video, sample_tags):
        """Replace existing tags with new ones."""
        # First, add some tags
        initial_tag_ids = [sample_tags[0].id, sample_tags[1].id]
        payload = VideoUpdate(tag_ids=initial_tag_ids)
        await update_video(sample_video.id, payload, db_session)

        # Verify initial tags
        refreshed = await get_videos(db_session, id=sample_video.id, first=True)
        assert len(refreshed.tags) == 2

        # Now replace with different tags
        new_tag_ids = [sample_tags[2].id, sample_tags[3].id, sample_tags[4].id]
        payload = VideoUpdate(tag_ids=new_tag_ids)
        await update_video(sample_video.id, payload, db_session)

        # Verify tags were replaced
        refreshed = await get_videos(db_session, id=sample_video.id, first=True)
        assert len(refreshed.tags) == 3

        result_tag_ids = {t.id for t in refreshed.tags}
        assert result_tag_ids == set(new_tag_ids)

    async def test_remove_all_tags_with_empty_list(
        self, db_session, sample_video, sample_tags
    ):
        """Remove all tags by providing an empty list."""
        # First, add some tags
        tag_ids = [sample_tags[0].id, sample_tags[1].id]
        payload = VideoUpdate(tag_ids=tag_ids)
        await update_video(sample_video.id, payload, db_session)

        # Verify tags were added
        refreshed = await get_videos(db_session, id=sample_video.id, first=True)
        assert len(refreshed.tags) == 2

        # Remove all tags with empty list
        payload = VideoUpdate(tag_ids=[])
        await update_video(sample_video.id, payload, db_session)

        # Verify all tags removed
        refreshed = await get_videos(db_session, id=sample_video.id, first=True)
        assert len(refreshed.tags) == 0

    async def test_update_without_tag_ids_preserves_tags(
        self, db_session, sample_video, sample_tags
    ):
        """Updating other fields without tag_ids should preserve existing tags."""
        # Add some tags
        tag_ids = [sample_tags[0].id, sample_tags[1].id]
        payload = VideoUpdate(tag_ids=tag_ids)
        await update_video(sample_video.id, payload, db_session)

        # Update is_favorited without touching tag_ids
        payload = VideoUpdate(is_favorited=True)
        await update_video(sample_video.id, payload, db_session)

        # Verify tags are still there
        refreshed = await get_videos(db_session, id=sample_video.id, first=True)
        assert len(refreshed.tags) == 2
        assert refreshed.is_favorited is True

    async def test_add_duplicate_tag_ids_in_list(
        self, db_session, sample_video, sample_tags
    ):
        """Providing duplicate tag IDs in the list should deduplicate."""
        # Provide duplicate IDs
        tag_ids = [sample_tags[0].id, sample_tags[0].id, sample_tags[1].id]

        payload = VideoUpdate(tag_ids=tag_ids)
        await update_video(sample_video.id, payload, db_session)

        # Verify only unique tags were added
        refreshed = await get_videos(db_session, id=sample_video.id, first=True)
        assert len(refreshed.tags) == 2

    async def test_update_video_with_nonexistent_tag_raises_error(
        self, db_session, sample_video
    ):
        """Providing a non-existent tag ID should raise HTTPException."""
        payload = VideoUpdate(tag_ids=["nonexistent-tag"])

        with pytest.raises(HTTPException) as exc_info:
            await update_video(sample_video.id, payload, db_session)

        assert exc_info.value.status_code == 400
        assert "does not exist" in exc_info.value.detail

    async def test_partial_invalid_tag_ids_raises_error(
        self, db_session, sample_video, sample_tags
    ):
        """Providing a mix of valid and invalid tag IDs should raise error."""
        # Mix valid and invalid IDs
        tag_ids = [sample_tags[0].id, "nonexistent-uuid", sample_tags[1].id]

        payload = VideoUpdate(tag_ids=tag_ids)

        with pytest.raises(HTTPException) as exc_info:
            await update_video(sample_video.id, payload, db_session)

        assert exc_info.value.status_code == 400

    async def test_update_nonexistent_video_with_tags_raises_error(
        self, db_session, sample_tags
    ):
        """Updating a non-existent video should raise 404."""
        payload = VideoUpdate(tag_ids=[sample_tags[0].id])

        with pytest.raises(HTTPException) as exc_info:
            await update_video("VIDEO_NONEXISTENT", payload, db_session)

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()


@pytest.mark.asyncio
class TestVideoTagRelationships:
    """Tests for tag relationship access and behavior."""

    async def test_access_tags_through_video_relationship(
        self, db_session, sample_video, sample_tags
    ):
        """Access tags through video.tags relationship."""
        tag_ids = [sample_tags[0].id, sample_tags[1].id]
        payload = VideoUpdate(tag_ids=tag_ids)
        await update_video(sample_video.id, payload, db_session)

        # Access through relationship
        refreshed = await get_videos(db_session, id=sample_video.id, first=True)
        assert len(refreshed.tags) == 2

        tag_names = {t.name for t in refreshed.tags}
        expected_names = {sample_tags[0].name, sample_tags[1].name}
        assert tag_names == expected_names

    async def test_access_videos_through_tag_relationship(
        self, db_session, sample_channel, sample_tags
    ):
        """Access videos through tag.videos relationship."""
        # Create multiple videos and add same tag to all
        videos = []
        for i in range(3):
            video = VideoCreate(
                id=f"VIDEO{i:03d}",
                channel_id=sample_channel.id,
                title=f"Video {i}",
                description=f"Description {i}",
                published_at=datetime.now(timezone.utc),
                duration_seconds=180,
                is_short=False,
            )
            videos.append(video)

        await create_videos_bulk(db_session, videos)

        # Add the same tag to each video
        for video in videos:
            created = await get_videos(db_session, id=video.id, first=True)
            payload = VideoUpdate(tag_ids=[sample_tags[0].id])
            await update_video(created.id, payload, db_session)

        # Access videos through tag relationship
        refreshed_tag = await get_tags(db_session, id=sample_tags[0].id, first=True)
        assert len(refreshed_tag.videos) == 3

        video_ids = {v.id for v in refreshed_tag.videos}
        expected_ids = {v.id for v in videos}
        assert video_ids == expected_ids

    async def test_video_with_no_tags(self, db_session, sample_video):
        """Video with no tags should have empty tags list."""
        refreshed = await get_videos(db_session, id=sample_video.id, first=True)
        assert len(refreshed.tags) == 0
        assert refreshed.tags == []

    async def test_tags_separate_from_yt_tags(
        self, db_session, sample_channel, sample_tags
    ):
        """Verify that user tags are separate from yt_tags (YouTube metadata)."""
        # Create video with yt_tags
        video = VideoCreate(
            id="VIDEO_YT_TAGS",
            channel_id=sample_channel.id,
            title="Video with YT tags",
            description="Test",
            published_at=datetime.now(timezone.utc),
            duration_seconds=180,
            is_short=False,
            yt_tags=["python", "tutorial", "coding"],  # YouTube metadata tags
        )
        await create_videos_bulk(db_session, [video])

        # Add user tags
        payload = VideoUpdate(tag_ids=[sample_tags[0].id])
        await update_video(video.id, payload, db_session)

        # Verify both exist separately
        refreshed = await get_videos(db_session, id=video.id, first=True)
        assert len(refreshed.tags) == 1  # User tags
        assert len(refreshed.yt_tags) == 3  # YouTube tags
        assert refreshed.yt_tags == ["python", "tutorial", "coding"]


@pytest.mark.asyncio
class TestVideoTagEdgeCases:
    """Tests for edge cases in video tag management."""

    async def test_video_with_many_tags(self, db_session, sample_video, sample_tags):
        """A video can have many tags."""
        # Add all tags to the video
        tag_ids = [t.id for t in sample_tags]
        payload = VideoUpdate(tag_ids=tag_ids)
        await update_video(sample_video.id, payload, db_session)

        refreshed = await get_videos(db_session, id=sample_video.id, first=True)
        assert len(refreshed.tags) == len(sample_tags)

    async def test_tag_used_by_many_videos(
        self, db_session, sample_channel, sample_tags
    ):
        """A tag can be used by many videos."""
        # Create multiple videos
        videos = []
        for i in range(5):
            video = VideoCreate(
                id=f"VIDEO{i:03d}",
                channel_id=sample_channel.id,
                title=f"Video {i}",
                description=f"Description {i}",
                published_at=datetime.now(timezone.utc),
                duration_seconds=180,
                is_short=False,
            )
            videos.append(video)

        await create_videos_bulk(db_session, videos)

        # Add same tag to each
        for video in videos:
            created = await get_videos(db_session, id=video.id, first=True)
            payload = VideoUpdate(tag_ids=[sample_tags[0].id])
            await update_video(created.id, payload, db_session)

        # Verify tag has all videos
        refreshed_tag = await get_tags(db_session, id=sample_tags[0].id, first=True)
        assert len(refreshed_tag.videos) == 5

    async def test_add_remove_add_tags_multiple_times(
        self, db_session, sample_video, sample_tags
    ):
        """Add and remove tags multiple times (idempotent operations)."""
        tag_ids = [sample_tags[0].id]

        # Add tags
        payload = VideoUpdate(tag_ids=tag_ids)
        await update_video(sample_video.id, payload, db_session)
        refreshed = await get_videos(db_session, id=sample_video.id, first=True)
        assert len(refreshed.tags) == 1

        # Remove tags
        payload = VideoUpdate(tag_ids=[])
        await update_video(sample_video.id, payload, db_session)
        refreshed = await get_videos(db_session, id=sample_video.id, first=True)
        assert len(refreshed.tags) == 0

        # Add again
        payload = VideoUpdate(tag_ids=tag_ids)
        await update_video(sample_video.id, payload, db_session)
        refreshed = await get_videos(db_session, id=sample_video.id, first=True)
        assert len(refreshed.tags) == 1

        # Remove again
        payload = VideoUpdate(tag_ids=[])
        await update_video(sample_video.id, payload, db_session)
        refreshed = await get_videos(db_session, id=sample_video.id, first=True)
        assert len(refreshed.tags) == 0

    async def test_combined_updates(self, db_session, sample_video, sample_tags):
        """Update tags along with other video fields."""
        tag_ids = [sample_tags[0].id, sample_tags[1].id]

        payload = VideoUpdate(
            tag_ids=tag_ids, is_favorited=True, is_watched=True, is_short=True
        )
        await update_video(sample_video.id, payload, db_session)

        # Verify all fields updated
        refreshed = await get_videos(db_session, id=sample_video.id, first=True)
        assert len(refreshed.tags) == 2
        assert refreshed.is_favorited is True
        assert refreshed.is_watched is True
        assert refreshed.is_short is True
