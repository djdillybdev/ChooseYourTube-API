"""
Comprehensive tests for flexible get_folders() CRUD method.

Tests dynamic filtering, pagination, ordering, and hierarchical queries using TDD approach.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from app.db.crud.crud_folder import get_folders
from app.db.models.folder import Folder


@pytest_asyncio.fixture
async def sample_folders(db_session):
    """
    Creates a hierarchical folder structure for testing.

    Returns: List of 8 folders with parent-child relationships:
    - Root folders (parent_id=None): Programming, Databases, Design
    - Child folders of Programming: Frontend, Backend
    - Child folders of Frontend: React, Vue
    - Child folder of Databases: SQL
    """
    now = datetime.now(timezone.utc)

    folders = [
        # Root folders
        Folder(
            id=1,
            name="Programming",
            parent_id=None,
            created_at=now - timedelta(days=1)
        ),
        Folder(
            id=2,
            name="Databases",
            parent_id=None,
            created_at=now - timedelta(days=2)
        ),
        Folder(
            id=3,
            name="Design",
            parent_id=None,
            created_at=now - timedelta(days=3)
        ),
        # Children of Programming (id=1)
        Folder(
            id=4,
            name="Frontend",
            parent_id=1,
            created_at=now - timedelta(days=4)
        ),
        Folder(
            id=5,
            name="Backend",
            parent_id=1,
            created_at=now - timedelta(days=5)
        ),
        # Children of Frontend (id=4)
        Folder(
            id=6,
            name="React",
            parent_id=4,
            created_at=now - timedelta(days=6)
        ),
        Folder(
            id=7,
            name="Vue",
            parent_id=4,
            created_at=now - timedelta(days=7)
        ),
        # Child of Databases (id=2)
        Folder(
            id=8,
            name="SQL",
            parent_id=2,
            created_at=now - timedelta(days=8)
        ),
    ]

    for folder in folders:
        db_session.add(folder)
    await db_session.commit()

    return folders


# Basic Filtering Tests

@pytest.mark.asyncio
class TestGetFoldersBasicFiltering:
    """Tests for single-field filtering."""

    async def test_filter_by_id_returns_single_folder(self, db_session, sample_folders):
        """Should return exactly one folder when filtering by ID with first=True."""
        result = await get_folders(db_session, id=1, first=True)

        assert result is not None
        assert isinstance(result, Folder)
        assert result.id == 1
        assert result.name == "Programming"

    async def test_filter_by_id_returns_list_when_first_false(self, db_session, sample_folders):
        """Should return a list with one folder when first=False."""
        results = await get_folders(db_session, id=1, first=False)

        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].id == 1

    async def test_filter_by_name(self, db_session, sample_folders):
        """Should return folder with exact name match."""
        result = await get_folders(db_session, name="React", first=True)

        assert result is not None
        assert result.name == "React"
        assert result.id == 6

    async def test_filter_by_parent_id(self, db_session, sample_folders):
        """Should return all children of a specific parent folder."""
        results = await get_folders(db_session, parent_id=1)

        assert len(results) == 2  # Frontend, Backend
        assert all(f.parent_id == 1 for f in results)
        names = {f.name for f in results}
        assert names == {"Frontend", "Backend"}

    async def test_filter_root_folders(self, db_session, sample_folders):
        """Should return only root folders (parent_id=None)."""
        results = await get_folders(db_session, parent_id=None)

        assert len(results) == 3  # Programming, Databases, Design
        assert all(f.parent_id is None for f in results)
        names = {f.name for f in results}
        assert names == {"Programming", "Databases", "Design"}


# Hierarchical Query Tests

@pytest.mark.asyncio
class TestGetFoldersHierarchical:
    """Tests for hierarchical folder relationships."""

    async def test_get_direct_children(self, db_session, sample_folders):
        """Should return only direct children of a folder, not grandchildren."""
        # Frontend (id=4) is child of Programming (id=1)
        # React and Vue are children of Frontend
        results = await get_folders(db_session, parent_id=4)

        assert len(results) == 2  # React, Vue (not Backend)
        assert all(f.parent_id == 4 for f in results)

    async def test_folder_with_no_children(self, db_session, sample_folders):
        """Should return empty list for folders with no children."""
        # React (id=6) has no children
        results = await get_folders(db_session, parent_id=6)

        assert results == []

    async def test_multiple_levels_of_nesting(self, db_session, sample_folders):
        """Should correctly filter at different nesting levels."""
        # Root level
        roots = await get_folders(db_session, parent_id=None)
        assert len(roots) == 3

        # Second level
        level2 = await get_folders(db_session, parent_id=1)
        assert len(level2) == 2

        # Third level
        level3 = await get_folders(db_session, parent_id=4)
        assert len(level3) == 2


# Pagination Tests

@pytest.mark.asyncio
class TestGetFoldersPagination:
    """Tests for limit and offset parameters."""

    async def test_limit_restricts_result_count(self, db_session, sample_folders):
        """Should return only the specified number of results."""
        results = await get_folders(db_session, limit=3)

        assert len(results) == 3

    async def test_offset_skips_results(self, db_session, sample_folders):
        """Should skip the first N results."""
        # Get first 3 folders
        first_batch = await get_folders(db_session, limit=3, offset=0)

        # Get next 3 folders
        second_batch = await get_folders(db_session, limit=3, offset=3)

        # IDs should be different
        first_ids = {f.id for f in first_batch}
        second_ids = {f.id for f in second_batch}
        assert first_ids.isdisjoint(second_ids)

    async def test_limit_and_offset_with_filters(self, db_session, sample_folders):
        """Should apply pagination after filtering."""
        # Get root folders with pagination
        results = await get_folders(
            db_session,
            parent_id=None,
            limit=2,
            offset=0
        )

        assert len(results) == 2
        assert all(f.parent_id is None for f in results)

    async def test_offset_beyond_result_set(self, db_session, sample_folders):
        """Should return empty list when offset exceeds total results."""
        results = await get_folders(db_session, offset=100)

        assert results == []

    async def test_limit_none_returns_all(self, db_session, sample_folders):
        """Should return all results when limit=None."""
        results = await get_folders(db_session, limit=None)

        assert len(results) == 8  # All sample folders


# Ordering Tests

@pytest.mark.asyncio
class TestGetFoldersOrdering:
    """Tests for order_by parameter."""

    async def test_order_by_name_asc(self, db_session, sample_folders):
        """Should order alphabetically by name (A-Z)."""
        results = await get_folders(
            db_session,
            order_by="name",
            order_direction="asc"
        )

        names = [f.name for f in results]
        assert names == sorted(names)

    async def test_order_by_name_desc(self, db_session, sample_folders):
        """Should order alphabetically by name (Z-A)."""
        results = await get_folders(
            db_session,
            order_by="name",
            order_direction="desc"
        )

        names = [f.name for f in results]
        assert names == sorted(names, reverse=True)

    async def test_order_by_id_asc(self, db_session, sample_folders):
        """Should order by ID ascending."""
        results = await get_folders(
            db_session,
            order_by="id",
            order_direction="asc"
        )

        ids = [f.id for f in results]
        assert ids == sorted(ids)

    async def test_order_by_id_desc(self, db_session, sample_folders):
        """Should order by ID descending."""
        results = await get_folders(
            db_session,
            order_by="id",
            order_direction="desc"
        )

        ids = [f.id for f in results]
        assert ids == sorted(ids, reverse=True)

    async def test_order_by_created_at_desc(self, db_session, sample_folders):
        """Should order by creation date, newest first."""
        results = await get_folders(
            db_session,
            order_by="created_at",
            order_direction="desc"
        )

        dates = [f.created_at for f in results]
        assert dates == sorted(dates, reverse=True)

    async def test_default_ordering(self, db_session, sample_folders):
        """Should use default ordering (name asc) when not specified."""
        results = await get_folders(db_session)

        # Default: name asc
        names = [f.name for f in results]
        assert names == sorted(names)


# Edge Cases and Error Handling

@pytest.mark.asyncio
class TestGetFoldersEdgeCases:
    """Tests for edge cases and error handling."""

    # Not currently allowing any fields to be used, potential to change in future
    # async def test_invalid_field_name_raises_error(self, db_session, sample_folders):
    #     """Should raise ValueError for invalid field names."""
    #     with pytest.raises(ValueError, match="Invalid filter field"):
    #         await get_folders(db_session, invalid_field="value")

    async def test_invalid_order_by_field_raises_error(self, db_session, sample_folders):
        """Should raise ValueError for invalid order_by field."""
        with pytest.raises(ValueError, match="Invalid order_by field"):
            await get_folders(db_session, order_by="nonexistent_field")

    async def test_invalid_order_direction_raises_error(self, db_session, sample_folders):
        """Should raise ValueError for invalid order direction."""
        with pytest.raises(ValueError, match="order_direction must be 'asc' or 'desc'"):
            await get_folders(db_session, order_direction="sideways")

    async def test_empty_database_returns_empty_list(self, db_session):
        """Should return empty list when no folders exist."""
        results = await get_folders(db_session)

        assert results == []

    async def test_first_true_with_no_results_returns_none(self, db_session, sample_folders):
        """Should return None when first=True and no matches found."""
        result = await get_folders(
            db_session,
            id=999,
            first=True
        )

        assert result is None

    async def test_negative_limit_raises_error(self, db_session, sample_folders):
        """Should validate limit is non-negative."""
        with pytest.raises(ValueError, match="limit must be"):
            await get_folders(db_session, limit=-1)

    async def test_negative_offset_raises_error(self, db_session, sample_folders):
        """Should validate offset is non-negative."""
        with pytest.raises(ValueError, match="offset must be"):
            await get_folders(db_session, offset=-1)


# Return Type Tests

@pytest.mark.asyncio
class TestGetFoldersReturnTypes:
    """Tests for proper return type handling."""

    async def test_first_true_returns_single_object(self, db_session, sample_folders):
        """first=True should return Folder | None, not a list."""
        result = await get_folders(db_session, id=1, first=True)

        assert isinstance(result, Folder)
        assert not isinstance(result, list)

    async def test_first_false_returns_list(self, db_session, sample_folders):
        """first=False should return list[Folder]."""
        results = await get_folders(db_session, first=False)

        assert isinstance(results, list)
        assert all(isinstance(f, Folder) for f in results)

    async def test_default_returns_list(self, db_session, sample_folders):
        """Default behavior (no first param) should return list."""
        results = await get_folders(db_session, parent_id=1)

        assert isinstance(results, list)


# Combined Filter Tests

@pytest.mark.asyncio
class TestGetFoldersCombinedFilters:
    """Tests for combining multiple filters."""

    async def test_filter_by_name_and_parent_id(self, db_session, sample_folders):
        """Should combine name and parent_id filters."""
        result = await get_folders(
            db_session,
            name="Frontend",
            parent_id=1,
            first=True
        )

        assert result is not None
        assert result.name == "Frontend"
        assert result.parent_id == 1

    async def test_combined_filters_with_no_match(self, db_session, sample_folders):
        """Should return empty list when no folders match all filters."""
        results = await get_folders(
            db_session,
            name="React",
            parent_id=1  # React's parent is 4, not 1
        )

        assert results == []

    async def test_filter_with_ordering_and_pagination(self, db_session, sample_folders):
        """Should combine filters, ordering, and pagination."""
        results = await get_folders(
            db_session,
            parent_id=None,  # Root folders only
            order_by="name",
            order_direction="asc",
            limit=2,
            offset=0
        )

        assert len(results) == 2
        assert all(f.parent_id is None for f in results)
        # Should be first 2 alphabetically
        names = [f.name for f in results]
        assert names == sorted(names)
