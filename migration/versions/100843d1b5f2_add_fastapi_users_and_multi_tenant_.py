"""add fastapi users and multi-tenant ownership

Revision ID: 100843d1b5f2
Revises: 04987b21232e
Create Date: 2026-02-18 00:38:39.536615

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import fastapi_users_db_sqlalchemy


# revision identifiers, used by Alembic.
revision: str = '100843d1b5f2'
down_revision: Union[str, Sequence[str], None] = '04987b21232e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_pk(table_name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    pk_name = inspector.get_pk_constraint(table_name).get("name")
    if pk_name:
        op.drop_constraint(pk_name, table_name, type_="primary")


def _drop_fk(table_name: str, constrained_columns: list[str], referred_table: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(table_name):
        if (
            fk.get("referred_table") == referred_table
            and fk.get("constrained_columns") == constrained_columns
            and fk.get("name")
        ):
            op.drop_constraint(fk["name"], table_name, type_="foreignkey")
            return


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("id", fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=1024), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.add_column("channels", sa.Column("owner_id", sa.String(length=36), nullable=True))
    op.add_column("videos", sa.Column("owner_id", sa.String(length=36), nullable=True))
    op.add_column("folders", sa.Column("owner_id", sa.String(length=36), nullable=True))
    op.add_column("tags", sa.Column("owner_id", sa.String(length=36), nullable=True))
    op.add_column("playlists", sa.Column("owner_id", sa.String(length=36), nullable=True))
    op.add_column(
        "channel_tags",
        sa.Column(
            "owner_id",
            sa.String(length=36),
            server_default="test-user",
            nullable=False,
        ),
    )
    op.add_column(
        "video_tags",
        sa.Column(
            "owner_id",
            sa.String(length=36),
            server_default="test-user",
            nullable=False,
        ),
    )
    op.add_column(
        "playlist_videos",
        sa.Column(
            "owner_id",
            sa.String(length=36),
            server_default="test-user",
            nullable=False,
        ),
    )

    op.execute("UPDATE channels SET owner_id = 'test-user' WHERE owner_id IS NULL")
    op.execute("UPDATE videos SET owner_id = 'test-user' WHERE owner_id IS NULL")
    op.execute("UPDATE folders SET owner_id = 'test-user' WHERE owner_id IS NULL")
    op.execute("UPDATE tags SET owner_id = 'test-user' WHERE owner_id IS NULL")
    op.execute("UPDATE playlists SET owner_id = 'test-user' WHERE owner_id IS NULL")
    op.execute(
        """
        UPDATE channel_tags ct
        SET owner_id = c.owner_id
        FROM channels c
        WHERE ct.channel_id = c.id AND ct.owner_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE video_tags vt
        SET owner_id = v.owner_id
        FROM videos v
        WHERE vt.video_id = v.id AND vt.owner_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE playlist_videos pv
        SET owner_id = p.owner_id
        FROM playlists p
        WHERE pv.playlist_id = p.id AND pv.owner_id IS NULL
        """
    )

    op.alter_column("channels", "owner_id", nullable=False)
    op.alter_column("videos", "owner_id", nullable=False)
    op.alter_column("folders", "owner_id", nullable=False)
    op.alter_column("tags", "owner_id", nullable=False)
    op.alter_column("playlists", "owner_id", nullable=False)

    _drop_fk("videos", ["channel_id"], "channels")
    _drop_fk("channel_tags", ["channel_id"], "channels")
    _drop_fk("video_tags", ["video_id"], "videos")
    _drop_fk("playlist_videos", ["video_id"], "videos")

    _drop_pk("channels")
    _drop_pk("videos")
    _drop_pk("channel_tags")
    _drop_pk("video_tags")
    _drop_pk("playlist_videos")

    op.create_primary_key("pk_channels", "channels", ["owner_id", "id"])
    op.create_primary_key("pk_videos", "videos", ["owner_id", "id"])
    op.create_primary_key("pk_channel_tags", "channel_tags", ["owner_id", "channel_id", "tag_id"])
    op.create_primary_key("pk_video_tags", "video_tags", ["owner_id", "video_id", "tag_id"])
    op.create_primary_key(
        "pk_playlist_videos", "playlist_videos", ["owner_id", "playlist_id", "video_id"]
    )

    op.create_foreign_key(
        None,
        "videos",
        "channels",
        ["owner_id", "channel_id"],
        ["owner_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        None,
        "channel_tags",
        "channels",
        ["owner_id", "channel_id"],
        ["owner_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        None,
        "video_tags",
        "videos",
        ["owner_id", "video_id"],
        ["owner_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        None,
        "playlist_videos",
        "videos",
        ["owner_id", "video_id"],
        ["owner_id", "id"],
        ondelete="CASCADE",
    )

    op.drop_index(op.f("ix_channels_handle"), table_name="channels")
    op.create_index(op.f("ix_channels_handle"), "channels", ["handle"], unique=False)
    op.create_index(op.f("ix_channels_owner_id"), "channels", ["owner_id"], unique=False)
    op.create_unique_constraint("uq_channel_owner_handle", "channels", ["owner_id", "handle"])
    op.create_index(op.f("ix_folders_owner_id"), "folders", ["owner_id"], unique=False)
    op.create_index(op.f("ix_playlists_owner_id"), "playlists", ["owner_id"], unique=False)
    op.drop_index(op.f("ix_tags_name"), table_name="tags")
    op.create_index(op.f("ix_tags_name"), "tags", ["name"], unique=False)
    op.create_index(op.f("ix_tags_owner_id"), "tags", ["owner_id"], unique=False)
    op.create_unique_constraint("uq_tag_owner_name", "tags", ["owner_id", "name"])
    op.drop_index(op.f("ix_video_channel_published"), table_name="videos")
    op.create_index(
        "ix_video_channel_published",
        "videos",
        ["owner_id", "channel_id", "published_at"],
        unique=False,
    )
    op.create_index(op.f("ix_videos_owner_id"), "videos", ["owner_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    _drop_fk("videos", ["owner_id", "channel_id"], "channels")
    _drop_fk("channel_tags", ["owner_id", "channel_id"], "channels")
    _drop_fk("video_tags", ["owner_id", "video_id"], "videos")
    _drop_fk("playlist_videos", ["owner_id", "video_id"], "videos")

    op.drop_index(op.f("ix_videos_owner_id"), table_name="videos")
    op.drop_index("ix_video_channel_published", table_name="videos")
    op.drop_constraint("uq_tag_owner_name", "tags", type_="unique")
    op.drop_index(op.f("ix_tags_owner_id"), table_name="tags")
    op.drop_index(op.f("ix_playlists_owner_id"), table_name="playlists")
    op.drop_index(op.f("ix_folders_owner_id"), table_name="folders")
    op.drop_constraint("uq_channel_owner_handle", "channels", type_="unique")
    op.drop_index(op.f("ix_channels_owner_id"), table_name="channels")

    _drop_pk("playlist_videos")
    _drop_pk("video_tags")
    _drop_pk("channel_tags")
    _drop_pk("videos")
    _drop_pk("channels")

    op.create_primary_key("channels_pkey", "channels", ["id"])
    op.create_primary_key("videos_pkey", "videos", ["id"])
    op.create_primary_key("pk_channel_tags", "channel_tags", ["channel_id", "tag_id"])
    op.create_primary_key("pk_video_tags", "video_tags", ["video_id", "tag_id"])
    op.create_primary_key("playlist_videos_pkey", "playlist_videos", ["playlist_id", "video_id"])

    op.create_foreign_key(
        "videos_channel_id_fkey",
        "videos",
        "channels",
        ["channel_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "channel_tags_channel_id_fkey",
        "channel_tags",
        "channels",
        ["channel_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "video_tags_video_id_fkey",
        "video_tags",
        "videos",
        ["video_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "playlist_videos_video_id_fkey",
        "playlist_videos",
        "videos",
        ["video_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_index(op.f("ix_channels_handle"), table_name="channels")
    op.create_index(op.f("ix_channels_handle"), "channels", ["handle"], unique=True)
    op.drop_index(op.f("ix_tags_name"), table_name="tags")
    op.create_index(op.f("ix_tags_name"), "tags", ["name"], unique=True)
    op.create_index(op.f("ix_video_channel_published"), "videos", ["channel_id", "published_at"], unique=False)

    op.drop_column("playlist_videos", "owner_id")
    op.drop_column("video_tags", "owner_id")
    op.drop_column("channel_tags", "owner_id")
    op.drop_column("playlists", "owner_id")
    op.drop_column("tags", "owner_id")
    op.drop_column("folders", "owner_id")
    op.drop_column("videos", "owner_id")
    op.drop_column("channels", "owner_id")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
