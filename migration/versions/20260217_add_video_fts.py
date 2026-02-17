"""add video full-text search index

Revision ID: 20260217_add_video_fts
Revises: c8d6f904317b
Create Date: 2026-02-17

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260217_add_video_fts"
down_revision: Union[str, Sequence[str], None] = "c8d6f904317b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create functional GIN index for full-text search on videos."""
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_video_search_fts "
            "ON videos USING gin("
            "to_tsvector('english', title || ' ' || coalesce(description, ''))"
            ")"
        )


def downgrade() -> None:
    """Drop the full-text search index."""
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_video_search_fts")
