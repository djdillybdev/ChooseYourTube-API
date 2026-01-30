"""add tag relationships to channels and videos

Revision ID: 7f3cd234e397
Revises: a67d3ea6e7b3
Create Date: 2026-01-29 20:59:30.382965

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7f3cd234e397"
down_revision: Union[str, Sequence[str], None] = "a67d3ea6e7b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Add unique constraint and index to tags.name for case-insensitive uniqueness
    op.create_unique_constraint("uq_tags_name", "tags", ["name"])
    op.create_index("ix_tags_name", "tags", ["name"], unique=True)

    # 2. Create channel_tags junction table
    op.create_table(
        "channel_tags",
        sa.Column("channel_id", sa.String(32), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("channel_id", "tag_id"),
    )
    # Index on tag_id for reverse lookups (finding channels by tag)
    op.create_index("ix_channel_tags_tag_id", "channel_tags", ["tag_id"])

    # 3. Create video_tags junction table
    op.create_table(
        "video_tags",
        sa.Column("video_id", sa.String(16), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("video_id", "tag_id"),
    )
    # Index on tag_id for reverse lookups (finding videos by tag)
    op.create_index("ix_video_tags_tag_id", "video_tags", ["tag_id"])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables in reverse order
    op.drop_index("ix_video_tags_tag_id", "video_tags")
    op.drop_table("video_tags")

    op.drop_index("ix_channel_tags_tag_id", "channel_tags")
    op.drop_table("channel_tags")

    # Remove unique constraint and index from tags
    op.drop_index("ix_tags_name", "tags")
    op.drop_constraint("uq_tags_name", "tags", type_="unique")
