"""
Unit tests for folder utility functions.

Tests pure functions from app.services.folder_service that handle tree operations:
- Tree building from flat folder lists
- Cycle detection for folder moves
"""

import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException
from app.services.folder_service import _build_tree, _assert_not_cycle


def create_mock_folder(id: str, name: str, parent_id: str | None = None):
    """Helper to create a mock Folder object for testing."""
    folder = MagicMock()
    folder.id = id
    folder.name = name
    folder.parent_id = parent_id
    return folder


class TestBuildTree:
    """Tests for folder tree construction from flat list."""

    @pytest.mark.unit
    def test_single_root_folder(self):
        """Should build tree with single root folder."""
        folders = [create_mock_folder("1", "Root", None)]
        tree = _build_tree(folders)

        assert len(tree) == 1
        assert tree[0].id == "1"
        assert tree[0].name == "Root"
        assert tree[0].parent_id is None
        assert tree[0].children == []

    @pytest.mark.unit
    def test_root_with_one_child(self):
        """Should build tree with root and one child."""
        folders = [
            create_mock_folder("1", "Root", None),
            create_mock_folder("2", "Child", "1"),
        ]
        tree = _build_tree(folders)

        assert len(tree) == 1
        assert tree[0].id == "1"
        assert len(tree[0].children) == 1
        assert tree[0].children[0].id == "2"
        assert tree[0].children[0].name == "Child"

    @pytest.mark.unit
    def test_root_with_multiple_children(self):
        """Should build tree with root and multiple children."""
        folders = [
            create_mock_folder("1", "Root", None),
            create_mock_folder("2", "Child1", "1"),
            create_mock_folder("3", "Child2", "1"),
            create_mock_folder("4", "Child3", "1"),
        ]
        tree = _build_tree(folders)

        assert len(tree) == 1
        assert len(tree[0].children) == 3
        child_names = {c.name for c in tree[0].children}
        assert child_names == {"Child1", "Child2", "Child3"}

    @pytest.mark.unit
    def test_multiple_root_folders(self):
        """Should handle multiple root folders (parent_id=None)."""
        folders = [
            create_mock_folder("1", "Root1", None),
            create_mock_folder("2", "Root2", None),
            create_mock_folder("3", "Root3", None),
        ]
        tree = _build_tree(folders)

        assert len(tree) == 3
        root_names = {r.name for r in tree}
        assert root_names == {"Root1", "Root2", "Root3"}

    @pytest.mark.unit
    def test_two_level_nesting(self):
        """Should handle two levels of nesting."""
        folders = [
            create_mock_folder("1", "Root", None),
            create_mock_folder("2", "Level1", "1"),
            create_mock_folder("3", "Level2", "2"),
        ]
        tree = _build_tree(folders)

        assert len(tree) == 1
        assert tree[0].name == "Root"
        assert len(tree[0].children) == 1
        assert tree[0].children[0].name == "Level1"
        assert len(tree[0].children[0].children) == 1
        assert tree[0].children[0].children[0].name == "Level2"

    @pytest.mark.unit
    def test_three_level_nesting(self):
        """Should handle deep nesting (3+ levels)."""
        folders = [
            create_mock_folder("1", "Root", None),
            create_mock_folder("2", "Level1", "1"),
            create_mock_folder("3", "Level2", "2"),
            create_mock_folder("4", "Level3", "3"),
        ]
        tree = _build_tree(folders)

        level3 = tree[0].children[0].children[0].children[0]
        assert level3.name == "Level3"
        assert level3.id == "4"

    @pytest.mark.unit
    def test_complex_tree_structure(self):
        """Should build complex tree with multiple branches."""
        folders = [
            create_mock_folder("1", "Root", None),
            create_mock_folder("2", "Branch1", "1"),
            create_mock_folder("3", "Branch2", "1"),
            create_mock_folder("4", "Branch1.1", "2"),
            create_mock_folder("5", "Branch1.2", "2"),
            create_mock_folder("6", "Branch2.1", "3"),
        ]
        tree = _build_tree(folders)

        assert len(tree) == 1
        root = tree[0]
        assert len(root.children) == 2

        # Branch1 should have 2 children
        branch1 = next(c for c in root.children if c.name == "Branch1")
        assert len(branch1.children) == 2

        # Branch2 should have 1 child
        branch2 = next(c for c in root.children if c.name == "Branch2")
        assert len(branch2.children) == 1

    @pytest.mark.unit
    def test_empty_folder_list(self):
        """Should return empty list for no folders."""
        tree = _build_tree([])
        assert tree == []

    @pytest.mark.unit
    def test_mixed_roots_and_children(self):
        """Should handle mix of root folders and nested folders."""
        folders = [
            create_mock_folder("1", "Root1", None),
            create_mock_folder("2", "Root2", None),
            create_mock_folder("3", "Root1Child", "1"),
            create_mock_folder("4", "Root2Child", "2"),
        ]
        tree = _build_tree(folders)

        assert len(tree) == 2
        root1 = next(r for r in tree if r.name == "Root1")
        root2 = next(r for r in tree if r.name == "Root2")

        assert len(root1.children) == 1
        assert root1.children[0].name == "Root1Child"
        assert len(root2.children) == 1
        assert root2.children[0].name == "Root2Child"

    @pytest.mark.unit
    def test_unordered_input_list(self):
        """Should handle folders provided in any order."""
        # Children listed before parents
        folders = [
            create_mock_folder("3", "Grandchild", "2"),
            create_mock_folder("1", "Root", None),
            create_mock_folder("2", "Child", "1"),
        ]
        tree = _build_tree(folders)

        assert len(tree) == 1
        assert tree[0].name == "Root"
        assert tree[0].children[0].name == "Child"
        assert tree[0].children[0].children[0].name == "Grandchild"


class TestAssertNotCycle:
    """Tests for cycle detection in folder moves."""

    @pytest.mark.unit
    def test_move_to_self_raises_error(self):
        """Should raise HTTPException when moving folder to itself."""
        folders_by_id = {"1": create_mock_folder("1", "A", None)}

        with pytest.raises(HTTPException) as exc_info:
            _assert_not_cycle(folders_by_id, moving_id="1", new_parent_id="1")

        assert exc_info.value.status_code == 400
        assert "descendant" in exc_info.value.detail.lower()

    @pytest.mark.unit
    def test_move_to_direct_child_raises_error(self):
        """Should raise error when moving folder into its direct child."""
        folders_by_id = {
            "1": create_mock_folder("1", "Parent", None),
            "2": create_mock_folder("2", "Child", "1"),
        }

        with pytest.raises(HTTPException) as exc_info:
            _assert_not_cycle(folders_by_id, moving_id="1", new_parent_id="2")

        assert exc_info.value.status_code == 400

    @pytest.mark.unit
    def test_move_to_grandchild_raises_error(self):
        """Should detect cycles through grandchildren."""
        folders_by_id = {
            "1": create_mock_folder("1", "Grandparent", None),
            "2": create_mock_folder("2", "Parent", "1"),
            "3": create_mock_folder("3", "Child", "2"),
        }

        with pytest.raises(HTTPException) as exc_info:
            _assert_not_cycle(folders_by_id, moving_id="1", new_parent_id="3")

        assert exc_info.value.status_code == 400

    @pytest.mark.unit
    def test_move_to_deep_descendant_raises_error(self):
        """Should detect cycles through deeply nested descendants."""
        folders_by_id = {
            "1": create_mock_folder("1", "Root", None),
            "2": create_mock_folder("2", "Level1", "1"),
            "3": create_mock_folder("3", "Level2", "2"),
            "4": create_mock_folder("4", "Level3", "3"),
            "5": create_mock_folder("5", "Level4", "4"),
        }

        # Try to move Root under Level4 (its great-great-grandchild)
        with pytest.raises(HTTPException):
            _assert_not_cycle(folders_by_id, moving_id="1", new_parent_id="5")

    @pytest.mark.unit
    def test_valid_move_to_sibling(self):
        """Should allow moving to sibling (same parent level)."""
        folders_by_id = {
            "1": create_mock_folder("1", "Root", None),
            "2": create_mock_folder("2", "Child1", "1"),
            "3": create_mock_folder("3", "Child2", "1"),
        }

        # Move Child1 under Child2 (sibling)
        # Should not raise
        _assert_not_cycle(folders_by_id, moving_id="2", new_parent_id="3")

    @pytest.mark.unit
    def test_valid_move_to_none(self):
        """Should allow moving to root (parent_id=None)."""
        folders_by_id = {
            "1": create_mock_folder("1", "Root", None),
            "2": create_mock_folder("2", "Child", "1"),
        }

        # Move Child to root level (parent_id=None)
        # Should not raise
        _assert_not_cycle(folders_by_id, moving_id="2", new_parent_id=None)

    @pytest.mark.unit
    def test_valid_move_to_unrelated_branch(self):
        """Should allow moving to a completely different branch."""
        folders_by_id = {
            "1": create_mock_folder("1", "Branch1", None),
            "2": create_mock_folder("2", "Branch1Child", "1"),
            "3": create_mock_folder("3", "Branch2", None),
            "4": create_mock_folder("4", "Branch2Child", "3"),
        }

        # Move Branch1Child under Branch2Child (different branch)
        # Should not raise
        _assert_not_cycle(folders_by_id, moving_id="2", new_parent_id="4")

    @pytest.mark.unit
    def test_valid_move_to_cousin(self):
        """Should allow moving to cousin folder."""
        folders_by_id = {
            "1": create_mock_folder("1", "Root", None),
            "2": create_mock_folder("2", "ParentA", "1"),
            "3": create_mock_folder("3", "ParentB", "1"),
            "4": create_mock_folder("4", "ChildA", "2"),
            "5": create_mock_folder("5", "ChildB", "3"),
        }

        # Move ChildA under ChildB (cousins)
        # Should not raise
        _assert_not_cycle(folders_by_id, moving_id="4", new_parent_id="5")

    @pytest.mark.unit
    def test_valid_move_up_one_level(self):
        """Should allow moving folder up to its grandparent."""
        folders_by_id = {
            "1": create_mock_folder("1", "Grandparent", None),
            "2": create_mock_folder("2", "Parent", "1"),
            "3": create_mock_folder("3", "Child", "2"),
        }

        # Move Child to Grandparent (skip a level up)
        # Should not raise
        _assert_not_cycle(folders_by_id, moving_id="3", new_parent_id="1")

    @pytest.mark.unit
    def test_move_child_under_another_child(self):
        """Should allow moving one child under another child of same parent."""
        folders_by_id = {
            "1": create_mock_folder("1", "Root", None),
            "2": create_mock_folder("2", "Child1", "1"),
            "3": create_mock_folder("3", "Child2", "1"),
            "4": create_mock_folder("4", "Grandchild1", "2"),
        }

        # Move Grandchild1 from under Child1 to under Child2
        # Should not raise
        _assert_not_cycle(folders_by_id, moving_id="4", new_parent_id="3")

    @pytest.mark.unit
    def test_cycle_detection_with_long_chain(self):
        """Should detect cycle even with very long ancestor chain."""
        # Build a 10-level deep chain
        folders_by_id = {}
        for i in range(1, 11):
            parent_id = str(i - 1) if i > 1 else None
            folders_by_id[str(i)] = create_mock_folder(str(i), f"Level{i}", parent_id)

        # Try to move Level1 (root) under Level10 (deepest descendant)
        with pytest.raises(HTTPException):
            _assert_not_cycle(folders_by_id, moving_id="1", new_parent_id="10")

    @pytest.mark.unit
    def test_move_middle_node_to_descendant(self):
        """Should detect when moving a middle node to its descendant."""
        folders_by_id = {
            "1": create_mock_folder("1", "Root", None),
            "2": create_mock_folder("2", "Middle", "1"),
            "3": create_mock_folder("3", "Child", "2"),
            "4": create_mock_folder("4", "Grandchild", "3"),
        }

        # Try to move Middle under its grandchild
        with pytest.raises(HTTPException):
            _assert_not_cycle(folders_by_id, moving_id="2", new_parent_id="4")
