"""
Comprehensive tests for tag write operations (create, delete).

Tests create_tag(), get_or_create_tag(), delete_tag(), and delete_all_tags() methods.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from app.db.crud.crud_tag import create_tag, get_or_create_tag, delete_tag, delete_all_tags, get_tags
from app.db.models.tag import Tag


@pytest.mark.asyncio
class TestCreateTag:
    """Tests for create_tag() function."""

    async def test_create_tag_with_lowercase_name(self, db_session):
        """Create a tag with lowercase name."""
        tag = Tag(name="python")

        result = await create_tag(db_session, tag)

        assert result.name == "python"
        assert result.id is not None
        assert isinstance(result.created_at, datetime)

    async def test_create_tag_normalizes_to_lowercase(self, db_session):
        """Tag names should be normalized to lowercase on creation."""
        tag = Tag(name="JAVASCRIPT")

        result = await create_tag(db_session, tag)

        # Name should be stored as lowercase
        assert result.name == "javascript"
        assert result.id is not None

    async def test_create_tag_with_mixed_case(self, db_session):
        """Tag with mixed case should be normalized to lowercase."""
        tag = Tag(name="PyThOn")

        result = await create_tag(db_session, tag)

        assert result.name == "python"

    async def test_create_tag_persists_to_database(self, db_session):
        """Verify tag is actually persisted and can be retrieved."""
        tag = Tag(name="react")

        created_tag = await create_tag(db_session, tag)

        # Retrieve the tag using get_tags
        retrieved = await get_tags(db_session, id=created_tag.id, first=True)
        assert retrieved is not None
        assert retrieved.name == "react"

    async def test_create_tag_with_duplicate_name_raises_integrity_error(self, db_session):
        """Creating a tag with duplicate name should raise IntegrityError (unique constraint)."""
        tag1 = Tag(name="database")
        await create_tag(db_session, tag1)

        # Try to create another tag with same name
        tag2 = Tag(name="database")

        with pytest.raises(IntegrityError):
            await create_tag(db_session, tag2)

    async def test_create_tag_duplicate_name_different_case_raises_error(self, db_session):
        """Creating a tag with same name but different case should raise IntegrityError."""
        tag1 = Tag(name="typescript")
        await create_tag(db_session, tag1)

        # Try to create with different case (should still conflict)
        tag2 = Tag(name="TypeScript")

        with pytest.raises(IntegrityError):
            await create_tag(db_session, tag2)

    async def test_create_tag_returns_refreshed_instance(self, db_session):
        """Verify returned tag has database-generated values."""
        tag = Tag(name="algorithm")

        result = await create_tag(db_session, tag)

        # id and created_at should be populated by database
        assert result.id is not None
        assert result.created_at is not None
        assert isinstance(result.created_at, datetime)

    async def test_create_multiple_tags(self, db_session):
        """Create multiple tags in sequence."""
        tag_names = ["python", "javascript", "go", "rust", "ruby"]

        for name in tag_names:
            tag = Tag(name=name)
            await create_tag(db_session, tag)

        # Verify all were created
        all_tags = await get_tags(db_session)
        assert len(all_tags) == 5
        tag_names_in_db = {tag.name for tag in all_tags}
        assert tag_names_in_db == set(tag_names)

    async def test_create_tag_with_special_characters(self, db_session):
        """Create tag with hyphens and underscores (common in tag names)."""
        tag = Tag(name="machine-learning")

        result = await create_tag(db_session, tag)

        assert result.name == "machine-learning"

    async def test_create_tag_with_numbers(self, db_session):
        """Create tag with numbers in the name."""
        tag = Tag(name="python3")

        result = await create_tag(db_session, tag)

        assert result.name == "python3"

    async def test_create_tag_created_at_is_set(self, db_session):
        """Verify created_at timestamp is set."""
        tag = Tag(name="timestamp-test")
        result = await create_tag(db_session, tag)

        # Verify created_at is set and is a datetime
        assert result.created_at is not None
        assert isinstance(result.created_at, datetime)


@pytest.mark.asyncio
class TestGetOrCreateTag:
    """Tests for get_or_create_tag() idempotent creation function."""

    async def test_get_or_create_creates_new_tag(self, db_session):
        """Should create a new tag if it doesn't exist."""
        result = await get_or_create_tag(db_session, "python")

        assert result.name == "python"
        assert result.id is not None

        # Verify it was persisted
        retrieved = await get_tags(db_session, name="python", first=True)
        assert retrieved is not None
        assert retrieved.id == result.id

    async def test_get_or_create_returns_existing_tag(self, db_session):
        """Should return existing tag if it already exists."""
        # Create a tag first
        original = Tag(name="javascript")
        created = await create_tag(db_session, original)

        # Call get_or_create with same name
        result = await get_or_create_tag(db_session, "javascript")

        # Should return the same tag (same ID)
        assert result.id == created.id
        assert result.name == "javascript"

        # Should not create a duplicate
        all_tags = await get_tags(db_session, name="javascript")
        assert len(all_tags) == 1

    async def test_get_or_create_case_insensitive(self, db_session):
        """Should return existing tag regardless of case used in search."""
        # Create tag with lowercase
        original = Tag(name="react")
        created = await create_tag(db_session, original)

        # Call get_or_create with uppercase
        result = await get_or_create_tag(db_session, "REACT")

        # Should return the existing tag (normalized to lowercase)
        assert result.id == created.id
        assert result.name == "react"  # Stored as lowercase

        # Should not create a duplicate
        all_tags = await get_tags(db_session)
        assert len(all_tags) == 1

    async def test_get_or_create_mixed_case(self, db_session):
        """Should handle mixed case correctly."""
        # Create with mixed case (stored as lowercase)
        result1 = await get_or_create_tag(db_session, "PyThOn")
        assert result1.name == "python"

        # Get with different case
        result2 = await get_or_create_tag(db_session, "PYTHON")
        assert result2.id == result1.id
        assert result2.name == "python"

    async def test_get_or_create_multiple_calls_same_tag(self, db_session):
        """Multiple calls with same name should return same tag."""
        result1 = await get_or_create_tag(db_session, "database")
        result2 = await get_or_create_tag(db_session, "database")
        result3 = await get_or_create_tag(db_session, "database")

        assert result1.id == result2.id == result3.id
        assert result1.name == result2.name == result3.name == "database"

        # Only one tag should exist
        all_tags = await get_tags(db_session)
        assert len(all_tags) == 1

    async def test_get_or_create_creates_multiple_different_tags(self, db_session):
        """Should create multiple tags when given different names."""
        tag1 = await get_or_create_tag(db_session, "python")
        tag2 = await get_or_create_tag(db_session, "javascript")
        tag3 = await get_or_create_tag(db_session, "go")

        assert tag1.id != tag2.id != tag3.id
        assert tag1.name == "python"
        assert tag2.name == "javascript"
        assert tag3.name == "go"

        all_tags = await get_tags(db_session)
        assert len(all_tags) == 3


@pytest.mark.asyncio
class TestDeleteTag:
    """Tests for delete_tag() function."""

    async def test_delete_existing_tag(self, db_session):
        """Delete a tag that exists in the database."""
        # Create a tag first
        tag = Tag(name="to-be-deleted")
        created_tag = await create_tag(db_session, tag)

        # Verify it exists
        existing = await get_tags(db_session, id=created_tag.id, first=True)
        assert existing is not None

        # Delete it
        await delete_tag(db_session, existing)

        # Verify it's gone
        deleted = await get_tags(db_session, id=created_tag.id, first=True)
        assert deleted is None

    async def test_delete_tag_removes_from_database(self, db_session):
        """Verify deletion actually removes the tag."""
        # Create multiple tags
        for name in ["tag1", "tag2", "tag3"]:
            tag = Tag(name=name)
            await create_tag(db_session, tag)

        # Verify we have 3 tags
        all_tags = await get_tags(db_session)
        assert len(all_tags) == 3

        # Delete one
        tag_to_delete = await get_tags(db_session, name="tag2", first=True)
        await delete_tag(db_session, tag_to_delete)

        # Verify we now have 2 tags
        remaining_tags = await get_tags(db_session)
        assert len(remaining_tags) == 2

        # Verify the correct tag was deleted
        remaining_names = {tag.name for tag in remaining_tags}
        assert remaining_names == {"tag1", "tag3"}

    async def test_delete_tag_by_name(self, db_session):
        """Delete a tag by retrieving it by name first."""
        tag = Tag(name="delete-by-name")
        await create_tag(db_session, tag)

        # Retrieve by name
        tag_to_delete = await get_tags(db_session, name="delete-by-name", first=True)
        assert tag_to_delete is not None

        # Delete it
        await delete_tag(db_session, tag_to_delete)

        # Verify it's deleted
        deleted = await get_tags(db_session, name="delete-by-name", first=True)
        assert deleted is None

    async def test_delete_multiple_tags_sequentially(self, db_session):
        """Delete multiple tags one by one."""
        # Create 5 tags
        for i in range(5):
            tag = Tag(name=f"delete-seq-{i}")
            await create_tag(db_session, tag)

        # Delete them one by one
        for i in range(5):
            tag_to_delete = await get_tags(db_session, name=f"delete-seq-{i}", first=True)
            await delete_tag(db_session, tag_to_delete)

        # Verify all gone
        remaining = await get_tags(db_session)
        assert len(remaining) == 0


@pytest.mark.asyncio
class TestDeleteAllTags:
    """Tests for delete_all_tags() bulk deletion function."""

    async def test_delete_all_tags_empty_database(self, db_session):
        """Delete all tags when database is empty returns 0."""
        count = await delete_all_tags(db_session)
        assert count == 0

    async def test_delete_all_tags_with_data(self, db_session):
        """Delete all tags returns correct count."""
        # Create 5 tags
        for i in range(5):
            tag = Tag(name=f"bulk-delete-{i}")
            await create_tag(db_session, tag)

        # Verify we have 5 tags
        all_tags = await get_tags(db_session)
        assert len(all_tags) == 5

        # Delete all
        count = await delete_all_tags(db_session)
        assert count == 5

        # Verify database is empty
        remaining = await get_tags(db_session)
        assert len(remaining) == 0

    async def test_delete_all_tags_twice(self, db_session):
        """Calling delete_all twice should work (second call returns 0)."""
        # Create some tags
        for i in range(3):
            tag = Tag(name=f"double-delete-{i}")
            await create_tag(db_session, tag)

        # First delete
        count1 = await delete_all_tags(db_session)
        assert count1 == 3

        # Second delete
        count2 = await delete_all_tags(db_session)
        assert count2 == 0

    async def test_delete_all_tags_large_dataset(self, db_session):
        """Delete all tags works with larger datasets."""
        # Create 50 tags
        for i in range(50):
            tag = Tag(name=f"large-{str(i).zfill(3)}")
            await create_tag(db_session, tag)

        count = await delete_all_tags(db_session)
        assert count == 50

        remaining = await get_tags(db_session)
        assert len(remaining) == 0

    async def test_delete_all_tags_with_various_names(self, db_session):
        """Delete all tags removes tags with various naming patterns."""
        tag_names = [
            "python",
            "JAVASCRIPT",  # Will be stored as "javascript"
            "TypeScript",  # Will be stored as "typescript"
            "go-lang",
            "c++",
            "rust2024",
        ]

        for name in tag_names:
            tag = Tag(name=name)
            await create_tag(db_session, tag)

        count = await delete_all_tags(db_session)
        assert count == 6

        # Verify all gone
        remaining = await get_tags(db_session)
        assert len(remaining) == 0
