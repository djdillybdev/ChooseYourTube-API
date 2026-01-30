"""Merge divergent heads: 7f3cd234e397 and 20260130_convert_yt_tags_to_json

Revision ID: 20260130_merge_heads
Revises: 7f3cd234e397, 20260130_convert_yt_tags_to_json
Create Date: 2026-01-30 00:05:00.000000

This is a no-op merge migration that unifies multiple heads so Alembic
can upgrade to a single linear head. It intentionally performs no schema
changes.
"""

from alembic import op
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "20260130_merge_heads"
down_revision: Union[str, Sequence[str], None] = (
    "7f3cd234e397",
    "20260130_convert_yt_tags_to_json",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No schema changes; this migration simply merges two heads.
    pass


def downgrade() -> None:
    # Downgrade would reintroduce branching; not supported automatically.
    pass
