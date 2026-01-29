"""
Comprehensive tests for flexible get_channels() CRUD method.

Tests dynamic filtering, pagination, ordering, and folder relationships using TDD approach.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from app.db.crud.crud_channel import get_channels
from app.db.models.channel import Channel


@pytest_asyncio.fixture
async def sample_channels(db_session):
    """
    Creates diverse test channels with various attributes.

    Returns: List of 10 Channel objects with different characteristics:
    - Mix of favorited/non-favorited
    - Different folders (some with folder_id=None)
    - Various handles and titles
    - Different creation dates
    """
    now = datetime.now(timezone.utc)

    channels = [
        Channel(
            id="ch001",
            title="Tech Tutorials",
            handle="@techtutorials",
            uploads_playlist_id="UU001",
            is_favorited=True,
            folder_id=1,
            created_at=now - timedelta(days=1)
        ),
        Channel(
            id="ch002",
            title="Programming Academy",
            handle="@progacademy",
            uploads_playlist_id="UU002",
            is_favorited=False,
            folder_id=1,
            created_at=now - timedelta(days=2)
        ),
        Channel(
            id="ch003",
            title="Quick Tips Daily",
            handle="@quicktips",
            uploads_playlist_id="UU003",
            is_favorited=True,
            folder_id=2,
            created_at=now - timedelta(days=3)
        ),
        Channel(
            id="ch004",
            title="Database Deep Dive",
            handle="@dbdeepdive",
            uploads_playlist_id="UU004",
            is_favorited=False,
            folder_id=None,  # No folder
            created_at=now - timedelta(days=4)
        ),
        Channel(
            id="ch005",
            title="React Masters",
            handle="@reactmasters",
            uploads_playlist_id="UU005",
            is_favorited=True,
            folder_id=None,
            created_at=now - timedelta(days=5)
        ),
        Channel(
            id="ch006",
            title="Python Weekly",
            handle="@pythonweekly",
            uploads_playlist_id="UU006",
            is_favorited=False,
            folder_id=2,
            created_at=now - timedelta(days=6)
        ),
        Channel(
            id="ch007",
            title="Algorithms Explained",
            handle="@algoexplained",
            uploads_playlist_id="UU007",
            is_favorited=True,
            folder_id=3,
            created_at=now - timedelta(days=7)
        ),
        Channel(
            id="ch008",
            title="Web Dev Basics",
            handle="@webdevbasics",
            uploads_playlist_id="UU008",
            is_favorited=False,
            folder_id=3,
            created_at=now - timedelta(days=8)
        ),
        Channel(
            id="ch009",
            title="AI Innovations",
            handle="@aiinnovations",
            uploads_playlist_id="UU009",
            is_favorited=True,
            folder_id=1,
            created_at=now - timedelta(days=9)
        ),
        Channel(
            id="ch010",
            title="Cloud Computing 101",
            handle="@cloudcomputing101",
            uploads_playlist_id="UU010",
            is_favorited=False,
            folder_id=None,
            created_at=now - timedelta(days=10)
        ),
    ]

    for channel in channels:
        db_session.add(channel)
    await db_session.commit()

    return channels


# Basic Filtering Tests

@pytest.mark.asyncio
class TestGetChannelsBasicFiltering:
    """Tests for single-field filtering."""

    async def test_filter_by_id_returns_single_channel(self, db_session, sample_channels):
        """Should return exactly one channel when filtering by ID with first=True."""
        result = await get_channels(db_session, id="ch001", first=True)

        assert result is not None
        assert isinstance(result, Channel)
        assert result.id == "ch001"
        assert result.title == "Tech Tutorials"

    async def test_filter_by_id_returns_list_when_first_false(self, db_session, sample_channels):
        """Should return a list with one channel when first=False."""
        results = await get_channels(db_session, id="ch001", first=False)

        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].id == "ch001"

    async def test_filter_by_handle(self, db_session, sample_channels):
        """Should return channel by handle."""
        result = await get_channels(db_session, handle="@techtutorials", first=True)

        assert result is not None
        assert result.handle == "@techtutorials"
        assert result.id == "ch001"

    async def test_filter_by_title(self, db_session, sample_channels):
        """Should return channel with exact title match."""
        result = await get_channels(db_session, title="React Masters", first=True)

        assert result is not None
        assert result.title == "React Masters"
        assert result.id == "ch005"

    async def test_filter_by_folder_id(self, db_session, sample_channels):
        """Should return all channels in a folder."""
        results = await get_channels(db_session, folder_id=1)

        assert len(results) == 3  # ch001, ch002, ch009
        assert all(c.folder_id == 1 for c in results)

    async def test_filter_by_folder_id_none(self, db_session, sample_channels):
        """Should return channels with no folder."""
        results = await get_channels(db_session, folder_id=None)

        assert len(results) == 3  # ch004, ch005, ch010
        assert all(c.folder_id is None for c in results)

    async def test_filter_by_is_favorited_true(self, db_session, sample_channels):
        """Should return only favorited channels."""
        results = await get_channels(db_session, is_favorited=True)

        assert len(results) == 5  # ch001, ch003, ch005, ch007, ch009
        assert all(c.is_favorited is True for c in results)

    async def test_filter_by_is_favorited_false(self, db_session, sample_channels):
        """Should return only non-favorited channels."""
        results = await get_channels(db_session, is_favorited=False)

        assert len(results) == 5  # ch002, ch004, ch006, ch008, ch010
        assert all(c.is_favorited is False for c in results)


# Multiple Filter Combination Tests

@pytest.mark.asyncio
class TestGetChannelsMultipleFilters:
    """Tests for combining multiple filters."""

    async def test_filter_by_folder_and_is_favorited(self, db_session, sample_channels):
        """Should return favorited channels in specific folder."""
        results = await get_channels(
            db_session,
            folder_id=1,
            is_favorited=True
        )

        assert len(results) == 2  # ch001, ch009
        assert all(c.folder_id == 1 and c.is_favorited is True for c in results)

    async def test_filter_no_folder_and_favorited(self, db_session, sample_channels):
        """Should return favorited channels with no folder."""
        results = await get_channels(
            db_session,
            folder_id=None,
            is_favorited=True
        )

        assert len(results) == 1  # Only ch005
        assert results[0].id == "ch005"

    async def test_filter_by_folder_and_not_favorited(self, db_session, sample_channels):
        """Should combine folder and is_favorited=False filters."""
        results = await get_channels(
            db_session,
            folder_id=3,
            is_favorited=False
        )

        assert len(results) == 1  # Only ch008
        assert results[0].id == "ch008"

    async def test_multiple_filters_with_no_matches(self, db_session, sample_channels):
        """Should return empty list when no channels match all filters."""
        results = await get_channels(
            db_session,
            folder_id=1,
            title="Python Weekly"  # Python Weekly is in folder 2, not 1
        )

        assert results == []


# Pagination Tests

@pytest.mark.asyncio
class TestGetChannelsPagination:
    """Tests for limit and offset parameters."""

    async def test_limit_restricts_result_count(self, db_session, sample_channels):
        """Should return only the specified number of results."""
        results = await get_channels(db_session, limit=3)

        assert len(results) == 3

    async def test_offset_skips_results(self, db_session, sample_channels):
        """Should skip the first N results."""
        # Get first 4 channels
        first_batch = await get_channels(db_session, limit=4, offset=0)

        # Get next 4 channels
        second_batch = await get_channels(db_session, limit=4, offset=4)

        # IDs should be different
        first_ids = {c.id for c in first_batch}
        second_ids = {c.id for c in second_batch}
        assert first_ids.isdisjoint(second_ids)

    async def test_limit_and_offset_with_filters(self, db_session, sample_channels):
        """Should apply pagination after filtering."""
        results = await get_channels(
            db_session,
            is_favorited=True,
            limit=2,
            offset=1
        )

        assert len(results) == 2
        assert all(c.is_favorited is True for c in results)

    async def test_offset_beyond_result_set(self, db_session, sample_channels):
        """Should return empty list when offset exceeds total results."""
        results = await get_channels(db_session, offset=100)

        assert results == []

    async def test_limit_none_returns_all(self, db_session, sample_channels):
        """Should return all results when limit=None."""
        results = await get_channels(db_session, limit=None)

        assert len(results) == 10  # All sample channels


# Ordering Tests

@pytest.mark.asyncio
class TestGetChannelsOrdering:
    """Tests for order_by parameter."""

    async def test_order_by_title_asc(self, db_session, sample_channels):
        """Should order alphabetically by title (A-Z)."""
        results = await get_channels(
            db_session,
            order_by="title",
            order_direction="asc"
        )

        titles = [c.title for c in results]
        assert titles == sorted(titles)

    async def test_order_by_title_desc(self, db_session, sample_channels):
        """Should order alphabetically by title (Z-A)."""
        results = await get_channels(
            db_session,
            order_by="title",
            order_direction="desc"
        )

        titles = [c.title for c in results]
        assert titles == sorted(titles, reverse=True)

    async def test_order_by_handle_asc(self, db_session, sample_channels):
        """Should order alphabetically by handle."""
        results = await get_channels(
            db_session,
            order_by="handle",
            order_direction="asc"
        )

        handles = [c.handle for c in results]
        assert handles == sorted(handles)

    async def test_order_by_created_at_desc(self, db_session, sample_channels):
        """Should order by creation date, newest first."""
        results = await get_channels(
            db_session,
            order_by="created_at",
            order_direction="desc"
        )

        dates = [c.created_at for c in results]
        assert dates == sorted(dates, reverse=True)

    async def test_order_by_created_at_asc(self, db_session, sample_channels):
        """Should order by creation date, oldest first."""
        results = await get_channels(
            db_session,
            order_by="created_at",
            order_direction="asc"
        )

        dates = [c.created_at for c in results]
        assert dates == sorted(dates)

    async def test_default_ordering(self, db_session, sample_channels):
        """Should use default ordering (title asc) when not specified."""
        results = await get_channels(db_session)

        # Default: title asc
        titles = [c.title for c in results]
        assert titles == sorted(titles)


# Edge Cases and Error Handling

@pytest.mark.asyncio
class TestGetChannelsEdgeCases:
    """Tests for edge cases and error handling."""

    async def test_invalid_order_by_field_raises_error(self, db_session, sample_channels):
        """Should raise ValueError for invalid order_by field."""
        with pytest.raises(ValueError, match="Invalid order_by field"):
            await get_channels(db_session, order_by="nonexistent_field")

    async def test_invalid_order_direction_raises_error(self, db_session, sample_channels):
        """Should raise ValueError for invalid order direction."""
        with pytest.raises(ValueError, match="order_direction must be 'asc' or 'desc'"):
            await get_channels(db_session, order_direction="sideways")

    async def test_empty_database_returns_empty_list(self, db_session):
        """Should return empty list when no channels exist."""
        results = await get_channels(db_session)

        assert results == []

    async def test_first_true_with_no_results_returns_none(self, db_session, sample_channels):
        """Should return None when first=True and no matches found."""
        result = await get_channels(
            db_session,
            id="nonexistent",
            first=True
        )

        assert result is None

    async def test_negative_limit_raises_error(self, db_session, sample_channels):
        """Should validate limit is non-negative."""
        with pytest.raises(ValueError, match="limit must be"):
            await get_channels(db_session, limit=-1)

    async def test_negative_offset_raises_error(self, db_session, sample_channels):
        """Should validate offset is non-negative."""
        with pytest.raises(ValueError, match="offset must be"):
            await get_channels(db_session, offset=-1)


# Return Type Tests

@pytest.mark.asyncio
class TestGetChannelsReturnTypes:
    """Tests for proper return type handling."""

    async def test_first_true_returns_single_object(self, db_session, sample_channels):
        """first=True should return Channel | None, not a list."""
        result = await get_channels(db_session, id="ch001", first=True)

        assert isinstance(result, Channel)
        assert not isinstance(result, list)

    async def test_first_false_returns_list(self, db_session, sample_channels):
        """first=False should return list[Channel]."""
        results = await get_channels(db_session, first=False)

        assert isinstance(results, list)
        assert all(isinstance(c, Channel) for c in results)

    async def test_default_returns_list(self, db_session, sample_channels):
        """Default behavior (no first param) should return list."""
        results = await get_channels(db_session, folder_id=1)

        assert isinstance(results, list)


# Folder Relationship Tests

@pytest.mark.asyncio
class TestGetChannelsFolderRelationships:
    """Tests for folder-related queries."""

    async def test_get_all_channels_in_folder(self, db_session, sample_channels):
        """Should get all channels in a specific folder."""
        results = await get_channels(db_session, folder_id=2)

        assert len(results) == 2  # ch003, ch006
        assert all(c.folder_id == 2 for c in results)

    async def test_get_channels_without_folder(self, db_session, sample_channels):
        """Should get all channels not in any folder."""
        results = await get_channels(db_session, folder_id=None)

        assert len(results) == 3  # ch004, ch005, ch010
        assert all(c.folder_id is None for c in results)

    async def test_filter_favorited_channels_in_folder(self, db_session, sample_channels):
        """Should combine folder filter with favorited status."""
        results = await get_channels(
            db_session,
            folder_id=2,
            is_favorited=True
        )

        assert len(results) == 1  # Only ch003
        assert results[0].id == "ch003"
        assert results[0].folder_id == 2
        assert results[0].is_favorited is True


# Combined Filter Tests

@pytest.mark.asyncio
class TestGetChannelsCombinedFilters:
    """Tests for combining multiple filters."""

    async def test_filter_by_handle_and_folder(self, db_session, sample_channels):
        """Should combine handle and folder_id filters."""
        result = await get_channels(
            db_session,
            handle="@techtutorials",
            folder_id=1,
            first=True
        )

        assert result is not None
        assert result.handle == "@techtutorials"
        assert result.folder_id == 1

    async def test_combined_filters_with_ordering(self, db_session, sample_channels):
        """Should combine filters with custom ordering."""
        results = await get_channels(
            db_session,
            is_favorited=True,
            order_by="created_at",
            order_direction="asc"
        )

        assert len(results) == 5
        assert all(c.is_favorited is True for c in results)
        # Should be ordered by creation date (oldest first)
        dates = [c.created_at for c in results]
        assert dates == sorted(dates)

    async def test_filter_with_ordering_and_pagination(self, db_session, sample_channels):
        """Should combine filters, ordering, and pagination."""
        results = await get_channels(
            db_session,
            folder_id=1,
            order_by="title",
            order_direction="asc",
            limit=2,
            offset=0
        )

        assert len(results) == 2
        assert all(c.folder_id == 1 for c in results)
        # Should be first 2 alphabetically
        titles = [c.title for c in results]
        assert titles == sorted(titles)
