from datetime import datetime, timezone
from typing import Literal
from sqlalchemy import select, func, delete, insert, update
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.playlist import Playlist
from ..models.association_tables import playlist_videos
from .crud_base import (
    base_get,
    _validate_pagination,
    _validate_order_by_field,
)


async def get_playlists(
    db: AsyncSession,
    *,
    id: str | list[str] | None = None,
    name: str | None = None,
    is_system: bool | None = None,
    limit: int | None = None,
    offset: int = 0,
    order_by: str = "name",
    order_direction: Literal["asc", "desc"] = "asc",
    first: bool = False,
) -> list[Playlist] | Playlist | None:
    _validate_pagination(limit, offset)
    if order_direction not in ("asc", "desc"):
        raise ValueError("order_direction must be 'asc' or 'desc'")
    _validate_order_by_field(Playlist, order_by)

    filters = {}
    if id is not None:
        filters["id"] = id
    if name is not None:
        filters["name"] = name
    if is_system is not None:
        filters["is_system"] = is_system

    return await base_get(
        db,
        Playlist,
        filters=filters,
        limit=limit,
        offset=offset,
        order_by=order_by,
        order_direction=order_direction,
        first=first,
    )


async def count_playlists(
    db: AsyncSession,
    *,
    id: str | list[str] | None = None,
    name: str | None = None,
    is_system: bool | None = None,
) -> int:
    filters = {}
    if id is not None:
        filters["id"] = id
    if name is not None:
        filters["name"] = name
    if is_system is not None:
        filters["is_system"] = is_system

    query = select(func.count()).select_from(Playlist)
    for field_name, value in filters.items():
        column = getattr(Playlist, field_name)
        if isinstance(value, list):
            query = query.where(column.in_(value))
        else:
            query = query.where(column == value)

    result = await db.execute(query)
    return result.scalar() or 0


async def create_playlist(db: AsyncSession, playlist: Playlist) -> Playlist:
    db.add(playlist)
    await db.commit()
    await db.refresh(playlist)
    return playlist


async def delete_playlist(db: AsyncSession, playlist: Playlist) -> Playlist:
    await db.delete(playlist)
    await db.commit()
    return playlist


async def get_playlist_video_ids(db: AsyncSession, playlist_id: str) -> list[str]:
    """Get ordered video IDs for a playlist."""
    query = (
        select(playlist_videos.c.video_id)
        .where(playlist_videos.c.playlist_id == playlist_id)
        .order_by(playlist_videos.c.position.asc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_max_position(db: AsyncSession, playlist_id: str) -> int:
    """Return the max position in a playlist, or -1 if empty."""
    query = select(func.coalesce(func.max(playlist_videos.c.position), -1)).where(
        playlist_videos.c.playlist_id == playlist_id
    )
    result = await db.execute(query)
    return result.scalar()


async def set_playlist_videos(
    db: AsyncSession, playlist_id: str, video_ids: list[str]
) -> None:
    """Replace all videos in a playlist with the given ordered list."""
    await db.execute(
        delete(playlist_videos).where(
            playlist_videos.c.playlist_id == playlist_id
        )
    )

    if video_ids:
        await db.execute(
            insert(playlist_videos),
            [
                {
                    "playlist_id": playlist_id,
                    "video_id": vid,
                    "position": idx,
                    "created_at": datetime.now(timezone.utc),
                }
                for idx, vid in enumerate(video_ids)
            ],
        )

    await db.commit()


async def add_video_to_playlist(
    db: AsyncSession, playlist_id: str, video_id: str, position: int | None = None
) -> None:
    """Add a single video to a playlist. If already present, move it instead."""
    # Check if video already exists in the playlist
    existing = await db.execute(
        select(playlist_videos.c.position).where(
            playlist_videos.c.playlist_id == playlist_id,
            playlist_videos.c.video_id == video_id,
        )
    )
    existing_pos = existing.scalar()

    if existing_pos is not None:
        # Video already in playlist — move it to the requested position
        if position is None:
            position = await get_max_position(db, playlist_id)
        await _move_video(db, playlist_id, video_id, existing_pos, position)
        await db.commit()
        return

    if position is None:
        position = (await get_max_position(db, playlist_id)) + 1
    else:
        # Shift existing items at >= position down
        await db.execute(
            update(playlist_videos)
            .where(
                playlist_videos.c.playlist_id == playlist_id,
                playlist_videos.c.position >= position,
            )
            .values(position=playlist_videos.c.position + 1)
        )

    await db.execute(
        insert(playlist_videos).values(
            playlist_id=playlist_id,
            video_id=video_id,
            position=position,
            created_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()


async def remove_video_from_playlist(
    db: AsyncSession, playlist_id: str, video_id: str
) -> int:
    """Remove a video from a playlist and compact positions. Returns number of rows deleted."""
    # Get the position of the video being removed
    result = await db.execute(
        select(playlist_videos.c.position).where(
            playlist_videos.c.playlist_id == playlist_id,
            playlist_videos.c.video_id == video_id,
        )
    )
    removed_position = result.scalar()

    if removed_position is None:
        return 0

    # Delete the association
    await db.execute(
        delete(playlist_videos).where(
            playlist_videos.c.playlist_id == playlist_id,
            playlist_videos.c.video_id == video_id,
        )
    )

    # Compact: shift items after removed position up by 1
    await db.execute(
        update(playlist_videos)
        .where(
            playlist_videos.c.playlist_id == playlist_id,
            playlist_videos.c.position > removed_position,
        )
        .values(position=playlist_videos.c.position - 1)
    )

    await db.commit()
    return 1


async def _move_video(
    db: AsyncSession,
    playlist_id: str,
    video_id: str,
    old_position: int,
    new_position: int,
) -> None:
    """Move a video from old_position to new_position, shifting others accordingly."""
    if old_position == new_position:
        return

    # Temporarily set to -1 to avoid unique constraint issues
    await db.execute(
        update(playlist_videos)
        .where(
            playlist_videos.c.playlist_id == playlist_id,
            playlist_videos.c.video_id == video_id,
        )
        .values(position=-1)
    )

    if old_position < new_position:
        # Moving down: shift items between old+1..new up by 1
        await db.execute(
            update(playlist_videos)
            .where(
                playlist_videos.c.playlist_id == playlist_id,
                playlist_videos.c.position > old_position,
                playlist_videos.c.position <= new_position,
            )
            .values(position=playlist_videos.c.position - 1)
        )
    else:
        # Moving up: shift items between new..old-1 down by 1
        await db.execute(
            update(playlist_videos)
            .where(
                playlist_videos.c.playlist_id == playlist_id,
                playlist_videos.c.position >= new_position,
                playlist_videos.c.position < old_position,
            )
            .values(position=playlist_videos.c.position + 1)
        )

    # Place video at new position
    await db.execute(
        update(playlist_videos)
        .where(
            playlist_videos.c.playlist_id == playlist_id,
            playlist_videos.c.video_id == video_id,
        )
        .values(position=new_position)
    )


async def move_video_in_playlist(
    db: AsyncSession, playlist_id: str, video_id: str, new_position: int
) -> None:
    """Move a video to a new position in a playlist."""
    # Get current position
    result = await db.execute(
        select(playlist_videos.c.position).where(
            playlist_videos.c.playlist_id == playlist_id,
            playlist_videos.c.video_id == video_id,
        )
    )
    old_position = result.scalar()

    if old_position is None:
        raise ValueError(f"Video '{video_id}' not found in playlist")

    # Clamp new_position to valid range
    max_pos = await get_max_position(db, playlist_id)
    new_position = min(new_position, max_pos)

    await _move_video(db, playlist_id, video_id, old_position, new_position)
    await db.commit()


async def bulk_add_videos_to_playlist(
    db: AsyncSession,
    playlist_id: str,
    video_ids: list[str],
    start_position: int | None = None,
) -> None:
    """Add multiple videos to a playlist. Duplicates are moved to new positions."""
    # Find which videos already exist in this playlist
    result = await db.execute(
        select(playlist_videos.c.video_id).where(
            playlist_videos.c.playlist_id == playlist_id,
            playlist_videos.c.video_id.in_(video_ids),
        )
    )
    existing_ids = set(result.scalars().all())

    # Remove duplicates first (they'll be re-inserted at new positions)
    if existing_ids:
        for vid in video_ids:
            if vid in existing_ids:
                await db.execute(
                    delete(playlist_videos).where(
                        playlist_videos.c.playlist_id == playlist_id,
                        playlist_videos.c.video_id == vid,
                    )
                )
        # Compact positions after removals
        await _compact_positions(db, playlist_id)

    if start_position is None:
        start_position = (await get_max_position(db, playlist_id)) + 1
    else:
        # Shift existing items at >= start_position
        await db.execute(
            update(playlist_videos)
            .where(
                playlist_videos.c.playlist_id == playlist_id,
                playlist_videos.c.position >= start_position,
            )
            .values(position=playlist_videos.c.position + len(video_ids))
        )

    # Deduplicate video_ids preserving order (keep last occurrence)
    seen = set()
    unique_ids = []
    for vid in video_ids:
        if vid not in seen:
            seen.add(vid)
            unique_ids.append(vid)

    await db.execute(
        insert(playlist_videos),
        [
            {
                "playlist_id": playlist_id,
                "video_id": vid,
                "position": start_position + idx,
                "created_at": datetime.now(timezone.utc),
            }
            for idx, vid in enumerate(unique_ids)
        ],
    )

    await db.commit()


async def clear_playlist_videos(db: AsyncSession, playlist_id: str) -> None:
    """Delete all video associations for a playlist."""
    await db.execute(
        delete(playlist_videos).where(
            playlist_videos.c.playlist_id == playlist_id
        )
    )
    await db.commit()


async def _compact_positions(db: AsyncSession, playlist_id: str) -> None:
    """Re-number positions to be contiguous starting from 0."""
    result = await db.execute(
        select(playlist_videos.c.video_id, playlist_videos.c.position)
        .where(playlist_videos.c.playlist_id == playlist_id)
        .order_by(playlist_videos.c.position.asc())
    )
    rows = result.all()

    for idx, (video_id, current_pos) in enumerate(rows):
        if current_pos != idx:
            await db.execute(
                update(playlist_videos)
                .where(
                    playlist_videos.c.playlist_id == playlist_id,
                    playlist_videos.c.video_id == video_id,
                )
                .values(position=idx)
            )
