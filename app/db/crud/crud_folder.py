from typing import Literal
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.folder import Folder
from .crud_base import (
    base_get,
    base_update,
    _validate_pagination,
    _validate_order_by_field,
)

_UNSET = object()


async def get_folders(
    db: AsyncSession,
    *,
    # model params
    id: str | list[str] | None = None,
    name: str | None = None,
    parent_id: str | list[str] | None | object = _UNSET,
    # Pagination
    limit: int | None = 100,
    offset: int = 0,
    # Ordering
    order_by: str = "name",
    order_direction: Literal["asc", "desc"] = "asc",
    # Return type control
    first: bool = False,
) -> list[Folder] | Folder | None:
    """
    Retrieve folders with flexible filtering, pagination, and ordering.

    Args:
        id: Single folder ID or list of folder IDs for IN clause
        name: Filter by exact folder name
        parent_id: Single parent folder ID, list of parent IDs, or None for root folders
        limit: Maximum number of results (None = unlimited, default 100)
        offset: Number of results to skip (for pagination)
        order_by: Field to order by
        order_direction: Sort direction ('asc' or 'desc')
        first: If True, return single Folder or None instead of list

    Returns:
        - If first=True: Single Folder instance or None
        - If first=False: List of Folder instances (empty list if no matches)
    """
    _validate_pagination(limit, offset)

    if order_direction not in ("asc", "desc"):
        raise ValueError("order_direction must be 'asc' or 'desc'")

    _validate_order_by_field(Folder, order_by)

    filters = {}
    if id is not None:
        filters["id"] = id
    if name is not None:
        filters["name"] = name
    if parent_id is not _UNSET:
        filters["parent_id"] = parent_id

    return await base_get(
        db,
        Folder,
        filters=filters,
        limit=limit,
        offset=offset,
        order_by=order_by,
        order_direction=order_direction,
        first=first,
    )


async def create_folder(db_session: AsyncSession, folder_to_create: Folder) -> Folder:
    """
    Creates a new folder in the database.

    Args:
        db_session: Database session
        folder_to_create: Folder instance to create

    Returns:
        The created and refreshed Folder instance
    """
    db_session.add(folder_to_create)
    await db_session.commit()
    await db_session.refresh(folder_to_create)
    return folder_to_create


async def get_max_position(db: AsyncSession, parent_id: str | None) -> int:
    """Return the max position for siblings under the given parent, or -1 if empty."""
    query = select(func.coalesce(func.max(Folder.position), -1))
    if parent_id is None:
        query = query.where(Folder.parent_id.is_(None))
    else:
        query = query.where(Folder.parent_id == parent_id)
    result = await db.execute(query)
    return result.scalar()


async def shift_positions_for_insert(
    db: AsyncSession, parent_id: str | None, start_position: int
) -> None:
    """Shift sibling positions down to make room for an insertion."""
    if parent_id is None:
        parent_filter = Folder.parent_id.is_(None)
    else:
        parent_filter = Folder.parent_id == parent_id

    await db.execute(
        update(Folder)
        .where(parent_filter, Folder.position >= start_position)
        .values(position=Folder.position + 1)
    )


async def shift_positions_after_removal(
    db: AsyncSession, parent_id: str | None, removed_position: int
) -> None:
    """Compact sibling positions after a removal."""
    if parent_id is None:
        parent_filter = Folder.parent_id.is_(None)
    else:
        parent_filter = Folder.parent_id == parent_id

    await db.execute(
        update(Folder)
        .where(parent_filter, Folder.position > removed_position)
        .values(position=Folder.position - 1)
    )


async def shift_positions_for_move(
    db: AsyncSession,
    parent_id: str | None,
    old_position: int,
    new_position: int,
) -> None:
    """Shift sibling positions to accommodate a move within the same parent."""
    if old_position == new_position:
        return

    if parent_id is None:
        parent_filter = Folder.parent_id.is_(None)
    else:
        parent_filter = Folder.parent_id == parent_id

    if old_position < new_position:
        await db.execute(
            update(Folder)
            .where(
                parent_filter,
                Folder.position > old_position,
                Folder.position <= new_position,
            )
            .values(position=Folder.position - 1)
        )
    else:
        await db.execute(
            update(Folder)
            .where(
                parent_filter,
                Folder.position >= new_position,
                Folder.position < old_position,
            )
            .values(position=Folder.position + 1)
        )


async def update_folder(db_session: AsyncSession, folder: Folder) -> Folder:
    """
    Updates a folder instance in the database.

    Args:
        db_session: Database session
        folder: The folder instance with modified attributes

    Returns:
        The refreshed folder instance
    """
    return await base_update(db_session, folder)


async def delete_folder(db_session: AsyncSession, folder_to_delete: Folder) -> None:
    """
    Deletes a specific folder instance from the database.

    Args:
        db_session: Database session
        folder_to_delete: The folder instance to delete
    """
    await db_session.delete(folder_to_delete)
    await db_session.commit()
