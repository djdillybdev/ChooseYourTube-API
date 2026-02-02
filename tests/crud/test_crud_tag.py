"""
Comprehensive tests for flexible get_tags() CRUD method.

Tests dynamic filtering, pagination, ordering, and case-insensitive name handling using TDD approach.
"""

import uuid

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from app.db.crud.crud_tag import get_tags
from app.db.models.tag import Tag


@pytest_asyncio.fixture
async def sample_tags(db_session):
    """
    Creates diverse test tags with various attributes.

    Returns: List of 10 Tag objects with different characteristics:
    - All names stored in lowercase (case-insensitive)
    - Various creation dates
    """
    now = datetime.now(timezone.utc)

    tags = [
        Tag(id=str(uuid.uuid4()), name="python", created_at=now - timedelta(days=1)),
        Tag(id=str(uuid.uuid4()), name="javascript", created_at=now - timedelta(days=2)),
        Tag(id=str(uuid.uuid4()), name="tutorial", created_at=now - timedelta(days=3)),
        Tag(id=str(uuid.uuid4()), name="advanced", created_at=now - timedelta(days=4)),
        Tag(id=str(uuid.uuid4()), name="beginner", created_at=now - timedelta(days=5)),
        Tag(id=str(uuid.uuid4()), name="database", created_at=now - timedelta(days=6)),
        Tag(id=str(uuid.uuid4()), name="react", created_at=now - timedelta(days=7)),
        Tag(id=str(uuid.uuid4()), name="algorithms", created_at=now - timedelta(days=8)),
        Tag(id=str(uuid.uuid4()), name="webdev", created_at=now - timedelta(days=9)),
        Tag(id=str(uuid.uuid4()), name="ai", created_at=now - timedelta(days=10)),
    ]

    for tag in tags:
        db_session.add(tag)
    await db_session.commit()

    return tags


# Basic Filtering Tests


@pytest.mark.asyncio
class TestGetTagsBasicFiltering:
    """Tests for single-field filtering."""

    async def test_filter_by_id_returns_single_tag(self, db_session, sample_tags):
        """Should return exactly one tag when filtering by ID with first=True."""
        tag_id = sample_tags[0].id
        result = await get_tags(db_session, id=tag_id, first=True)

        assert result is not None
        assert isinstance(result, Tag)
        assert result.id == tag_id
        assert result.name == "python"

    async def test_filter_by_id_returns_list_when_first_false(
        self, db_session, sample_tags
    ):
        """Should return a list with one tag when first=False."""
        tag_id = sample_tags[0].id
        results = await get_tags(db_session, id=tag_id, first=False)

        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].id == tag_id

    async def test_filter_by_name_exact_match(self, db_session, sample_tags):
        """Should return tag by exact name match (lowercase)."""
        result = await get_tags(db_session, name="python", first=True)

        assert result is not None
        assert result.name == "python"

    async def test_filter_by_name_case_insensitive(self, db_session, sample_tags):
        """Should find tag regardless of case (case-insensitive search)."""
        # Search with different cases should find the same tag
        result_lower = await get_tags(db_session, name="python", first=True)
        result_upper = await get_tags(db_session, name="PYTHON", first=True)
        result_mixed = await get_tags(db_session, name="PyThOn", first=True)

        assert result_lower is not None
        assert result_upper is not None
        assert result_mixed is not None

        # All should find the same tag (stored as lowercase)
        assert result_lower.id == result_upper.id == result_mixed.id
        assert result_lower.name == "python"

    async def test_get_all_tags_no_filters(self, db_session, sample_tags):
        """Should return all tags when no filters applied."""
        results = await get_tags(db_session)

        assert len(results) == 10
        assert all(isinstance(tag, Tag) for tag in results)

    async def test_filter_returns_empty_list_when_no_match(
        self, db_session, sample_tags
    ):
        """Should return empty list when no tags match the filter."""
        results = await get_tags(db_session, name="nonexistent")

        assert results == []

    async def test_filter_by_nonexistent_id(self, db_session, sample_tags):
        """Should return None when filtering by non-existent ID with first=True."""
        result = await get_tags(db_session, id="nonexistent-tag-id", first=True)

        assert result is None


# Pagination Tests


@pytest.mark.asyncio
class TestGetTagsPagination:
    """Tests for limit and offset parameters."""

    async def test_limit_returns_specified_number(self, db_session, sample_tags):
        """Should return exactly limit number of tags."""
        results = await get_tags(db_session, limit=3)

        assert len(results) == 3

    async def test_limit_larger_than_total_returns_all(self, db_session, sample_tags):
        """Should return all tags when limit exceeds total count."""
        results = await get_tags(db_session, limit=100)

        assert len(results) == 10

    async def test_offset_skips_specified_number(self, db_session, sample_tags):
        """Should skip offset number of tags."""
        all_tags = await get_tags(db_session, order_by="name")
        offset_tags = await get_tags(db_session, offset=3, order_by="name")

        assert len(offset_tags) == 7
        assert offset_tags[0].id == all_tags[3].id

    async def test_limit_and_offset_combined(self, db_session, sample_tags):
        """Should apply both limit and offset correctly."""
        results = await get_tags(db_session, limit=3, offset=2, order_by="name")

        assert len(results) == 3
        # Should get tags at indices 2, 3, 4 when ordered by name

    async def test_offset_beyond_total_returns_empty(self, db_session, sample_tags):
        """Should return empty list when offset exceeds total count."""
        results = await get_tags(db_session, offset=100)

        assert results == []

    async def test_limit_zero_returns_empty(self, db_session, sample_tags):
        """Should return empty list for limit=0 (valid SQL but returns no rows)."""
        results = await get_tags(db_session, limit=0)

        assert results == []

    async def test_negative_limit_raises_error(self, db_session, sample_tags):
        """Should raise ValueError for negative limit."""
        with pytest.raises(ValueError, match="limit must be non-negative"):
            await get_tags(db_session, limit=-1)

    async def test_negative_offset_raises_error(self, db_session, sample_tags):
        """Should raise ValueError for negative offset."""
        with pytest.raises(ValueError, match="offset must be non-negative"):
            await get_tags(db_session, offset=-1)


# Ordering Tests


@pytest.mark.asyncio
class TestGetTagsOrdering:
    """Tests for order_by and order_direction parameters."""

    async def test_order_by_name_ascending(self, db_session, sample_tags):
        """Should order tags by name in ascending order (default)."""
        results = await get_tags(db_session, order_by="name", order_direction="asc")

        names = [tag.name for tag in results]
        assert names == sorted(names)

    async def test_order_by_name_descending(self, db_session, sample_tags):
        """Should order tags by name in descending order."""
        results = await get_tags(db_session, order_by="name", order_direction="desc")

        names = [tag.name for tag in results]
        assert names == sorted(names, reverse=True)

    async def test_order_by_created_at_ascending(self, db_session, sample_tags):
        """Should order tags by created_at in ascending order (oldest first)."""
        results = await get_tags(
            db_session, order_by="created_at", order_direction="asc"
        )

        # Oldest tag should be first (created 10 days ago)
        assert results[0].name == "ai"
        assert results[-1].name == "python"

    async def test_order_by_created_at_descending(self, db_session, sample_tags):
        """Should order tags by created_at in descending order (newest first)."""
        results = await get_tags(
            db_session, order_by="created_at", order_direction="desc"
        )

        # Newest tag should be first (created 1 day ago)
        assert results[0].name == "python"
        assert results[-1].name == "ai"

    async def test_order_by_id_ascending(self, db_session, sample_tags):
        """Should order tags by id in ascending order."""
        results = await get_tags(db_session, order_by="id", order_direction="asc")

        ids = [tag.id for tag in results]
        assert ids == sorted(ids)

    async def test_order_by_id_descending(self, db_session, sample_tags):
        """Should order tags by id in descending order."""
        results = await get_tags(db_session, order_by="id", order_direction="desc")

        ids = [tag.id for tag in results]
        assert ids == sorted(ids, reverse=True)

    async def test_default_ordering_is_name_asc(self, db_session, sample_tags):
        """Should default to ordering by name ascending when no order specified."""
        results = await get_tags(db_session)

        names = [tag.name for tag in results]
        assert names == sorted(names)

    async def test_invalid_order_direction_raises_error(self, db_session, sample_tags):
        """Should raise ValueError for invalid order_direction."""
        with pytest.raises(ValueError, match="order_direction must be 'asc' or 'desc'"):
            await get_tags(db_session, order_direction="invalid")

    async def test_invalid_order_by_field_raises_error(self, db_session, sample_tags):
        """Should raise ValueError for invalid order_by field."""
        with pytest.raises(ValueError, match="Invalid order_by field"):
            await get_tags(db_session, order_by="nonexistent_field")


# Edge Cases and Error Handling


@pytest.mark.asyncio
class TestGetTagsEdgeCases:
    """Tests for edge cases and error handling."""

    async def test_empty_database_returns_empty_list(self, db_session):
        """Should return empty list when no tags exist."""
        results = await get_tags(db_session)

        assert results == []

    async def test_empty_database_with_first_returns_none(self, db_session):
        """Should return None when no tags exist and first=True."""
        result = await get_tags(db_session, first=True)

        assert result is None

    async def test_filter_with_pagination_and_ordering(self, db_session, sample_tags):
        """Should correctly combine filtering, pagination, and ordering."""
        # Get tags ordered by name, skip first 2, take 3
        results = await get_tags(
            db_session, limit=3, offset=2, order_by="name", order_direction="asc"
        )

        assert len(results) == 3
        # Should be alphabetically sorted
        names = [tag.name for tag in results]
        assert names == sorted(names)


# Return Type Tests


@pytest.mark.asyncio
class TestGetTagsReturnTypes:
    """Tests for proper return type handling."""

    async def test_first_true_returns_single_object(self, db_session, sample_tags):
        """first=True should return Tag | None, not a list."""
        result = await get_tags(db_session, name="python", first=True)

        assert isinstance(result, Tag)
        assert not isinstance(result, list)

    async def test_first_false_returns_list(self, db_session, sample_tags):
        """first=False should return list[Tag], even with one result."""
        results = await get_tags(db_session, name="python", first=False)

        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], Tag)

    async def test_first_true_with_no_match_returns_none(self, db_session, sample_tags):
        """first=True with no match should return None, not empty list."""
        result = await get_tags(db_session, name="nonexistent", first=True)

        assert result is None
        assert not isinstance(result, list)

    async def test_first_false_with_no_match_returns_empty_list(
        self, db_session, sample_tags
    ):
        """first=False with no match should return empty list."""
        results = await get_tags(db_session, name="nonexistent", first=False)

        assert isinstance(results, list)
        assert len(results) == 0

    async def test_default_first_false_returns_list(self, db_session, sample_tags):
        """Default behavior (first=False) should return list."""
        results = await get_tags(db_session)

        assert isinstance(results, list)
        assert len(results) == 10


# List-Based Filtering Tests


@pytest.mark.asyncio
class TestGetTagsListFiltering:
    """Tests for list-based filtering (IN clauses)."""

    async def test_filter_by_id_list(self, db_session, sample_tags):
        """Should return multiple tags by ID list."""
        # Get first 3 tag IDs
        tag_ids = [sample_tags[0].id, sample_tags[2].id, sample_tags[5].id]

        results = await get_tags(db_session, id=tag_ids)

        assert len(results) == 3
        result_ids = {t.id for t in results}
        assert result_ids == set(tag_ids)

        # Should get python, tutorial, database
        names = {t.name for t in results}
        assert names == {"python", "tutorial", "database"}

    async def test_filter_empty_list_raises_error(self, db_session, sample_tags):
        """Should reject empty filter lists."""
        with pytest.raises(ValueError, match="cannot be empty"):
            await get_tags(db_session, id=[])
