"""Migrate folder and tag IDs from int to UUID strings

Revision ID: 20260202_migrate_folder_tag_ids_to_uuid
Revises: 20260130_merge_heads
Create Date: 2026-02-02 00:00:00.000000

This migration converts folder and tag IDs from auto-incrementing integers
to UUID strings (String(36)). This makes them consistent with how channels
and videos already use string IDs and provides better scalability.

The migration:
1. Adds temporary UUID columns for folders and tags
2. Generates UUIDs for all existing data
3. Updates foreign key references in dependent tables
4. Drops old integer columns and constraints
5. Renames UUID columns to original names
6. Recreates foreign key constraints with String(36) type
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
import uuid


# revision identifiers, used by Alembic.
revision = "20260202_folder_tag_uuid"
down_revision = "20260130_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Convert folder and tag IDs from int to UUID strings."""
    bind = op.get_bind()

    # ========== STEP 1: Add temporary UUID columns ==========

    # Folders table
    op.add_column("folders", sa.Column("uuid_id", sa.String(36), nullable=True))
    op.add_column("folders", sa.Column("uuid_parent_id", sa.String(36), nullable=True))

    # Tags table
    op.add_column("tags", sa.Column("uuid_id", sa.String(36), nullable=True))

    # Channels table
    op.add_column("channels", sa.Column("uuid_folder_id", sa.String(36), nullable=True))

    # Association tables
    op.add_column(
        "channel_tags", sa.Column("uuid_tag_id", sa.String(36), nullable=True)
    )
    op.add_column("video_tags", sa.Column("uuid_tag_id", sa.String(36), nullable=True))

    # ========== STEP 2: Generate UUIDs for existing data ==========

    # Use Python's uuid module for database-agnostic UUID generation
    # This works with both PostgreSQL and SQLite (for testing)

    # Generate UUIDs for folders
    folder_rows = bind.execute(text("SELECT id FROM folders")).fetchall()
    for row in folder_rows:
        new_uuid = str(uuid.uuid4())
        bind.execute(
            text("UPDATE folders SET uuid_id = :uuid WHERE id = :id"),
            {"uuid": new_uuid, "id": row[0]},
        )

    # Generate UUIDs for tags
    tag_rows = bind.execute(text("SELECT id FROM tags")).fetchall()
    for row in tag_rows:
        new_uuid = str(uuid.uuid4())
        bind.execute(
            text("UPDATE tags SET uuid_id = :uuid WHERE id = :id"),
            {"uuid": new_uuid, "id": row[0]},
        )

    # ========== STEP 3: Update foreign key references ==========

    # Update folders.uuid_parent_id using the mapping from old int to new UUID
    bind.execute(
        text("""
        UPDATE folders AS child
        SET uuid_parent_id = (
            SELECT parent.uuid_id
            FROM folders AS parent
            WHERE parent.id = child.parent_id
        )
        WHERE child.parent_id IS NOT NULL
    """)
    )

    # Update channels.uuid_folder_id
    bind.execute(
        text("""
        UPDATE channels AS c
        SET uuid_folder_id = (
            SELECT f.uuid_id
            FROM folders AS f
            WHERE f.id = c.folder_id
        )
        WHERE c.folder_id IS NOT NULL
    """)
    )

    # Update channel_tags.uuid_tag_id
    bind.execute(
        text("""
        UPDATE channel_tags AS ct
        SET uuid_tag_id = (
            SELECT t.uuid_id
            FROM tags AS t
            WHERE t.id = ct.tag_id
        )
    """)
    )

    # Update video_tags.uuid_tag_id
    bind.execute(
        text("""
        UPDATE video_tags AS vt
        SET uuid_tag_id = (
            SELECT t.uuid_id
            FROM tags AS t
            WHERE t.id = vt.tag_id
        )
    """)
    )

    # ========== STEP 4: Drop old foreign key constraints and columns ==========

    # Drop foreign keys on channels table
    with op.batch_alter_table("channels", schema=None) as batch_op:
        # SQLite doesn't name FK constraints explicitly, so we drop by recreating table
        batch_op.drop_column("folder_id")

    # Drop foreign keys on association tables
    with op.batch_alter_table("channel_tags", schema=None) as batch_op:
        batch_op.drop_column("tag_id")

    with op.batch_alter_table("video_tags", schema=None) as batch_op:
        batch_op.drop_column("tag_id")

    # Drop old integer columns from folders
    with op.batch_alter_table("folders", schema=None) as batch_op:
        batch_op.drop_column("parent_id")
        batch_op.drop_column("id")

    # Drop old integer column from tags
    with op.batch_alter_table("tags", schema=None) as batch_op:
        batch_op.drop_column("id")

    # ========== STEP 5: Rename UUID columns to original names ==========

    # Folders table
    op.alter_column("folders", "uuid_id", new_column_name="id")
    op.alter_column("folders", "uuid_parent_id", new_column_name="parent_id")

    # Tags table
    op.alter_column("tags", "uuid_id", new_column_name="id")

    # Channels table
    op.alter_column("channels", "uuid_folder_id", new_column_name="folder_id")

    # Association tables
    op.alter_column("channel_tags", "uuid_tag_id", new_column_name="tag_id")
    op.alter_column("video_tags", "uuid_tag_id", new_column_name="tag_id")

    # ========== STEP 6: Recreate primary keys and foreign key constraints ==========

    with op.batch_alter_table("folders", schema=None) as batch_op:
        # Set id as NOT NULL and make it primary key
        batch_op.alter_column("id", nullable=False)
        batch_op.create_primary_key("pk_folders", ["id"])

        # Create index on id (it was indexed before)
        batch_op.create_index("ix_folders_id", ["id"])

        # Create foreign key for parent_id (self-referencing)
        batch_op.create_foreign_key(
            "fk_folders_parent_id", "folders", ["parent_id"], ["id"]
        )

    with op.batch_alter_table("tags", schema=None) as batch_op:
        # Set id as NOT NULL and make it primary key
        batch_op.alter_column("id", nullable=False)
        batch_op.create_primary_key("pk_tags", ["id"])

        # Create index on id (it was indexed before)
        batch_op.create_index("ix_tags_id", ["id"])

    with op.batch_alter_table("channels", schema=None) as batch_op:
        # Create foreign key for folder_id
        batch_op.create_foreign_key(
            "fk_channels_folder_id", "folders", ["folder_id"], ["id"]
        )

    with op.batch_alter_table("channel_tags", schema=None) as batch_op:
        # Recreate primary key (tag_id is part of composite PK)
        # Note: channel_id is still part of the PK
        batch_op.create_primary_key("pk_channel_tags", ["channel_id", "tag_id"])

        # Create foreign key for tag_id
        batch_op.create_foreign_key(
            "fk_channel_tags_tag_id", "tags", ["tag_id"], ["id"], ondelete="CASCADE"
        )

    with op.batch_alter_table("video_tags", schema=None) as batch_op:
        # Recreate primary key (tag_id is part of composite PK)
        # Note: video_id is still part of the PK
        batch_op.create_primary_key("pk_video_tags", ["video_id", "tag_id"])

        # Create foreign key for tag_id
        batch_op.create_foreign_key(
            "fk_video_tags_tag_id", "tags", ["tag_id"], ["id"], ondelete="CASCADE"
        )


def downgrade() -> None:
    """Downgrade from UUID strings back to integers.

    WARNING: This is destructive and will lose the UUID values.
    New sequential integer IDs will be generated.
    """
    bind = op.get_bind()

    # ========== STEP 1: Add temporary integer columns ==========

    op.add_column(
        "folders", sa.Column("int_id", sa.Integer(), nullable=True, autoincrement=True)
    )
    op.add_column("folders", sa.Column("int_parent_id", sa.Integer(), nullable=True))
    op.add_column(
        "tags", sa.Column("int_id", sa.Integer(), nullable=True, autoincrement=True)
    )
    op.add_column("channels", sa.Column("int_folder_id", sa.Integer(), nullable=True))
    op.add_column("channel_tags", sa.Column("int_tag_id", sa.Integer(), nullable=True))
    op.add_column("video_tags", sa.Column("int_tag_id", sa.Integer(), nullable=True))

    # ========== STEP 2: Generate sequential integers ==========

    # This is database-specific; for SQLite we need to use row_number
    # For simplicity, we'll assign new sequential IDs

    # Assign new integer IDs to folders (ordered by name for consistency)
    bind.execute(
        text("""
        UPDATE folders
        SET int_id = (
            SELECT COUNT(*)
            FROM folders AS f2
            WHERE f2.name <= folders.name
        )
    """)
    )

    # Assign new integer IDs to tags (ordered by name for consistency)
    bind.execute(
        text("""
        UPDATE tags
        SET int_id = (
            SELECT COUNT(*)
            FROM tags AS t2
            WHERE t2.name <= tags.name
        )
    """)
    )

    # ========== STEP 3: Update foreign key references ==========

    # Update folders.int_parent_id
    bind.execute(
        text("""
        UPDATE folders AS child
        SET int_parent_id = (
            SELECT parent.int_id
            FROM folders AS parent
            WHERE parent.id = child.parent_id
        )
        WHERE child.parent_id IS NOT NULL
    """)
    )

    # Update channels.int_folder_id
    bind.execute(
        text("""
        UPDATE channels AS c
        SET int_folder_id = (
            SELECT f.int_id
            FROM folders AS f
            WHERE f.id = c.folder_id
        )
        WHERE c.folder_id IS NOT NULL
    """)
    )

    # Update channel_tags.int_tag_id
    bind.execute(
        text("""
        UPDATE channel_tags AS ct
        SET int_tag_id = (
            SELECT t.int_id
            FROM tags AS t
            WHERE t.id = ct.tag_id
        )
    """)
    )

    # Update video_tags.int_tag_id
    bind.execute(
        text("""
        UPDATE video_tags AS vt
        SET int_tag_id = (
            SELECT t.int_id
            FROM tags AS t
            WHERE t.id = vt.tag_id
        )
    """)
    )

    # ========== STEP 4: Drop UUID columns and constraints ==========

    with op.batch_alter_table("channels", schema=None) as batch_op:
        batch_op.drop_constraint("fk_channels_folder_id", type_="foreignkey")
        batch_op.drop_column("folder_id")

    with op.batch_alter_table("channel_tags", schema=None) as batch_op:
        batch_op.drop_constraint("fk_channel_tags_tag_id", type_="foreignkey")
        batch_op.drop_constraint("pk_channel_tags", type_="primary")
        batch_op.drop_column("tag_id")

    with op.batch_alter_table("video_tags", schema=None) as batch_op:
        batch_op.drop_constraint("fk_video_tags_tag_id", type_="foreignkey")
        batch_op.drop_constraint("pk_video_tags", type_="primary")
        batch_op.drop_column("tag_id")

    with op.batch_alter_table("folders", schema=None) as batch_op:
        batch_op.drop_constraint("fk_folders_parent_id", type_="foreignkey")
        batch_op.drop_constraint("pk_folders", type_="primary")
        batch_op.drop_index("ix_folders_id")
        batch_op.drop_column("parent_id")
        batch_op.drop_column("id")

    with op.batch_alter_table("tags", schema=None) as batch_op:
        batch_op.drop_constraint("pk_tags", type_="primary")
        batch_op.drop_index("ix_tags_id")
        batch_op.drop_column("id")

    # ========== STEP 5: Rename integer columns back ==========

    op.alter_column("folders", "int_id", new_column_name="id")
    op.alter_column("folders", "int_parent_id", new_column_name="parent_id")
    op.alter_column("tags", "int_id", new_column_name="id")
    op.alter_column("channels", "int_folder_id", new_column_name="folder_id")
    op.alter_column("channel_tags", "int_tag_id", new_column_name="tag_id")
    op.alter_column("video_tags", "int_tag_id", new_column_name="tag_id")

    # ========== STEP 6: Recreate integer PKs and FKs ==========

    with op.batch_alter_table("folders", schema=None) as batch_op:
        batch_op.alter_column("id", nullable=False)
        batch_op.create_primary_key("pk_folders", ["id"])
        batch_op.create_index("ix_folders_id", ["id"])
        batch_op.create_foreign_key(
            "fk_folders_parent_id", "folders", ["parent_id"], ["id"]
        )

    with op.batch_alter_table("tags", schema=None) as batch_op:
        batch_op.alter_column("id", nullable=False)
        batch_op.create_primary_key("pk_tags", ["id"])
        batch_op.create_index("ix_tags_id", ["id"])

    with op.batch_alter_table("channels", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_channels_folder_id", "folders", ["folder_id"], ["id"]
        )

    with op.batch_alter_table("channel_tags", schema=None) as batch_op:
        batch_op.create_primary_key("pk_channel_tags", ["channel_id", "tag_id"])
        batch_op.create_foreign_key(
            "fk_channel_tags_tag_id", "tags", ["tag_id"], ["id"], ondelete="CASCADE"
        )

    with op.batch_alter_table("video_tags", schema=None) as batch_op:
        batch_op.create_primary_key("pk_video_tags", ["video_id", "tag_id"])
        batch_op.create_foreign_key(
            "fk_video_tags_tag_id", "tags", ["tag_id"], ["id"], ondelete="CASCADE"
        )
