"""
Tests for folder service integration.

Tests the folder service functions that interact with the database,
including tree building, folder creation, and folder updates.
"""

import pytest
import pytest_asyncio
from fastapi import HTTPException

from app.services.folder_service import get_tree, create_folder, update_folder
from app.schemas.folder import FolderCreate, FolderUpdate
from app.db.models.folder import Folder


@pytest_asyncio.fixture
async def sample_folders(db_session):
    """Create a sample folder hierarchy for testing."""
    # Create folder hierarchy:
    # root1/
    #   child1/
    #     grandchild1/
    #   child2/
    # root2/
    folders = [
        Folder(id=1, name="root1", parent_id=None),
        Folder(id=2, name="child1", parent_id=1),
        Folder(id=3, name="child2", parent_id=1),
        Folder(id=4, name="grandchild1", parent_id=2),
        Folder(id=5, name="root2", parent_id=None),
    ]

    for folder in folders:
        db_session.add(folder)
    await db_session.commit()

    # Refresh all folders
    for folder in folders:
        await db_session.refresh(folder)

    return folders


@pytest.mark.asyncio
class TestGetTree:
    """Test get_tree function."""

    async def test_get_tree_hierarchical_structure(self, db_session, sample_folders):
        """Test that get_tree returns hierarchical folder structure."""
        tree = await get_tree(db_session)

        # Should have 2 root folders
        assert len(tree) == 2

        # Find root1 and verify its structure
        root1 = next(f for f in tree if f.name == "root1")
        assert len(root1.children) == 2

        # Verify child1 has grandchild1
        child1 = next(c for c in root1.children if c.name == "child1")
        assert len(child1.children) == 1
        assert child1.children[0].name == "grandchild1"

        # Verify child2 has no children
        child2 = next(c for c in root1.children if c.name == "child2")
        assert len(child2.children) == 0

        # Find root2 and verify it has no children
        root2 = next(f for f in tree if f.name == "root2")
        assert len(root2.children) == 0

    async def test_get_tree_empty_database(self, db_session):
        """Test get_tree with no folders returns empty list."""
        tree = await get_tree(db_session)

        assert tree == []


@pytest.mark.asyncio
class TestCreateFolder:
    """Test create_folder function."""

    async def test_create_folder_root_without_parent(self, db_session):
        """Test creating a root folder (parent_id=None)."""
        payload = FolderCreate(name="New Root", parent_id=None)

        folder = await create_folder(payload, db_session)

        assert folder.name == "New Root"
        assert folder.parent_id is None
        assert folder.id is not None

    async def test_create_folder_with_valid_parent(self, db_session, sample_folders):
        """Test creating a folder with a valid parent."""
        # Create child under root1 (id=1)
        payload = FolderCreate(name="New Child", parent_id=1)

        folder = await create_folder(payload, db_session)

        assert folder.name == "New Child"
        assert folder.parent_id == 1
        assert folder.id is not None

    async def test_create_folder_with_nonexistent_parent_raises_404(self, db_session):
        """Test that creating folder with non-existent parent raises 404."""
        payload = FolderCreate(name="Invalid Child", parent_id=99999)

        with pytest.raises(HTTPException) as exc_info:
            await create_folder(payload, db_session)

        assert exc_info.value.status_code == 404
        assert "Parent folder not found" in exc_info.value.detail

    async def test_create_folder_deeply_nested(self, db_session, sample_folders):
        """Test creating a deeply nested folder."""
        # Create under grandchild1 (id=4), which is already 2 levels deep
        payload = FolderCreate(name="Great Grandchild", parent_id=4)

        folder = await create_folder(payload, db_session)

        assert folder.name == "Great Grandchild"
        assert folder.parent_id == 4


@pytest.mark.asyncio
class TestUpdateFolder:
    """Test update_folder function."""

    async def test_update_folder_name_only(self, db_session, sample_folders):
        """Test updating only the folder name."""
        payload = FolderUpdate(name="Renamed Root")

        folder = await update_folder(1, payload, db_session)

        assert folder.id == 1
        assert folder.name == "Renamed Root"
        assert folder.parent_id is None  # Should remain unchanged

    async def test_update_folder_parent_only(self, db_session, sample_folders):
        """Test updating only the folder parent."""
        # Move child2 (id=3) from root1 to root2 (id=5)
        payload = FolderUpdate(parent_id=5)

        folder = await update_folder(3, payload, db_session)

        assert folder.id == 3
        assert folder.name == "child2"  # Name unchanged
        assert folder.parent_id == 5  # Parent changed

    async def test_update_folder_both_name_and_parent(self, db_session, sample_folders):
        """Test updating both name and parent."""
        payload = FolderUpdate(name="Moved and Renamed", parent_id=5)

        folder = await update_folder(3, payload, db_session)

        assert folder.id == 3
        assert folder.name == "Moved and Renamed"
        assert folder.parent_id == 5

    async def test_update_folder_self_parent_raises_400(self, db_session, sample_folders):
        """Test that setting folder as its own parent raises 400."""
        payload = FolderUpdate(parent_id=1)

        with pytest.raises(HTTPException) as exc_info:
            await update_folder(1, payload, db_session)

        assert exc_info.value.status_code == 400
        assert "cannot be its own parent" in exc_info.value.detail.lower()

    async def test_update_folder_nonexistent_parent_raises_404(self, db_session, sample_folders):
        """Test that setting non-existent parent raises 404."""
        payload = FolderUpdate(parent_id=99999)

        with pytest.raises(HTTPException) as exc_info:
            await update_folder(1, payload, db_session)

        assert exc_info.value.status_code == 404
        assert "New parent not found" in exc_info.value.detail

    async def test_update_folder_creates_cycle_raises_400(self, db_session, sample_folders):
        """Test that creating a cycle raises 400."""
        # Try to move root1 (id=1) under its grandchild (id=4)
        # Hierarchy: root1 -> child1 -> grandchild1
        # This would create: grandchild1 -> root1 -> child1 -> grandchild1 (cycle)
        payload = FolderUpdate(parent_id=4)

        with pytest.raises(HTTPException) as exc_info:
            await update_folder(1, payload, db_session)

        assert exc_info.value.status_code == 400
        assert "descendant" in exc_info.value.detail.lower()

    async def test_update_folder_to_direct_child_raises_400(self, db_session, sample_folders):
        """Test that moving folder under its direct child raises 400."""
        # Try to move root1 (id=1) under child1 (id=2)
        payload = FolderUpdate(parent_id=2)

        with pytest.raises(HTTPException) as exc_info:
            await update_folder(1, payload, db_session)

        assert exc_info.value.status_code == 400
        assert "descendant" in exc_info.value.detail.lower()

    async def test_update_nonexistent_folder_raises_404(self, db_session):
        """Test that updating non-existent folder raises 404."""
        payload = FolderUpdate(name="New Name")

        with pytest.raises(HTTPException) as exc_info:
            await update_folder(99999, payload, db_session)

        assert exc_info.value.status_code == 404
        assert "Folder not found" in exc_info.value.detail

    async def test_update_folder_to_sibling(self, db_session, sample_folders):
        """Test moving folder to be under a sibling (valid move)."""
        # Move child2 (id=3) under child1 (id=2) - both are children of root1
        payload = FolderUpdate(parent_id=2)

        folder = await update_folder(3, payload, db_session)

        assert folder.id == 3
        assert folder.parent_id == 2  # Now child of child1

    async def test_update_folder_with_none_parent_changed(self, db_session, sample_folders):
        """Test that parent_id=None in payload changes parent to None."""
        # child1 (id=2) has parent_id=1
        # Passing parent_id=None should change it to None (i.e., make it a root)
        payload = FolderUpdate(parent_id=None, name="Renamed Child")

        folder = await update_folder(2, payload, db_session)

        assert folder.id == 2
        assert folder.name == "Renamed Child"  # Name was updated
        assert folder.parent_id is None  # Parent changed to None (i.e., root folder)