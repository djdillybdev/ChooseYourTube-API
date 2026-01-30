from typing import Literal, Any
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.video import Video
from ...schemas.video import VideoCreate
from .crud_base import base_get, base_update, _validate_pagination, _validate_order_by_field, _validate_filter_field


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

    # Create the bulk insert statement
    stmt = insert(Video).values(video_dicts)

    # Add the ON CONFLICT clause to ignore duplicates based on the primary key (id)
    stmt = stmt.on_conflict_do_nothing(index_elements=["id"])

    await db_session.execute(stmt)
    await db_session.commit()


async def get_videos(
    db: AsyncSession,
    *,
    # Explicit parameters for common filters
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
        db, Video,
        filters=filters,
        limit=limit,
        offset=offset,
        order_by=order_by,
        order_direction=order_direction,
        first=first,
        special_ordering_handler=_apply_video_ordering
    )


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
