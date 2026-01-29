"""
Comprehensive tests for video write operations (bulk create).

Tests create_videos_bulk() method with ON CONFLICT DO NOTHING handling.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from app.db.crud.crud_video import create_videos_bulk, get_videos
from app.db.crud.crud_channel import create_channel
from app.db.models.channel import Channel
from app.schemas.video import VideoCreate


@pytest_asyncio.fixture
async def sample_channel(db_session):
    """Creates a test channel for testing video foreign key relationships."""
    channel = Channel(
        id="UC_test_channel",
        title="Test Channel",
        handle="@testchannel",
        uploads_playlist_id="UU_test_playlist",
    )
    await create_channel(db_session, channel)
    return channel


@pytest.mark.asyncio
class TestCreateVideosBulk:
    """Tests for create_videos_bulk() function."""

    async def test_create_videos_bulk_single_video(self, db_session, sample_channel):
        """Bulk create with a single video."""
        now = datetime.now(timezone.utc)
        videos = [
            VideoCreate(
                id="video_001",
                channel_id=sample_channel.id,
                title="Test Video 1",
                description="Description 1",
                thumbnail_url="https://example.com/thumb1.jpg",
                published_at=now,
                duration_seconds=300,
                yt_tags=["tag1", "tag2"],
                is_short=False,
            )
        ]

        await create_videos_bulk(db_session, videos)

        # Verify video was created
        result = await get_videos(db_session, id="video_001", first=True)
        assert result is not None
        assert result.title == "Test Video 1"
        assert result.channel_id == sample_channel.id
        assert result.duration_seconds == 300

    async def test_create_videos_bulk_multiple_videos(self, db_session, sample_channel):
        """Bulk create multiple videos at once."""
        now = datetime.now(timezone.utc)
        videos = [
            VideoCreate(
                id=f"video_{str(i).zfill(3)}",
                channel_id=sample_channel.id,
                title=f"Test Video {i}",
                description=f"Description {i}",
                thumbnail_url=f"https://example.com/thumb{i}.jpg",
                published_at=now - timedelta(days=i),
                duration_seconds=300 + i * 10,
                yt_tags=[f"tag{i}"],
                is_short=False,
            )
            for i in range(10)
        ]

        await create_videos_bulk(db_session, videos)

        # Verify all videos were created
        all_videos = await get_videos(db_session, channel_id=sample_channel.id)
        assert len(all_videos) == 10

    async def test_create_videos_bulk_with_duplicates_ignores_duplicates(
        self, db_session, sample_channel
    ):
        """ON CONFLICT DO NOTHING should ignore duplicate video IDs."""
        now = datetime.now(timezone.utc)

        # First batch
        videos_batch1 = [
            VideoCreate(
                id="video_duplicate",
                channel_id=sample_channel.id,
                title="Original Title",
                description="Original Description",
                thumbnail_url="https://example.com/original.jpg",
                published_at=now,
                duration_seconds=100,
                yt_tags=["original"],
                is_short=False,
            )
        ]
        await create_videos_bulk(db_session, videos_batch1)

        # Second batch with same ID but different data
        videos_batch2 = [
            VideoCreate(
                id="video_duplicate",  # Same ID
                channel_id=sample_channel.id,
                title="New Title",  # Different title
                description="New Description",  # Different description
                thumbnail_url="https://example.com/new.jpg",
                published_at=now,
                duration_seconds=200,  # Different duration
                yt_tags=["new"],
                is_short=True,
            )
        ]
        await create_videos_bulk(db_session, videos_batch2)

        # Verify original video is unchanged
        result = await get_videos(db_session, id="video_duplicate", first=True)
        assert result.title == "Original Title"  # Original title preserved
        assert result.duration_seconds == 100  # Original duration preserved

    async def test_create_videos_bulk_empty_list(self, db_session):
        """Bulk create with empty list should do nothing."""
        await create_videos_bulk(db_session, [])

        # Verify no videos exist
        all_videos = await get_videos(db_session)
        assert len(all_videos) == 0

    async def test_create_videos_bulk_with_minimal_fields(self, db_session, sample_channel):
        """Create videos with only required fields."""
        now = datetime.now(timezone.utc)
        videos = [
            VideoCreate(
                id="video_minimal",
                channel_id=sample_channel.id,
                title="Minimal Video",
                description=None,  # Optional
                thumbnail_url=None,  # Optional
                published_at=now,
                duration_seconds=None,  # Optional
                yt_tags=[],  # Default empty list
                is_short=False,
            )
        ]

        await create_videos_bulk(db_session, videos)

        result = await get_videos(db_session, id="video_minimal", first=True)
        assert result is not None
        assert result.title == "Minimal Video"
        assert result.description is None
        assert result.thumbnail_url is None
        assert result.duration_seconds is None
        assert result.yt_tags == []

    async def test_create_videos_bulk_with_all_fields(self, db_session, sample_channel):
        """Create videos with all optional fields populated."""
        now = datetime.now(timezone.utc)
        videos = [
            VideoCreate(
                id="video_full",
                channel_id=sample_channel.id,
                title="Full Video",
                description="Complete description with all fields",
                thumbnail_url="https://example.com/full.jpg",
                published_at=now,
                duration_seconds=600,
                yt_tags=["tag1", "tag2", "tag3"],
                is_short=True,
            )
        ]

        await create_videos_bulk(db_session, videos)

        result = await get_videos(db_session, id="video_full", first=True)
        assert result is not None
        assert result.description == "Complete description with all fields"
        assert result.thumbnail_url == "https://example.com/full.jpg"
        assert result.duration_seconds == 600
        assert len(result.yt_tags) == 3
        assert result.is_short is True

    async def test_create_videos_bulk_short_videos(self, db_session, sample_channel):
        """Create YouTube Shorts videos."""
        now = datetime.now(timezone.utc)
        videos = [
            VideoCreate(
                id="short_001",
                channel_id=sample_channel.id,
                title="Short Video #shorts",
                description="A YouTube Short",
                thumbnail_url="https://example.com/short.jpg",
                published_at=now,
                duration_seconds=45,
                yt_tags=["shorts"],
                is_short=True,
            )
        ]

        await create_videos_bulk(db_session, videos)

        result = await get_videos(db_session, id="short_001", first=True)
        assert result.is_short is True
        assert result.duration_seconds == 45

    async def test_create_videos_bulk_with_tags(self, db_session, sample_channel):
        """Create videos with multiple YouTube tags."""
        now = datetime.now(timezone.utc)
        videos = [
            VideoCreate(
                id="video_tags",
                channel_id=sample_channel.id,
                title="Tagged Video",
                description="Video with many tags",
                thumbnail_url="https://example.com/tagged.jpg",
                published_at=now,
                duration_seconds=300,
                yt_tags=["python", "tutorial", "coding", "beginner", "2024"],
                is_short=False,
            )
        ]

        await create_videos_bulk(db_session, videos)

        result = await get_videos(db_session, id="video_tags", first=True)
        assert len(result.yt_tags) == 5
        assert "python" in result.yt_tags
        assert "tutorial" in result.yt_tags

    async def test_create_videos_bulk_large_batch(self, db_session, sample_channel):
        """Bulk create a large batch of videos (100+)."""
        now = datetime.now(timezone.utc)
        videos = [
            VideoCreate(
                id=f"video_large_{str(i).zfill(4)}",
                channel_id=sample_channel.id,
                title=f"Video {i}",
                description=f"Description {i}",
                thumbnail_url=f"https://example.com/thumb{i}.jpg",
                published_at=now - timedelta(hours=i),
                duration_seconds=100 + i,
                yt_tags=[f"tag{i}"],
                is_short=i % 10 == 0,  # Every 10th video is a short
            )
            for i in range(150)
        ]

        await create_videos_bulk(db_session, videos)

        # Verify all were created
        all_videos = await get_videos(db_session, channel_id=sample_channel.id)
        assert len(all_videos) == 150

        # Verify shorts were marked correctly
        shorts = await get_videos(db_session, is_short=True)
        assert len(shorts) == 15  # 150 / 10 = 15 shorts

    async def test_create_videos_bulk_mixed_batch_with_some_duplicates(
        self, db_session, sample_channel
    ):
        """Bulk create with some new and some duplicate videos."""
        now = datetime.now(timezone.utc)

        # First batch: create 3 videos
        videos_batch1 = [
            VideoCreate(
                id=f"video_mixed_{i}",
                channel_id=sample_channel.id,
                title=f"Original {i}",
                description=f"Description {i}",
                thumbnail_url=f"https://example.com/{i}.jpg",
                published_at=now,
                duration_seconds=100,
                yt_tags=[],
                is_short=False,
            )
            for i in range(3)
        ]
        await create_videos_bulk(db_session, videos_batch1)

        # Second batch: 2 duplicates + 2 new videos
        videos_batch2 = [
            # Duplicates (should be ignored)
            VideoCreate(
                id="video_mixed_0",
                channel_id=sample_channel.id,
                title="Updated 0",
                description="Updated",
                thumbnail_url="https://example.com/updated.jpg",
                published_at=now,
                duration_seconds=200,
                yt_tags=[],
                is_short=False,
            ),
            VideoCreate(
                id="video_mixed_1",
                channel_id=sample_channel.id,
                title="Updated 1",
                description="Updated",
                thumbnail_url="https://example.com/updated.jpg",
                published_at=now,
                duration_seconds=200,
                yt_tags=[],
                is_short=False,
            ),
            # New videos (should be inserted)
            VideoCreate(
                id="video_mixed_3",
                channel_id=sample_channel.id,
                title="New 3",
                description="Description 3",
                thumbnail_url="https://example.com/3.jpg",
                published_at=now,
                duration_seconds=100,
                yt_tags=[],
                is_short=False,
            ),
            VideoCreate(
                id="video_mixed_4",
                channel_id=sample_channel.id,
                title="New 4",
                description="Description 4",
                thumbnail_url="https://example.com/4.jpg",
                published_at=now,
                duration_seconds=100,
                yt_tags=[],
                is_short=False,
            ),
        ]
        await create_videos_bulk(db_session, videos_batch2)

        # Verify we have 5 total videos (3 original + 2 new, 2 duplicates ignored)
        all_videos = await get_videos(db_session, channel_id=sample_channel.id)
        assert len(all_videos) == 5

        # Verify duplicates kept original values
        video_0 = await get_videos(db_session, id="video_mixed_0", first=True)
        assert video_0.title == "Original 0"  # Not "Updated 0"
        assert video_0.duration_seconds == 100  # Not 200

    async def test_create_videos_bulk_different_channels(self, db_session):
        """Bulk create videos for multiple channels."""
        # Create two channels
        channel1 = Channel(
            id="UC_channel_1",
            title="Channel 1",
            handle="@channel1",
            uploads_playlist_id="UU_channel_1",
        )
        channel2 = Channel(
            id="UC_channel_2",
            title="Channel 2",
            handle="@channel2",
            uploads_playlist_id="UU_channel_2",
        )
        await create_channel(db_session, channel1)
        await create_channel(db_session, channel2)

        now = datetime.now(timezone.utc)
        videos = [
            VideoCreate(
                id="video_ch1_001",
                channel_id="UC_channel_1",
                title="Channel 1 Video",
                description="From channel 1",
                thumbnail_url="https://example.com/ch1.jpg",
                published_at=now,
                duration_seconds=300,
                yt_tags=[],
                is_short=False,
            ),
            VideoCreate(
                id="video_ch2_001",
                channel_id="UC_channel_2",
                title="Channel 2 Video",
                description="From channel 2",
                thumbnail_url="https://example.com/ch2.jpg",
                published_at=now,
                duration_seconds=400,
                yt_tags=[],
                is_short=False,
            ),
        ]

        await create_videos_bulk(db_session, videos)

        # Verify videos are associated with correct channels
        ch1_videos = await get_videos(db_session, channel_id="UC_channel_1")
        ch2_videos = await get_videos(db_session, channel_id="UC_channel_2")

        assert len(ch1_videos) == 1
        assert len(ch2_videos) == 1
        assert ch1_videos[0].title == "Channel 1 Video"
        assert ch2_videos[0].title == "Channel 2 Video"

    async def test_create_videos_bulk_preserves_published_dates(
        self, db_session, sample_channel
    ):
        """Verify published_at dates are preserved correctly."""
        dates = [
            datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 2, 15, 8, 30, 0, tzinfo=timezone.utc),
            datetime(2024, 3, 20, 18, 45, 0, tzinfo=timezone.utc),
        ]

        videos = [
            VideoCreate(
                id=f"video_date_{i}",
                channel_id=sample_channel.id,
                title=f"Video {i}",
                description=f"Description {i}",
                thumbnail_url=f"https://example.com/{i}.jpg",
                published_at=date,
                duration_seconds=100,
                yt_tags=[],
                is_short=False,
            )
            for i, date in enumerate(dates)
        ]

        await create_videos_bulk(db_session, videos)

        # Verify dates are correct (SQLite strips timezone info, so compare without tz)
        for i, expected_date in enumerate(dates):
            video = await get_videos(db_session, id=f"video_date_{i}", first=True)
            # Compare year, month, day, hour, minute, second (SQLite doesn't preserve timezone)
            assert video.published_at.year == expected_date.year
            assert video.published_at.month == expected_date.month
            assert video.published_at.day == expected_date.day
            assert video.published_at.hour == expected_date.hour
            assert video.published_at.minute == expected_date.minute
            assert video.published_at.second == expected_date.second

    async def test_create_videos_bulk_sets_default_values(
        self, db_session, sample_channel
    ):
        """Verify database defaults are set correctly."""
        now = datetime.now(timezone.utc)
        videos = [
            VideoCreate(
                id="video_defaults",
                channel_id=sample_channel.id,
                title="Defaults Test",
                description="Testing defaults",
                thumbnail_url="https://example.com/defaults.jpg",
                published_at=now,
                duration_seconds=300,
                yt_tags=[],
                is_short=False,
            )
        ]

        await create_videos_bulk(db_session, videos)

        result = await get_videos(db_session, id="video_defaults", first=True)
        assert result.is_favorited is False  # Default value
        assert result.is_watched is False  # Default value
        assert result.created_at is not None  # Auto-generated
        assert result.last_updated is not None  # Auto-generated
