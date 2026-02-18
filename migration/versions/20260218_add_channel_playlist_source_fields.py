"""add channel playlist source fields

Revision ID: 20260218_add_channel_playlist_source_fields
Revises: 100843d1b5f2
Create Date: 2026-02-18

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260218_add_channel_playlist_source_fields"
down_revision: Union[str, Sequence[str], None] = "100843d1b5f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "playlists", sa.Column("thumbnail_url", sa.String(length=512), nullable=True)
    )
    op.add_column(
        "playlists",
        sa.Column(
            "source_type",
            sa.String(length=20),
            nullable=False,
            server_default="manual",
        ),
    )
    op.add_column(
        "playlists",
        sa.Column("source_channel_id", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "playlists",
        sa.Column("source_youtube_playlist_id", sa.String(length=48), nullable=True),
    )
    op.add_column(
        "playlists",
        sa.Column(
            "source_is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "playlists",
        sa.Column("source_last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        op.f("ix_playlists_source_channel_id"),
        "playlists",
        ["source_channel_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_playlists_source_youtube_playlist_id"),
        "playlists",
        ["source_youtube_playlist_id"],
        unique=False,
    )

    op.create_unique_constraint(
        "uq_playlist_owner_source_playlist",
        "playlists",
        ["owner_id", "source_type", "source_youtube_playlist_id"],
    )

    op.create_foreign_key(
        "fk_playlists_source_channel",
        "playlists",
        "channels",
        ["owner_id", "source_channel_id"],
        ["owner_id", "id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_playlists_source_channel", "playlists", type_="foreignkey")
    op.drop_constraint("uq_playlist_owner_source_playlist", "playlists", type_="unique")
    op.drop_index(
        op.f("ix_playlists_source_youtube_playlist_id"), table_name="playlists"
    )
    op.drop_index(op.f("ix_playlists_source_channel_id"), table_name="playlists")

    op.drop_column("playlists", "source_last_synced_at")
    op.drop_column("playlists", "source_is_active")
    op.drop_column("playlists", "source_youtube_playlist_id")
    op.drop_column("playlists", "source_channel_id")
    op.drop_column("playlists", "source_type")
    op.drop_column("playlists", "thumbnail_url")
