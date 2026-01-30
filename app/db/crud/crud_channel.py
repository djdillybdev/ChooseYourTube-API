from typing import Literal
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.channel import Channel
from .crud_base import (
    base_get,
    base_update,
    _validate_pagination,
    _validate_order_by_field,
)

_UNSET = object()


async def get_channels(
    db: AsyncSession,
    *,
    id: str | list[str] | None = None,
    title: str | None = None,
    handle: str | None = None,
    description: str | None = None,
    is_favorited: bool | None = None,
    folder_id: int | list[int] | None | object = _UNSET,
    # Pagination
    limit: int | None = None,
    offset: int = 0,
    # Ordering
    order_by: str = "title",
    order_direction: Literal["asc", "desc"] = "asc",
    # Return type control
    first: bool = False,
) -> list[Channel] | Channel | None:
    """
    Retrieve channels with flexible filtering, pagination, and ordering.

    Args:
        id: Single channel ID or list of channel IDs for IN clause
        title: Filter by exact title match
        handle: Filter by channel handle
        description: Filter by description
        is_favorited: Filter by favorited status
        folder_id: Single folder ID, list of folder IDs, or None for no folder
        limit: Maximum number of results (None = unlimited)
        offset: Number of results to skip (for pagination)
        order_by: Field to order by
        order_direction: Sort direction ('asc' or 'desc')
        first: If True, return single Channel or None instead of list

    Returns:
        - If first=True: Single Channel instance or None
        - If first=False: List of Channel instances (empty list if no matches)
    """
    _validate_pagination(limit, offset)

    if order_direction not in ("asc", "desc"):
        raise ValueError("order_direction must be 'asc' or 'desc'")

    _validate_order_by_field(Channel, order_by)

    filters = {}
    if id is not None:
        filters["id"] = id
    if title is not None:
        filters["title"] = title
    if handle is not None:
        filters["handle"] = handle
    if description is not None:
        filters["description"] = description
    if is_favorited is not None:
        filters["is_favorited"] = is_favorited
    if folder_id is not _UNSET:
        filters["folder_id"] = folder_id

    return await base_get(
        db,
        Channel,
        filters=filters,
        limit=limit,
        offset=offset,
        order_by=order_by,
        order_direction=order_direction,
        first=first,
    )


async def create_channel(
    db_session: AsyncSession, channel_to_create: Channel
) -> Channel:
    """
    Adds a new Channel instance to the database.
    """
    db_session.add(channel_to_create)
    await db_session.commit()
    await db_session.refresh(channel_to_create)
    return channel_to_create


async def update_channel(db_session: AsyncSession, channel: Channel) -> Channel:
    """
    Updates a channel instance in the database.

    Args:
        db_session: Database session
        channel: The channel instance with modified attributes

    Returns:
        The refreshed channel instance
    """
    return await base_update(db_session, channel)


async def delete_channel(db_session: AsyncSession, channel_to_delete: Channel) -> None:
    """
    Deletes a specific channel instance from the database.
    """
    await db_session.delete(channel_to_delete)
    await db_session.commit()


async def delete_all_channels(db_session: AsyncSession) -> int:
    """
    Deletes all channels from the database and returns the count of deleted rows.
    This is a bulk operation.
    """
    result = await db_session.execute(delete(Channel))
    await db_session.commit()
    return result.rowcount
