from typing import Literal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect
from ..models.folder import Folder

_UNSET = object()

def _get_valid_fields(model_class) -> set[str]:
    """Extract valid column names from SQLAlchemy model."""
    mapper = inspect(model_class)
    return {col.key for col in mapper.columns}

def _validate_pagination(limit: int | None, offset: int) -> None:
    """Validate pagination parameters."""
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative")
    if offset < 0:
        raise ValueError("offset must be non-negative")

def _validate_order_by_field(model_class, field_name: str) -> None:
    """Validate that an order_by field exists on the model."""
    valid_fields = _get_valid_fields(model_class)
    if field_name not in valid_fields:
        raise ValueError(
            f"Invalid order_by field '{field_name}'. "
            f"Valid fields: {', '.join(sorted(valid_fields))}"
        )

async def get_by_id(db: AsyncSession, folder_id: int) -> Folder | None:
    res = await db.execute(select(Folder).where(Folder.id == folder_id))
    return res.scalars().first()


async def get_all(db: AsyncSession) -> list[Folder]:
    res = await db.execute(select(Folder))
    return list(res.scalars().all())

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

    query = select(Folder)

    for field_name, value in filters.items():
        column = getattr(Folder, field_name)
        query = query.where(column == value)

    order_column = getattr(Folder, order_by)
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



async def create(db: AsyncSession, folder: Folder) -> Folder:
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return folder


async def delete(db: AsyncSession, folder: Folder) -> None:
    await db.delete(folder)
    await db.commit()
