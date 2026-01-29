"""
Base CRUD utilities for all models.

Contains shared validation functions and the base_get() function that
eliminates code duplication across get_channels(), get_videos(), and get_folders().
"""

from typing import Any, Callable, Literal, Type, TypeVar
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect

# Type variable for SQLAlchemy models
ModelType = TypeVar("ModelType")


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


async def base_get(
    db: AsyncSession,
    model_class: Type[ModelType],
    *,
    filters: dict[str, Any],
    limit: int | None,
    offset: int,
    order_by: str,
    order_direction: Literal["asc", "desc"],
    first: bool = False,
    special_ordering_handler: Callable | None = None
) -> list[ModelType] | ModelType | None:
    """
    Base query function for retrieving model instances with filtering, pagination, and ordering.

    This function consolidates the common query logic used by get_channels(), get_videos(),
    and get_folders() to eliminate code duplication.

    Args:
        db: Database session
        model_class: SQLAlchemy model class to query
        filters: Dictionary of field_name: value pairs to filter by
        limit: Maximum number of results (None = unlimited)
        offset: Number of results to skip (for pagination)
        order_by: Field to order by (must be valid model column)
        order_direction: Sort direction ('asc' or 'desc')
        first: If True, return single object or None instead of list
        special_ordering_handler: Optional callback for custom ordering logic.
            Signature: (query, order_column, order_by: str, order_direction: str) -> query

    Returns:
        - If first=True: Single model instance or None
        - If first=False: List of model instances (empty list if no matches)

    Examples:
        # Get all channels in a folder, ordered by title
        channels = await base_get(
            db, Channel,
            filters={"folder_id": 1},
            limit=None,
            offset=0,
            order_by="title",
            order_direction="asc"
        )

        # Get single video by ID
        video = await base_get(
            db, Video,
            filters={"id": "abc123"},
            limit=None,
            offset=0,
            order_by="published_at",
            order_direction="desc",
            first=True
        )
    """
    # 1. Initialize query
    query = select(model_class)

    # 2. Apply filters
    for field_name, value in filters.items():
        column = getattr(model_class, field_name)
        query = query.where(column == value)

    # 3. Apply ordering
    order_column = getattr(model_class, order_by)
    if special_ordering_handler is not None:
        # Use custom ordering logic (e.g., for videos' nullslast)
        query = special_ordering_handler(query, order_column, order_by, order_direction)
    else:
        # Standard ordering
        if order_direction == "desc":
            query = query.order_by(order_column.desc())
        else:
            query = query.order_by(order_column.asc())

    # 4. Apply pagination
    if limit is not None:
        query = query.limit(limit)
    query = query.offset(offset)

    # 5. Execute query
    result = await db.execute(query)

    # 6. Return based on 'first' flag
    if first:
        return result.scalars().first()
    else:
        return list(result.scalars().all())


async def base_update(db: AsyncSession, model_instance: ModelType) -> ModelType:
    """
    Base update function for persisting changes to a model instance.

    This function handles the commit and refresh operations, providing a
    consistent interface for all update operations across different models.

    Args:
        db: Database session
        model_instance: The SQLAlchemy model instance with modified attributes

    Returns:
        The refreshed model instance with updated data from the database

    Example:
        folder = await crud_folder.get_folders(db, id=1, first=True)
        folder.name = "New Name"
        updated_folder = await crud_folder.update(db, folder)
    """
    await db.commit()
    await db.refresh(model_instance)
    return model_instance
