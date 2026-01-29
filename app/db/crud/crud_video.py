from typing import Literal, Any
from sqlalchemy import select, asc, desc
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect
from ..models.video import Video
from ...schemas.video import VideoCreate


# Helper functions for get_videos()

def _get_valid_fields(model_class) -> set[str]:
    """Extract valid column names from SQLAlchemy model."""
    mapper = inspect(model_class)
    return {col.key for col in mapper.columns}


def _validate_filter_field(model_class, field_name: str) -> None:
    """Validate that a field name exists on the model."""
    valid_fields = _get_valid_fields(model_class)
    if field_name not in valid_fields:
        raise ValueError(
            f"Invalid filter field '{field_name}'. "
            f"Valid fields: {', '.join(sorted(valid_fields))}"
        )


def _validate_order_by_field(model_class, field_name: str) -> None:
    """Validate that an order_by field exists on the model."""
    valid_fields = _get_valid_fields(model_class)
    if field_name not in valid_fields:
        raise ValueError(
            f"Invalid order_by field '{field_name}'. "
            f"Valid fields: {', '.join(sorted(valid_fields))}"
        )


def _validate_pagination(limit: int | None, offset: int) -> None:
    """Validate pagination parameters."""
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative")
    if offset < 0:
        raise ValueError("offset must be non-negative")


async def create_videos_bulk(
    db_session: AsyncSession, videos_to_create: list[VideoCreate]
) -> None:
    """
    Bulk inserts video records using PostgreSQL's "ON CONFLICT DO NOTHING".
    This is highly efficient for adding many videos at once and safely
    handles duplicates without raising an error.
    """
    if not videos_to_create:
        return

    # Convert Pydantic models to dictionaries for the insert statement
    video_dicts = [video.model_dump() for video in videos_to_create]

    # Create the bulk insert statement
    stmt = insert(Video).values(video_dicts)

    # Add the ON CONFLICT clause to ignore duplicates based on the primary key (id)
    stmt = stmt.on_conflict_do_nothing(index_elements=["id"])

    await db_session.execute(stmt)
    await db_session.commit()


async def get_video_by_id(db_session: AsyncSession, video_id: str) -> Video | None:
    res = await db_session.execute(select(Video).where(Video.id == video_id))
    return res.scalars().first()


async def get_all_videos(
    db_session: AsyncSession, limit: int = 50, offset: int = 0
) -> list[Video]:
    stmt = (
        select(Video)
        .order_by(Video.published_at.desc().nullslast(), Video.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    res = await db_session.execute(stmt)
    return list(res.scalars().all())


async def get_videos_by_channel_id(
    db_session: AsyncSession, channel_id: str, limit: int = 50, offset: int = 0
) -> list[Video]:
    stmt = (
        select(Video)
        .where(Video.channel_id == channel_id)
        .order_by(Video.published_at.desc().nullslast(), Video.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    res = await db_session.execute(stmt)
    return list(res.scalars().all())


async def get_videos(
    db: AsyncSession,
    *,
    # Explicit parameters for common filters (IDE autocomplete)
    id: str | None = None,
    channel_id: str | None = None,
    is_favorited: bool | None = None,
    is_short: bool | None = None,
    is_watched: bool | None = None,
    # Pagination
    limit: int | None = None,
    offset: int = 0,
    # Ordering
    order_by: str = "published_at",
    order_direction: Literal["asc", "desc"] = "desc",
    # Return type control
    first: bool = False,
    # Catch-all for any other Video field
    **kwargs: Any
) -> list[Video] | Video | None:
    """
    Flexible query method for videos with dynamic filtering.

    Args:
        db: Database session
        id: Filter by video ID
        channel_id: Filter by channel ID
        is_favorited: Filter by favorite status
        is_short: Filter by YouTube Short status
        is_watched: Filter by watched status
        limit: Maximum number of results (None = unlimited)
        offset: Number of results to skip (for pagination)
        order_by: Field to order by (must be valid Video column)
        order_direction: Sort direction ('asc' or 'desc')
        first: If True, return single Video | None instead of list
        **kwargs: Additional filter fields (validated against Video model)

    Returns:
        - If first=True: Single Video object or None
        - If first=False: List of Video objects (empty list if no matches)

    Raises:
        ValueError: If invalid field name in filters or order_by
        ValueError: If limit/offset negative
        ValueError: If order_direction not 'asc' or 'desc'

    Examples:
        # Get single video by ID
        video = await get_videos(db, id="abc123", first=True)

        # Get all unwatched shorts from a channel
        videos = await get_videos(
            db,
            channel_id="UC123",
            is_short=True,
            is_watched=False,
            limit=50
        )

        # Get favorited videos, oldest first
        videos = await get_videos(
            db,
            is_favorited=True,
            order_by="published_at",
            order_direction="asc"
        )
    """
    # 1. Validate parameters
    _validate_pagination(limit, offset)

    if order_direction not in ("asc", "desc"):
        raise ValueError("order_direction must be 'asc' or 'desc'")

    _validate_order_by_field(Video, order_by)

    # 2. Merge explicit params with kwargs to build filters dict
    filters = {}
    if id is not None:
        filters["id"] = id
    if channel_id is not None:
        filters["channel_id"] = channel_id
    if is_favorited is not None:
        filters["is_favorited"] = is_favorited
    if is_short is not None:
        filters["is_short"] = is_short
    if is_watched is not None:
        filters["is_watched"] = is_watched

    # Add any additional kwargs
    for key, value in kwargs.items():
        if value is not None:
            filters[key] = value

    # 3. Validate all filter fields
    for field_name in filters.keys():
        _validate_filter_field(Video, field_name)

    # 4. Build base query
    query = select(Video)

    # 5. Apply filters
    for field_name, value in filters.items():
        column = getattr(Video, field_name)
        if value is not None:
            query = query.where(column == value)

    # 6. Apply ordering
    order_column = getattr(Video, order_by)
    if order_direction == "desc":
        # Use nullslast for published_at DESC ordering
        if order_by == "published_at":
            query = query.order_by(order_column.desc().nullslast())
        else:
            query = query.order_by(order_column.desc())
    else:
        query = query.order_by(order_column.asc())

    # 7. Apply pagination
    if limit is not None:
        query = query.limit(limit)
    query = query.offset(offset)

    # 8. Execute query
    result = await db.execute(query)

    # 9. Return based on 'first' flag
    if first:
        return result.scalars().first()
    else:
        return list(result.scalars().all())
