from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.video import Video
from ...schemas.video import VideoCreate


async def create_videos_bulk(
    db_session: AsyncSession, videos_to_create: list[VideoCreate]
) -> None:
    """
    Bulk inserts video records using PostgreSQL's "ON CONFLICT DO NOTHING".
    This is highly efficient for adding many videos at once and safely
    handles duplicates without raising an error.
    """
    if not videos_to_create:
        return

    # Convert Pydantic models to dictionaries for the insert statement
    video_dicts = [video.model_dump() for video in videos_to_create]

    # Create the bulk insert statement
    stmt = insert(Video).values(video_dicts)

    # Add the ON CONFLICT clause to ignore duplicates based on the primary key (id)
    stmt = stmt.on_conflict_do_nothing(index_elements=["id"])

    await db_session.execute(stmt)
    await db_session.commit()


async def get_video_by_id(db_session: AsyncSession, video_id: str) -> Video | None:
    res = await db_session.execute(select(Video).where(Video.id == video_id))
    return res.scalars().first()


async def get_all_videos(
    db_session: AsyncSession, limit: int = 50, offset: int = 0
) -> list[Video]:
    stmt = (
        select(Video)
        .order_by(Video.published_at.desc().nullslast(), Video.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    res = await db_session.execute(stmt)
    return list(res.scalars().all())


async def get_videos_by_channel_id(
    db_session: AsyncSession, channel_id: str, limit: int = 50, offset: int = 0
) -> list[Video]:
    stmt = (
        select(Video)
        .where(Video.channel_id == channel_id)
        .order_by(Video.published_at.desc().nullslast(), Video.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    res = await db_session.execute(stmt)
    return list(res.scalars().all())
