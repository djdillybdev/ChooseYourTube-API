from typing import Literal
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.folder import Folder
from .crud_base import base_get, base_update, _validate_pagination, _validate_order_by_field

_UNSET = object()

async def get_folders(
        db: AsyncSession,
        *,
        # model params
        id: int | None = None,
        name: str | None = None,
        parent_id: int | None | object = _UNSET,
        # Pagination
        limit: int | None = 100,
        offset: int = 0,
        # Ordering
        order_by: str = "name",
        order_direction: Literal["asc", "desc"] = "asc",
        # Return type control
        first: bool = False,
        ) -> list[Folder] | Folder | None:

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
        db, Folder,
        filters=filters,
        limit=limit,
        offset=offset,
        order_by=order_by,
        order_direction=order_direction,
        first=first
    )



async def create(db: AsyncSession, folder: Folder) -> Folder:
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return folder


async def update(db: AsyncSession, folder: Folder) -> Folder:
    """
    Updates a folder instance in the database.

    Args:
        db: Database session
        folder: The folder instance with modified attributes

    Returns:
        The refreshed folder instance
    """
    return await base_update(db, folder)


async def delete(db: AsyncSession, folder: Folder) -> None:
    await db.delete(folder)
    await db.commit()
