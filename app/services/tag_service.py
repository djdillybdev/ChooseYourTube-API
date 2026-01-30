"""
Tag management service.

Provides utilities for tag synchronization and management across entities.
"""

from typing import Protocol
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.schemas.base import PaginatedResponse

from ..db.crud import crud_tag
from ..db.models.tag import Tag
from ..schemas.tag import TagCreate, TagUpdate, TagOut


class TaggableEntity(Protocol):
    """Protocol for entities that can have tags."""

    tags: list  # Relationship to Tag model


async def sync_entity_tags(
    entity: TaggableEntity, tag_ids: list[int], db_session: AsyncSession
) -> None:
    """
    Synchronize tags for any entity (Channel or Video).

    This function handles the complete tag synchronization:
    1. Validates all requested tags exist in database
    2. Calculates which tags to add and remove
    3. Updates the entity's tag relationships

    Args:
        entity: The entity (Channel or Video) to sync tags for
        tag_ids: List of tag IDs that should be associated with the entity
        db_session: Database session for queries

    Raises:
        HTTPException: If any requested tag ID doesn't exist
    """
    from ..db.models.tag import Tag

    # Load all requested tags from database
    requested_tag_ids = set(tag_ids)
    requested_tags = []

    for tag_id in requested_tag_ids:
        tag = await db_session.get(Tag, tag_id)
        if tag is None:
            raise HTTPException(
                status_code=400, detail=f"Tag with id {tag_id} does not exist"
            )
        requested_tags.append(tag)

    # Calculate current tags
    current_tag_ids = {tag.id for tag in entity.tags}

    # Find tags to add and remove
    tags_to_add_ids = requested_tag_ids - current_tag_ids
    tags_to_remove_ids = current_tag_ids - requested_tag_ids

    # Remove tags that are no longer needed
    for tag in list(entity.tags):
        if tag.id in tags_to_remove_ids:
            entity.tags.remove(tag)

    # Add new tags
    for tag in requested_tags:
        if tag.id in tags_to_add_ids:
            entity.tags.append(tag)


async def get_all_tags(
    db_session: AsyncSession, limit: int | None = None, offset: int = 0
) -> PaginatedResponse[TagOut]:
    """
    Get all tags with pagination.

    Args:
        db_session: Database session
        limit: Maximum number of tags to return
        offset: Number of tags to skip

    Returns:
        List of Tag instances
    """
    tags = crud_tag.get_tags(
        db_session, limit=limit, offset=offset, order_by="name", order_direction="asc"
    )

    return PaginatedResponse[TagOut](
        total=len(tags),
        items=tags,
        limit=limit,
        offset=offset,
        has_more=offset + len(tags) < len(tags),
    )


async def get_tag_by_id(tag_id: int, db_session: AsyncSession) -> Tag:
    """
    Get a tag by its ID.

    Args:
        tag_id: Tag ID
        db_session: Database session

    Returns:
        Tag instance

    Raises:
        HTTPException: If tag not found
    """
    tag = await crud_tag.get_tags(db_session, id=tag_id, first=True)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag


async def create_new_tag(payload: TagCreate, db_session: AsyncSession) -> Tag:
    """
    Create a new tag.

    Args:
        payload: Tag creation data
        db_session: Database session

    Returns:
        Created Tag instance

    Raises:
        HTTPException: If tag with same name already exists
    """
    # Check if tag with this name already exists
    existing_tag = await crud_tag.get_tags(db_session, name=payload.name, first=True)
    if existing_tag:
        raise HTTPException(
            status_code=409, detail=f"Tag with name '{payload.name}' already exists"
        )

    # Create new tag
    new_tag = Tag(name=payload.name)
    try:
        return await crud_tag.create_tag(db_session, new_tag)
    except IntegrityError:
        await db_session.rollback()
        raise HTTPException(
            status_code=409, detail=f"Tag with name '{payload.name}' already exists"
        )


async def update_tag(tag_id: int, payload: TagUpdate, db_session: AsyncSession) -> Tag:
    """
    Update a tag's name.

    Args:
        tag_id: Tag ID
        payload: Update data
        db_session: Database session

    Returns:
        Updated Tag instance

    Raises:
        HTTPException: If tag not found or new name conflicts with existing tag
    """
    # Get existing tag
    tag = await get_tag_by_id(tag_id, db_session)

    # Update name if provided
    if payload.name is not None:
        # Check if new name conflicts with existing tag
        existing_tag = await crud_tag.get_tags(
            db_session, name=payload.name, first=True
        )
        if existing_tag and existing_tag.id != tag_id:
            raise HTTPException(
                status_code=409, detail=f"Tag with name '{payload.name}' already exists"
            )
        tag.name = payload.name

    # Save changes
    db_session.add(tag)
    await db_session.commit()
    await db_session.refresh(tag)
    return tag


async def delete_tag_by_id(tag_id: int, db_session: AsyncSession) -> None:
    """
    Delete a tag by its ID.

    Args:
        tag_id: Tag ID
        db_session: Database session

    Raises:
        HTTPException: If tag not found
    """
    # Get tag to ensure it exists
    tag = await get_tag_by_id(tag_id, db_session)

    # Delete the tag (relationships will be cleaned up automatically)
    await crud_tag.delete_tag(db_session, tag)


async def get_videos_for_tag(
    tag_id: int, db_session: AsyncSession, limit: int = 50, offset: int = 0
):
    """
    Get all videos associated with a tag.

    Args:
        tag_id: Tag ID
        db_session: Database session
        limit: Maximum number of videos to return
        offset: Number of videos to skip

    Returns:
        List of Video instances

    Raises:
        HTTPException: If tag not found
    """
    # Get tag with videos relationship
    tag = await get_tag_by_id(tag_id, db_session)

    # Return videos (already loaded via selectin)
    # Note: This doesn't use limit/offset on the videos themselves
    # For proper pagination, we'd need a more complex query
    return tag.videos[offset : offset + limit] if limit else tag.videos[offset:]


async def get_channels_for_tag(
    tag_id: int, db_session: AsyncSession, limit: int = 50, offset: int = 0
):
    """
    Get all channels associated with a tag.

    Args:
        tag_id: Tag ID
        db_session: Database session
        limit: Maximum number of channels to return
        offset: Number of channels to skip

    Returns:
        List of Channel instances

    Raises:
        HTTPException: If tag not found
    """
    # Get tag with channels relationship
    tag = await get_tag_by_id(tag_id, db_session)

    # Return channels (already loaded via selectin)
    return tag.channels[offset : offset + limit] if limit else tag.channels[offset:]
