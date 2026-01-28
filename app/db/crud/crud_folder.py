from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.folder import Folder


async def get_by_id(db: AsyncSession, folder_id: int) -> Folder | None:
    res = await db.execute(select(Folder).where(Folder.id == folder_id))
    return res.scalars().first()


async def get_all(db: AsyncSession) -> list[Folder]:
    res = await db.execute(select(Folder))
    return list(res.scalars().all())


async def create(db: AsyncSession, folder: Folder) -> Folder:
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return folder


async def delete(db: AsyncSession, folder: Folder) -> None:
    await db.delete(folder)
    await db.commit()
