from typing import Literal, Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.video import Video
from ...schemas.video import VideoCreate
from .crud_base import (
    base_get,
    base_update,
    _validate_pagination,
    _validate_order_by_field,
    _validate_filter_field,
)


def _apply_video_ordering(query, order_column, order_by: str, order_direction: str):
    """Handle special nullslast logic for published_at ordering."""
    if order_direction == "desc":
        if order_by == "published_at":
            return query.order_by(order_column.desc().nullslast())
        else:
            return query.order_by(order_column.desc())
    else:
        return query.order_by(order_column.asc())


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

    # Ensure `yt_tags` is a JSON-serializable list for DB storage.
    # The `Video.yt_tags` column uses JSON storage, so passing plain
    # Python lists works across SQLite and Postgres JSON types.
    for vd in video_dicts:
        if "yt_tags" in vd and vd["yt_tags"] is not None:
            if not isinstance(vd["yt_tags"], (list, tuple)):
                vd["yt_tags"] = [vd["yt_tags"]]

    # Create the bulk insert statement. Use the dialect-specific insert
    # constructor so we can call `on_conflict_do_nothing()` on both
    # Postgres and SQLite engines.
    dialect_name = None
    if getattr(db_session, "bind", None) is not None:
        dialect = getattr(db_session.bind, "dialect", None)
        if dialect is not None:
            dialect_name = getattr(dialect, "name", None)

    if dialect_name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as dialect_insert

        stmt = dialect_insert(Video).values(video_dicts)
        stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
    else:
        # Default to Postgres-style insert which supports ON CONFLICT
        from sqlalchemy.dialects.postgresql import insert as dialect_insert

        stmt = dialect_insert(Video).values(video_dicts)
        stmt = stmt.on_conflict_do_nothing(index_elements=["id"])

    await db_session.execute(stmt)
    await db_session.commit()


async def get_videos(
    db: AsyncSession,
    *,
    # Explicit parameters for common filters
    id: str | list[str] | None = None,
    channel_id: str | list[str] | None = None,
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
    **kwargs: Any,
) -> list[Video] | Video | None:
    """
    Retrieve videos with flexible filtering, pagination, and ordering.

    Args:
        id: Single video ID or list of video IDs for IN clause
        channel_id: Single channel ID or list of channel IDs for IN clause
        is_favorited: Filter by favorited status
        is_short: Filter by YouTube Shorts
        is_watched: Filter by watched status
        limit: Maximum number of results (None = unlimited)
        offset: Number of results to skip (for pagination)
        order_by: Field to order by
        order_direction: Sort direction ('asc' or 'desc')
        first: If True, return single Video or None instead of list
        **kwargs: Additional filter fields

    Returns:
        - If first=True: Single Video instance or None
        - If first=False: List of Video instances (empty list if no matches)
    """
    _validate_pagination(limit, offset)

    if order_direction not in ("asc", "desc"):
        raise ValueError("order_direction must be 'asc' or 'desc'")

    _validate_order_by_field(Video, order_by)

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

    for field_name in filters.keys():
        _validate_filter_field(Video, field_name)

    return await base_get(
        db,
        Video,
        filters=filters,
        limit=limit,
        offset=offset,
        order_by=order_by,
        order_direction=order_direction,
        first=first,
        special_ordering_handler=_apply_video_ordering,
    )


async def count_videos(
    db: AsyncSession,
    *,
    # Explicit parameters for common filters
    id: str | list[str] | None = None,
    channel_id: str | list[str] | None = None,
    is_favorited: bool | None = None,
    is_short: bool | None = None,
    is_watched: bool | None = None,
    # Catch-all for any other Video field
    **kwargs: Any,
) -> int:
    """
    Count videos matching the given filters.

    Args:
        id: Single video ID or list of video IDs for IN clause
        channel_id: Single channel ID or list of channel IDs for IN clause
        is_favorited: Filter by favorited status
        is_short: Filter by YouTube Shorts
        is_watched: Filter by watched status
        **kwargs: Additional filter fields

    Returns:
        Total count of videos matching the filters
    """
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

    for field_name in filters.keys():
        _validate_filter_field(Video, field_name)

    # Build the count query
    query = select(func.count()).select_from(Video)

    # Apply filters
    for field_name, value in filters.items():
        column = getattr(Video, field_name)
        if isinstance(value, list):
            query = query.where(column.in_(value))
        else:
            query = query.where(column == value)

    result = await db.execute(query)
    return result.scalar() or 0


async def update_video(db: AsyncSession, video: Video) -> Video:
    """
    Updates a video instance in the database.

    Args:
        db: Database session
        video: The video instance with modified attributes

    Returns:
        The refreshed video instance
    """
    return await base_update(db, video)


async def delete_video(db_session: AsyncSession, video_to_delete: Video) -> None:
    """
    Deletes a specific video instance from the database.

    Args:
        db_session: Database session
        video_to_delete: The video instance to delete
    """
    await db_session.delete(video_to_delete)
    await db_session.commit()
