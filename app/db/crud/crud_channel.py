from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.channel import Channel


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
