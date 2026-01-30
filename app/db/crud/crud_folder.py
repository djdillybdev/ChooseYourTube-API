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
