"""
Comprehensive tests for flexible get_videos() CRUD method.

Tests dynamic filtering, pagination, ordering, and edge cases using TDD approach.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from app.db.crud.crud_video import get_videos
from app.db.models.video import Video


@pytest_asyncio.fixture
async def sample_videos(db_session):
    """
    Creates a diverse set of test videos with various attributes.

    Returns: List of 10 Video objects with different characteristics:
    - Mix of favorited/non-favorited
    - Mix of shorts/regular videos
    - Mix of watched/unwatched
    - Multiple channels
    - Various publish dates
    """
    now = datetime.now(timezone.utc)

    videos = [
        Video(
            id="vid001",
            channel_id="ch001",
            title="Introduction to Python",
            is_favorited=True,
            is_short=False,
            is_watched=True,
            published_at=now - timedelta(days=1),
            duration_seconds=600
        ),
        Video(
            id="vid002",
            channel_id="ch001",
            title="Quick Python Tip #shorts",
            is_favorited=False,
            is_short=True,
            is_watched=False,
            published_at=now - timedelta(days=2),
            duration_seconds=45
        ),
        Video(
            id="vid003",
            channel_id="ch002",
            title="Advanced React Patterns",
            is_favorited=True,
            is_short=False,
            is_watched=False,
            published_at=now - timedelta(days=3),
            duration_seconds=1200
        ),
        Video(
            id="vid004",
            channel_id="ch002",
            title="React Hooks Explained #shorts",
            is_favorited=False,
            is_short=True,
            is_watched=True,
            published_at=now - timedelta(days=4),
            duration_seconds=50
        ),
        Video(
            id="vid005",
            channel_id="ch003",
            title="Database Design Tutorial",
            is_favorited=False,
            is_short=False,
            is_watched=False,
            published_at=now - timedelta(days=5),
            duration_seconds=900
        ),
        Video(
            id="vid006",
            channel_id="ch003",
            title="Test Video 6",
            is_favorited=False,
            is_short=False,
            is_watched=False,
            published_at=now - timedelta(days=6),
            duration_seconds=300
        ),
        Video(
            id="vid007",
            channel_id="ch001",
            title="Test Video 7",
            is_favorited=True,
            is_short=True,
            is_watched=True,
            published_at=now - timedelta(days=7),
            duration_seconds=30
        ),
        Video(
            id="vid008",
            channel_id="ch002",
            title="Test Video 8",
            is_favorited=False,
            is_short=False,
            is_watched=False,
            published_at=now - timedelta(days=8),
            duration_seconds=500
        ),
        Video(
            id="vid009",
            channel_id="ch003",
            title="Test Video 9",
            is_favorited=True,
            is_short=False,
            is_watched=True,
            published_at=now - timedelta(days=9),
            duration_seconds=700
        ),
        Video(
            id="vid010",
            channel_id="ch001",
            title="Test Video 10",
            is_favorited=False,
            is_short=True,
            is_watched=False,
            published_at=now - timedelta(days=10),
            duration_seconds=55
        ),
    ]

    for video in videos:
        db_session.add(video)
    await db_session.commit()

    return videos


# Basic Filtering Tests

@pytest.mark.asyncio
class TestGetVideosBasicFiltering:
    """Tests for single-field filtering."""

    async def test_filter_by_id_returns_single_video(self, db_session, sample_videos):
        """Should return exactly one video when filtering by ID with first=True."""
        result = await get_videos(db_session, id="vid001", first=True)

        assert result is not None
        assert isinstance(result, Video)
        assert result.id == "vid001"
        assert result.title == "Introduction to Python"

    async def test_filter_by_id_returns_list_when_first_false(self, db_session, sample_videos):
        """Should return a list with one video when first=False."""
        results = await get_videos(db_session, id="vid001", first=False)

        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].id == "vid001"

    async def test_filter_by_channel_id(self, db_session, sample_videos):
        """Should return all videos for a specific channel."""
        results = await get_videos(db_session, channel_id="ch001")

        assert len(results) == 4  # vid001, vid002, vid007, vid010
        assert all(v.channel_id == "ch001" for v in results)

    async def test_filter_by_is_favorited_true(self, db_session, sample_videos):
        """Should return only favorited videos."""
        results = await get_videos(db_session, is_favorited=True)

        assert len(results) == 4  # vid001, vid003, vid007, vid009
        assert all(v.is_favorited is True for v in results)

    async def test_filter_by_is_short_true(self, db_session, sample_videos):
        """Should return only YouTube Shorts."""
        results = await get_videos(db_session, is_short=True)

        assert len(results) == 4  # vid002, vid004, vid007, vid010
        assert all(v.is_short is True for v in results)

    async def test_filter_by_is_watched_false(self, db_session, sample_videos):
        """Should return only unwatched videos."""
        results = await get_videos(db_session, is_watched=False)

        expected_count = 6  # vid002, vid003, vid005, vid006, vid008, vid010
        assert len(results) == expected_count
        assert all(v.is_watched is False for v in results)


# Multiple Filter Combination Tests

@pytest.mark.asyncio
class TestGetVideosMultipleFilters:
    """Tests for combining multiple filters."""

    async def test_filter_by_channel_and_is_short(self, db_session, sample_videos):
        """Should return shorts from specific channel."""
        results = await get_videos(
            db_session,
            channel_id="ch001",
            is_short=True
        )

        assert len(results) == 3  # vid002, vid007, vid010
        assert all(v.channel_id == "ch001" and v.is_short is True for v in results)

    async def test_filter_by_favorited_and_unwatched(self, db_session, sample_videos):
        """Should return favorited videos that haven't been watched yet."""
        results = await get_videos(
            db_session,
            is_favorited=True,
            is_watched=False
        )

        assert len(results) == 1  # Only vid003
        assert results[0].id == "vid003"

    async def test_filter_by_channel_favorited_and_short(self, db_session, sample_videos):
        """Should combine three filters: channel + favorited + shorts."""
        results = await get_videos(
            db_session,
            channel_id="ch001",
            is_favorited=True,
            is_short=True
        )

        assert len(results) == 1  # Only vid007
        assert results[0].id == "vid007"

    async def test_multiple_filters_with_no_matches(self, db_session, sample_videos):
        """Should return empty list when no videos match all filters."""
        results = await get_videos(
            db_session,
            channel_id="ch001",
            is_favorited=True,
            is_short=False,
            is_watched=False
        )

        assert results == []


# Pagination Tests

@pytest.mark.asyncio
class TestGetVideosPagination:
    """Tests for limit and offset parameters."""

    async def test_limit_restricts_result_count(self, db_session, sample_videos):
        """Should return only the specified number of results."""
        results = await get_videos(db_session, limit=3)

        assert len(results) == 3

    async def test_offset_skips_results(self, db_session, sample_videos):
        """Should skip the first N results."""
        # Get first 3 videos
        first_batch = await get_videos(db_session, limit=3, offset=0)

        # Get next 3 videos
        second_batch = await get_videos(db_session, limit=3, offset=3)

        # IDs should be different
        first_ids = {v.id for v in first_batch}
        second_ids = {v.id for v in second_batch}
        assert first_ids.isdisjoint(second_ids)

    async def test_limit_and_offset_with_filters(self, db_session, sample_videos):
        """Should apply pagination after filtering."""
        results = await get_videos(
            db_session,
            channel_id="ch001",
            limit=2,
            offset=1
        )

        assert len(results) == 2
        assert all(v.channel_id == "ch001" for v in results)

    async def test_offset_beyond_result_set(self, db_session, sample_videos):
        """Should return empty list when offset exceeds total results."""
        results = await get_videos(db_session, offset=100)

        assert results == []

    async def test_limit_none_returns_all(self, db_session, sample_videos):
        """Should return all results when limit=None."""
        results = await get_videos(db_session, limit=None)

        assert len(results) == 10  # All sample videos


# Ordering Tests

@pytest.mark.asyncio
class TestGetVideosOrdering:
    """Tests for order_by parameter."""

    async def test_order_by_published_at_desc(self, db_session, sample_videos):
        """Should order by published_at descending (newest first)."""
        results = await get_videos(
            db_session,
            order_by="published_at",
            order_direction="desc"
        )

        # Check dates are in descending order
        dates = [v.published_at for v in results if v.published_at]
        assert dates == sorted(dates, reverse=True)

    async def test_order_by_published_at_asc(self, db_session, sample_videos):
        """Should order by published_at ascending (oldest first)."""
        results = await get_videos(
            db_session,
            order_by="published_at",
            order_direction="asc"
        )

        dates = [v.published_at for v in results if v.published_at]
        assert dates == sorted(dates)

    async def test_order_by_title_asc(self, db_session, sample_videos):
        """Should order alphabetically by title."""
        results = await get_videos(
            db_session,
            order_by="title",
            order_direction="asc"
        )

        titles = [v.title for v in results]
        assert titles == sorted(titles)

    async def test_order_by_duration_desc(self, db_session, sample_videos):
        """Should order by video duration, longest first."""
        results = await get_videos(
            db_session,
            order_by="duration_seconds",
            order_direction="desc"
        )

        durations = [v.duration_seconds for v in results if v.duration_seconds]
        assert durations == sorted(durations, reverse=True)

    async def test_default_ordering(self, db_session, sample_videos):
        """Should use default ordering when order_by not specified."""
        results = await get_videos(db_session)

        # Default: published_at desc
        # Just verify we got results in some consistent order
        assert len(results) == 10


# Edge Cases and Error Handling

@pytest.mark.asyncio
class TestGetVideosEdgeCases:
    """Tests for edge cases and error handling."""

    async def test_invalid_field_name_raises_error(self, db_session, sample_videos):
        """Should raise ValueError for invalid field names."""
        with pytest.raises(ValueError, match="Invalid filter field"):
            await get_videos(db_session, invalid_field="value")

    async def test_invalid_order_by_field_raises_error(self, db_session, sample_videos):
        """Should raise ValueError for invalid order_by field."""
        with pytest.raises(ValueError, match="Invalid order_by field"):
            await get_videos(db_session, order_by="nonexistent_field")

    async def test_invalid_order_direction_raises_error(self, db_session, sample_videos):
        """Should raise ValueError for invalid order direction."""
        with pytest.raises(ValueError, match="order_direction must be 'asc' or 'desc'"):
            await get_videos(db_session, order_direction="sideways")

    async def test_empty_database_returns_empty_list(self, db_session):
        """Should return empty list when no videos exist."""
        results = await get_videos(db_session)

        assert results == []

    async def test_first_true_with_no_results_returns_none(self, db_session, sample_videos):
        """Should return None when first=True and no matches found."""
        result = await get_videos(
            db_session,
            id="nonexistent",
            first=True
        )

        assert result is None

    async def test_negative_limit_raises_error(self, db_session, sample_videos):
        """Should validate limit is non-negative."""
        with pytest.raises(ValueError, match="limit must be"):
            await get_videos(db_session, limit=-1)

    async def test_negative_offset_raises_error(self, db_session, sample_videos):
        """Should validate offset is non-negative."""
        with pytest.raises(ValueError, match="offset must be"):
            await get_videos(db_session, offset=-1)


# Return Type Tests

@pytest.mark.asyncio
class TestGetVideosReturnTypes:
    """Tests for proper return type handling."""

    async def test_first_true_returns_single_object(self, db_session, sample_videos):
        """first=True should return Video | None, not a list."""
        result = await get_videos(db_session, id="vid001", first=True)

        assert isinstance(result, Video)
        assert not isinstance(result, list)

    async def test_first_false_returns_list(self, db_session, sample_videos):
        """first=False should return list[Video]."""
        results = await get_videos(db_session, first=False)

        assert isinstance(results, list)
        assert all(isinstance(v, Video) for v in results)

    async def test_default_returns_list(self, db_session, sample_videos):
        """Default behavior (no first param) should return list."""
        results = await get_videos(db_session, channel_id="ch001")

        assert isinstance(results, list)
