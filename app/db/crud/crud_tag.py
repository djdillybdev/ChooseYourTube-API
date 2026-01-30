from typing import Literal
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.tag import Tag
from .crud_base import (
    base_get,
    base_update,
    _validate_pagination,
    _validate_order_by_field,
)


async def get_tags(
    db: AsyncSession,
    *,
    id: int | None = None,
    name: str | None = None,
    # Pagination
    limit: int | None = None,
    offset: int = 0,
    # Ordering
    order_by: str = "name",
    order_direction: Literal["asc", "desc"] = "asc",
    # Return type control
    first: bool = False,
) -> list[Tag] | Tag | None:
    """
    Retrieve tags with flexible filtering, pagination, and ordering.

    Args:
        db: Database session
        id: Filter by tag ID
        name: Filter by tag name (case-insensitive)
        limit: Maximum number of results
        offset: Number of results to skip
        order_by: Field to order by (name, created_at, id)
        order_direction: Sort direction ('asc' or 'desc')
        first: If True, return single Tag or None instead of list

    Returns:
        - If first=True: Single Tag instance or None
        - If first=False: List of Tag instances (empty list if no matches)
    """
    _validate_pagination(limit, offset)

    if order_direction not in ("asc", "desc"):
        raise ValueError("order_direction must be 'asc' or 'desc'")

    _validate_order_by_field(Tag, order_by)

    filters = {}
    if id is not None:
        filters["id"] = id
    if name is not None:
        # Normalize to lowercase for case-insensitive search
        filters["name"] = name.lower()

    return await base_get(
        db,
        Tag,
        filters=filters,
        limit=limit,
        offset=offset,
        order_by=order_by,
        order_direction=order_direction,
        first=first,
    )


async def create_tag(db_session: AsyncSession, tag_to_create: Tag) -> Tag:
    """
    Adds a new Tag instance to the database.
    Tag name will be normalized to lowercase automatically by the Tag model.

    Args:
        db_session: Database session
        tag_to_create: Tag instance to create

    Returns:
        The created Tag instance
    """
    db_session.add(tag_to_create)
    await db_session.commit()
    await db_session.refresh(tag_to_create)
    return tag_to_create


async def get_or_create_tag(db_session: AsyncSession, name: str) -> Tag:
    """
    Get an existing tag by name, or create it if it doesn't exist.
    This is idempotent - calling it multiple times with the same name returns the same tag.

    Args:
        db_session: Database session
        name: Tag name (will be normalized to lowercase)

    Returns:
        The existing or newly created Tag instance
    """
    # Try to get existing tag (name will be normalized to lowercase in get_tags)
    existing_tag = await get_tags(db_session, name=name, first=True)

    if existing_tag:
        return existing_tag

    # Create new tag if it doesn't exist
    new_tag = Tag(name=name)
    return await create_tag(db_session, new_tag)


async def delete_tag(db_session: AsyncSession, tag: Tag) -> Tag:
    """
    Deletes a tag from the database.

    Args:
        db_session: Database session
        tag: Tag instance to delete

    Returns:
        The deleted Tag instance
    """
    await db_session.delete(tag)
    await db_session.commit()
    return tag


async def delete_all_tags(db_session: AsyncSession) -> int:
    """
    Deletes all tags from the database. Used primarily for testing.

    Args:
        db_session: Database session

    Returns:
        Number of tags deleted
    """
    result = await db_session.execute(delete(Tag))
    await db_session.commit()
    return result.rowcount
