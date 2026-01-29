from typing import Literal
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect
from ..models.channel import Channel

_UNSET = object()

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

async def get_channel_by_id(
    db_session: AsyncSession, channel_id: str
) -> Channel | None:
    """
    Retrieves a Channel by its primary key (the YouTube channel ID).
    """
    result = await db_session.execute(select(Channel).where(Channel.id == channel_id))
    return result.scalars().first()


async def get_all_channels(db_session: AsyncSession) -> list[Channel]:
    """
    Retrieves all channels from the database.
    """
    result = await db_session.execute(select(Channel).order_by(Channel.title))
    return list(result.scalars().all())

async def get_channels(
        db: AsyncSession,
        *,
        id: str | None = None,
        title: str | None = None,
        handle: str | None = None,
        description: str | None = None,
        is_favorited: bool | None = None,
        folder_id: int | None | object = _UNSET,
        # Pagination
        limit: int | None = None,
        offset: int = 0,
        # Ordering
        order_by: str = "title",
        order_direction: Literal["asc", "desc"] = "asc",
        # Return type control
        first: bool = False
) -> list[Channel] | Channel | None:

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

    query = select(Channel)

    for field_name, value in filters.items():
        column = getattr(Channel, field_name)
        query = query.where(column == value)

    order_column = getattr(Channel, order_by)
    if order_direction == "desc":
        query = query.order_by(order_column.desc())
    else:
        query = query.order_by(order_column.asc())

    if limit is not None:
        query = query.limit(limit)
    query = query.offset(offset)

    result = await db.execute(query)

    if first:
        return result.scalars().first()
    else:
        return list(result.scalars().all())


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
