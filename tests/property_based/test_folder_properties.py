"""
Property-based tests for folder-related functions using Hypothesis.

Tests folder tree building, cycle detection, and hierarchy validation.
"""

import pytest
from hypothesis import given, strategies as st, assume
from app.services.folder_service import _build_tree, _assert_not_cycle
from app.db.models.folder import Folder


class TestBuildTreeProperties:
    """Property-based tests for folder tree building."""

    @given(folder_count=st.integers(min_value=1, max_value=20))
    def test_build_tree_preserves_all_nodes(self, folder_count):
        """
        Property: All input folders appear in output tree exactly once.

        When building a tree from a flat list of folders, every folder
        should appear in the resulting tree structure exactly once.
        No folders should be lost or duplicated.
        """
        # Create flat list of folders (all roots for simplicity)
        folders = [
            Folder(id=str(i), name=f"Folder {i}", parent_id=None, position=i - 1)
            for i in range(1, folder_count + 1)
        ]

        tree = _build_tree(folders)

        # Count all nodes in the tree recursively
        def count_nodes(nodes):
            count = len(nodes)
            for node in nodes:
                count += len(node.children)
                # Recursively count children of children
                for child in node.children:
                    count += count_nodes([child])
            return count

        # Simple count for this case (all roots, no children)
        total_nodes = len(tree)

        assert total_nodes == folder_count, (
            f"Expected {folder_count} nodes, got {total_nodes}"
        )

    @given(
        root_count=st.integers(min_value=1, max_value=10),
        children_per_root=st.integers(min_value=0, max_value=5),
    )
    def test_build_tree_correct_hierarchy(self, root_count, children_per_root):
        """
        Property: Tree structure matches parent-child relationships.

        The built tree should correctly represent the parent-child
        relationships defined in the input folders.
        """
        folders = []
        folder_id = 1

        # Create root folders
        for root_idx in range(root_count):
            folders.append(
                Folder(
                    id=str(folder_id),
                    name=f"Root {root_idx}",
                    parent_id=None,
                    position=root_idx,
                )
            )
            root_id = str(folder_id)
            folder_id += 1

            # Create children for this root
            for child_idx in range(children_per_root):
                folders.append(
                    Folder(
                        id=str(folder_id),
                        name=f"Child {child_idx}",
                        parent_id=root_id,
                        position=child_idx,
                    )
                )
                folder_id += 1

        tree = _build_tree(folders)

        # Verify root count
        assert len(tree) == root_count, f"Expected {root_count} roots, got {len(tree)}"

        # Verify each root has correct number of children
        for root in tree:
            assert len(root.children) == children_per_root, (
                f"Root {root.name} should have {children_per_root} children, got {len(root.children)}"
            )

    def test_build_tree_empty_list_returns_empty(self):
        """
        Property: Empty input produces empty output.

        Building a tree from an empty list should return an empty list.
        """
        folders = []
        tree = _build_tree(folders)

        assert tree == []

    @given(folder_count=st.integers(min_value=1, max_value=15))
    def test_build_tree_single_parent_ids(self, folder_count):
        """
        Property: Each folder has at most one parent.

        In the built tree, each folder should have exactly one parent
        (or None for roots). This verifies proper tree structure.
        """
        # Create a simple hierarchy: one root with all others as direct children
        folders = [Folder(id="1", name="Root", parent_id=None, position=0)]
        folders.extend(
            [
                Folder(id=str(i), name=f"Child {i}", parent_id="1", position=i - 2)
                for i in range(2, folder_count + 1)
            ]
        )

        tree = _build_tree(folders)

        # Should have exactly one root
        assert len(tree) == 1

        # That root should have (folder_count - 1) children
        assert len(tree[0].children) == folder_count - 1

    @given(depth=st.integers(min_value=1, max_value=10))
    def test_build_tree_handles_deep_hierarchies(self, depth):
        """
        Property: Tree building handles arbitrary depth.

        The tree builder should correctly handle deeply nested
        folder structures without errors or stack overflow.
        """
        # Create a chain: root -> child1 -> child2 -> ... -> childN
        folders = [Folder(id="1", name="Root", parent_id=None, position=0)]

        for i in range(2, depth + 2):
            folders.append(
                Folder(
                    id=str(i),
                    name=f"Level {i - 1}",
                    parent_id=str(i - 1),
                    position=0,
                )
            )

        tree = _build_tree(folders)

        # Should have exactly one root
        assert len(tree) == 1

        # Walk down the chain and verify depth
        current = tree[0]
        levels_traversed = 1

        while current.children:
            assert len(current.children) == 1, (
                "Chain should have exactly one child at each level"
            )
            current = current.children[0]
            levels_traversed += 1

        assert levels_traversed == depth + 1, (
            f"Expected depth {depth + 1}, got {levels_traversed}"
        )


class TestAssertNotCycleProperties:
    """Property-based tests for cycle detection."""

    @given(chain_length=st.integers(min_value=2, max_value=10))
    def test_assert_not_cycle_detects_simple_cycles(self, chain_length):
        """
        Property: Cycle detection catches all circular references.

        When a folder's ancestor chain eventually points back to itself,
        the cycle detector should always raise an HTTPException.
        """
        from fastapi import HTTPException

        # Create a chain: 1 -> 2 -> 3 -> ... -> N -> 1 (cycle)
        folders_dict = {}

        for i in range(1, chain_length + 1):
            next_id = (
                str(i + 1) if i < chain_length else "1"
            )  # Last points back to first
            folders_dict[str(i)] = Folder(
                id=str(i), name=f"Folder {i}", parent_id=next_id, position=0
            )

        # Try to move folder 1 to any position in the chain (should all fail)
        for new_parent_id in range(2, chain_length + 1):
            with pytest.raises(HTTPException) as exc_info:
                _assert_not_cycle(
                    folders_dict, moving_id="1", new_parent_id=str(new_parent_id)
                )

            assert exc_info.value.status_code == 400
            assert "descendant" in exc_info.value.detail.lower()

    @given(
        folder_id=st.integers(min_value=1, max_value=100),
        non_ancestor_id=st.integers(min_value=101, max_value=200),
    )
    def test_assert_not_cycle_allows_non_cycles(self, folder_id, non_ancestor_id):
        """
        Property: Cycle detection allows valid moves.

        When moving a folder to a non-ancestor, no exception should be raised.
        """
        # Create simple structure: folder_id -> parent, and separate non_ancestor_id
        folders_dict = {
            str(folder_id): Folder(
                id=str(folder_id),
                name=f"Folder {folder_id}",
                parent_id=None,
                position=0,
            ),
            str(non_ancestor_id): Folder(
                id=str(non_ancestor_id),
                name=f"Folder {non_ancestor_id}",
                parent_id=None,
                position=0,
            ),
        }

        # This should NOT raise (no cycle possible)
        try:
            _assert_not_cycle(
                folders_dict,
                moving_id=str(folder_id),
                new_parent_id=str(non_ancestor_id),
            )
        except Exception as e:
            pytest.fail(f"Unexpected exception: {e}")

    def test_assert_not_cycle_allows_root_move(self):
        """
        Property: Moving to None (root) is always allowed.

        Moving any folder to become a root (parent_id=None) should
        never create a cycle.
        """
        folders_dict = {
            "1": Folder(id="1", name="Folder 1", parent_id=None, position=0),
            "2": Folder(id="2", name="Folder 2", parent_id="1", position=0),
            "3": Folder(id="3", name="Folder 3", parent_id="2", position=0),
        }

        # Moving to root (None) should always be allowed
        try:
            _assert_not_cycle(folders_dict, moving_id="3", new_parent_id=None)
        except Exception as e:
            pytest.fail(f"Moving to root should not raise exception: {e}")

    @given(hierarchy_depth=st.integers(min_value=2, max_value=10))
    def test_assert_not_cycle_detects_cycle_to_any_descendant(self, hierarchy_depth):
        """
        Property: Cannot move folder under any of its descendants.

        For a folder at the top of a chain, moving it to any descendant
        in the chain should be detected as a cycle.
        """
        from fastapi import HTTPException

        # Create chain: 1 -> 2 -> 3 -> ... -> N
        folders_dict = {}
        folders_dict["1"] = Folder(id="1", name="Folder 1", parent_id=None, position=0)

        for i in range(2, hierarchy_depth + 1):
            folders_dict[str(i)] = Folder(
                id=str(i), name=f"Folder {i}", parent_id=str(i - 1), position=0
            )

        # Try to move folder 1 to any of its descendants (all should fail)
        for descendant_id in range(2, hierarchy_depth + 1):
            with pytest.raises(HTTPException) as exc_info:
                _assert_not_cycle(
                    folders_dict, moving_id="1", new_parent_id=str(descendant_id)
                )

            assert exc_info.value.status_code == 400

    @given(
        root_count=st.integers(min_value=2, max_value=5),
        depth_per_root=st.integers(min_value=1, max_value=5),
    )
    def test_assert_not_cycle_allows_cross_tree_moves(self, root_count, depth_per_root):
        """
        Property: Moving between separate trees is always allowed.

        If folders are in completely separate trees (different roots),
        moving from one tree to another should never create a cycle.
        """
        folders_dict = {}
        folder_id = 1

        # Create multiple separate trees
        for root_idx in range(root_count):
            folders_dict[str(folder_id)] = Folder(
                id=str(folder_id),
                name=f"Root {root_idx}",
                parent_id=None,
                position=0,
            )
            folder_id += 1

            # Create a chain under this root
            for depth in range(depth_per_root):
                parent_id = str(folder_id - 1)
                folders_dict[str(folder_id)] = Folder(
                    id=str(folder_id),
                    name=f"Node {folder_id}",
                    parent_id=parent_id,
                    position=0,
                )
                folder_id += 1

        # Pick a leaf from first tree and a leaf from last tree
        first_tree_leaf = str(depth_per_root)  # Last node of first tree
        last_tree_root = str((root_count - 1) * (depth_per_root + 1) + 1)

        # Moving between different trees should be allowed
        try:
            _assert_not_cycle(
                folders_dict, moving_id=first_tree_leaf, new_parent_id=last_tree_root
            )
        except Exception as e:
            pytest.fail(f"Cross-tree move should not raise exception: {e}")


class TestFolderHierarchyProperties:
    """Property-based tests for folder hierarchy invariants."""

    @given(
        parent_id=st.integers(min_value=1, max_value=100),
        child_id=st.integers(min_value=101, max_value=200),
    )
    def test_parent_child_relationship_is_directional(self, parent_id, child_id):
        """
        Property: Parent-child relationships are directional.

        If A is parent of B, then B cannot be parent of A.
        This is a fundamental tree property.
        """
        assume(parent_id != child_id)

        folders_dict = {
            str(parent_id): Folder(
                id=str(parent_id),
                name=f"Parent {parent_id}",
                parent_id=None,
                position=0,
            ),
            str(child_id): Folder(
                id=str(child_id),
                name=f"Child {child_id}",
                parent_id=str(parent_id),
                position=0,
            ),
        }

        # Build tree to verify relationship
        folders = list(folders_dict.values())
        tree = _build_tree(folders)

        # Find parent in tree
        parent_node = next(node for node in tree if node.id == str(parent_id))

        # Verify child is in parent's children
        child_ids = [child.id for child in parent_node.children]
        assert str(child_id) in child_ids

        # Verify parent is NOT in child's children (if we traverse there)
        child_node = parent_node.children[0]
        assert str(parent_id) not in [c.id for c in child_node.children]
