"""
Tests for folder write operations (create, delete).

Tests create() and delete() methods from crud_folder.
"""

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from app.db.crud.crud_folder import create_folder, delete_folder, get_folders
from app.db.models.folder import Folder


@pytest.mark.asyncio
class TestCreateFolder:
    """Tests for create() function."""

    async def test_create_folder_without_parent(self, db_session):
        """Create a root folder (no parent)."""
        folder = Folder(name="Root Folder")

        result = await create_folder(db_session, folder)

        assert result.name == "Root Folder"
        assert result.parent_id is None
        assert result.id is not None  # Auto-generated

    async def test_create_folder_with_parent(self, db_session):
        """Create a folder with a parent folder."""
        # Create parent first
        parent = Folder(name="Parent Folder")
        parent = await create_folder(db_session, parent)

        # Create child
        child = Folder(name="Child Folder", parent_id=parent.id)
        result = await create_folder(db_session, child)

        assert result.name == "Child Folder"
        assert result.parent_id == parent.id

    async def test_create_folder_persists_to_database(self, db_session):
        """Verify folder is persisted and retrievable."""
        folder = Folder(name="Persisted Folder")
        created = await create_folder(db_session, folder)

        # Retrieve it
        retrieved = await get_folders(db_session, id=created.id, first=True)
        assert retrieved is not None
        assert retrieved.name == "Persisted Folder"

    async def test_create_multiple_folders_with_same_name(self, db_session):
        """Multiple folders can have the same name."""
        folder1 = Folder(name="Duplicate Name")
        folder2 = Folder(name="Duplicate Name")

        result1 = await create_folder(db_session, folder1)
        result2 = await create_folder(db_session, folder2)

        assert result1.name == "Duplicate Name"
        assert result2.name == "Duplicate Name"
        assert result1.id != result2.id  # Different IDs

    async def test_create_deep_folder_hierarchy(self, db_session):
        """Create a deep folder hierarchy (3+ levels)."""
        # Level 1
        level1 = Folder(name="Level 1")
        level1 = await create_folder(db_session, level1)

        # Level 2
        level2 = Folder(name="Level 2", parent_id=level1.id)
        level2 = await create_folder(db_session, level2)

        # Level 3
        level3 = Folder(name="Level 3", parent_id=level2.id)
        level3 = await create_folder(db_session, level3)

        # Verify hierarchy
        assert level1.parent_id is None
        assert level2.parent_id == level1.id
        assert level3.parent_id == level2.id

    async def test_create_folder_with_non_existent_parent(self, db_session):
        """
        Creating a folder with non-existent parent_id.

        Note: SQLite doesn't enforce foreign key constraints by default.
        """
        folder = Folder(name="Orphan Folder", parent_id=99999)

        # SQLite allows this, PostgreSQL would raise IntegrityError
        result = await create_folder(db_session, folder)
        assert result.parent_id == 99999

    async def test_create_multiple_root_folders(self, db_session):
        """Create multiple folders without parents."""
        folders = [Folder(name=f"Root {i}") for i in range(5)]

        created_folders = []
        for folder in folders:
            result = await create_folder(db_session, folder)
            created_folders.append(result)

        # Verify all are roots
        for folder in created_folders:
            assert folder.parent_id is None

        # Verify all exist
        all_folders = await get_folders(db_session, parent_id=None)
        assert len(all_folders) == 5


@pytest.mark.asyncio
class TestDeleteFolder:
    """Tests for delete() function."""

    async def test_delete_folder_without_children(self, db_session):
        """Delete a folder that has no children."""
        folder = Folder(name="To Delete")
        folder = await create_folder(db_session, folder)

        await delete_folder(db_session, folder)

        # Verify it's gone
        deleted = await get_folders(db_session, id=folder.id, first=True)
        assert deleted is None

    async def test_delete_folder_with_children(self, db_session):
        """
        Delete a parent folder with children.

        Note: Behavior depends on database cascade settings.
        """
        # Create parent
        parent = Folder(name="Parent")
        parent = await create_folder(db_session, parent)

        # Create children
        child1 = Folder(name="Child 1", parent_id=parent.id)
        child2 = Folder(name="Child 2", parent_id=parent.id)
        await create_folder(db_session, child1)
        await create_folder(db_session, child2)

        # Delete parent
        await delete_folder(db_session, parent)

        # Verify parent is gone
        deleted_parent = await get_folders(db_session, id=parent.id, first=True)
        assert deleted_parent is None

    async def test_delete_child_folder_keeps_parent(self, db_session):
        """Deleting a child folder should not affect the parent."""
        # Create parent
        parent = Folder(name="Parent")
        parent = await create_folder(db_session, parent)

        # Create child
        child = Folder(name="Child", parent_id=parent.id)
        child = await create_folder(db_session, child)
        # Delete child
        await delete_folder(db_session, child)

        # Verify parent still exists
        existing_parent = await get_folders(db_session, id=parent.id, first=True)
        assert existing_parent is not None
        assert existing_parent.name == "Parent"

    async def test_delete_multiple_folders(self, db_session):
        """Delete multiple folders."""
        # Create folders
        folders = [Folder(name=f"Folder {i}") for i in range(3)]
        created = []
        for folder in folders:
            result = await create_folder(db_session, folder)
            created.append(result)

        # Delete all
        for folder in created:
            await delete_folder(db_session, folder)

        # Verify all gone
        remaining = await get_folders(db_session)
        assert len(remaining) == 0

    async def test_delete_folder_from_middle_of_hierarchy(self, db_session):
        """Delete a folder in the middle of a hierarchy."""
        # Create hierarchy: Root -> Middle -> Leaf
        root = Folder(name="Root")
        root = await create_folder(db_session, root)

        middle = Folder(name="Middle", parent_id=root.id)
        middle = await create_folder(db_session, middle)

        leaf = Folder(name="Leaf", parent_id=middle.id)
        leaf = await create_folder(db_session, leaf)

        # Delete middle folder
        await delete_folder(db_session, middle)

        # Verify middle is gone
        deleted_middle = await get_folders(db_session, id=middle.id, first=True)
        assert deleted_middle is None

        # Root should still exist
        existing_root = await get_folders(db_session, id=root.id, first=True)
        assert existing_root is not None
