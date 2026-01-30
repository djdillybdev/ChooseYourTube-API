"""Convert videos.yt_tags from text[] to json

Revision ID: 20260130_convert_yt_tags_to_json
Revises: a67d3ea6e7b3
Create Date: 2026-01-30 00:00:00.000000

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260130_convert_yt_tags_to_json"
down_revision = "a67d3ea6e7b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Convert `yt_tags` column from PostgreSQL `text[]` to `json`.

    This uses `to_json(yt_tags)` to safely convert existing array values
    into JSON arrays. The migration is a no-op on non-Postgres backends.
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    # Ensure default and not-null are set to JSON array
    # 0) Drop any existing default which may be incompatible with json
    op.execute("ALTER TABLE videos ALTER COLUMN yt_tags DROP DEFAULT")

    # 1) Convert existing data from text[] to json using to_json()
    op.execute(
        "ALTER TABLE videos ALTER COLUMN yt_tags TYPE json USING to_json(yt_tags)"
    )

    # 2) Set server default to JSON empty array
    op.execute("ALTER TABLE videos ALTER COLUMN yt_tags SET DEFAULT '[]'::json")

    # 3) Ensure NOT NULL (matches model expectation)
    op.execute("ALTER TABLE videos ALTER COLUMN yt_tags SET NOT NULL")


def downgrade() -> None:
    """Downgrade is not implemented automatically.

    Converting JSON back to a Postgres text[] may be lossy in some edge cases
    and requires careful handling. If you need a downgrade implement it
    manually for your environment (e.g. using json_array_elements_text).
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    raise NotImplementedError(
        "Downgrade not implemented: manual conversion from json to text[] required"
    )
