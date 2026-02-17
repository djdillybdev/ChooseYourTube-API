"""
Playlist management service.
"""

import random
import uuid
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.base import PaginatedResponse
from ..db.crud import crud_playlist
from ..db.crud.crud_video import get_videos
from ..db.models.playlist import Playlist
from ..schemas.playlist import (
    PlaylistCreate,
    PlaylistUpdate,
    PlaylistOut,
    PlaylistDetailOut,
    PlaylistAddVideo,
    PlaylistAddVideos,
    PlaylistMoveVideo,
    PlaylistSetPosition,
    PlaylistSetVideos,
)


async def get_all_playlists(
    db_session: AsyncSession,
    owner_id: str = "test-user",
    limit: int = 50,
    offset: int = 0,
    is_system: bool | None = None,
) -> PaginatedResponse[PlaylistOut]:
    total = await crud_playlist.count_playlists(
        db_session, owner_id=owner_id, is_system=is_system
    )

    playlists = await crud_playlist.get_playlists(
        db_session,
        owner_id=owner_id,
        is_system=is_system,
        limit=limit,
        offset=offset,
        order_by="name",
        order_direction="asc",
    )

    # Ensure playlists is a list (handles case where it might be None)
    if not isinstance(playlists, list):
        playlists = [] if playlists is None else [playlists]

    return PaginatedResponse[PlaylistOut](
        total=total,
        items=playlists,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


async def get_playlist_by_id(
    playlist_id: str, db_session: AsyncSession, owner_id: str = "test-user"
) -> Playlist:
    playlist = await crud_playlist.get_playlists(
        db_session, owner_id=owner_id, id=playlist_id, first=True
    )
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return playlist


async def _build_detail_out(
    playlist: Playlist, db_session: AsyncSession, owner_id: str = "test-user"
) -> PlaylistDetailOut:
    video_ids = await crud_playlist.get_playlist_video_ids(
        db_session, playlist.id, owner_id=owner_id
    )
    return PlaylistDetailOut(
        id=playlist.id,
        name=playlist.name,
        description=playlist.description,
        is_system=playlist.is_system,
        current_position=playlist.current_position,
        total_videos=len(video_ids),
        created_at=playlist.created_at,
        video_ids=video_ids,
    )


async def get_playlist_detail(
    playlist_id: str, db_session: AsyncSession, owner_id: str = "test-user"
) -> PlaylistDetailOut:
    playlist = await get_playlist_by_id(playlist_id, db_session, owner_id=owner_id)
    return await _build_detail_out(playlist, db_session, owner_id=owner_id)


async def create_new_playlist(
    payload: PlaylistCreate, db_session: AsyncSession, owner_id: str = "test-user"
) -> Playlist:
    playlist_id = str(uuid.uuid4())
    new_playlist = Playlist(
        id=playlist_id,
        owner_id=owner_id,
        name=payload.name,
        description=payload.description,
        is_system=payload.is_system,
    )
    return await crud_playlist.create_playlist(db_session, new_playlist)


async def update_playlist(
    playlist_id: str,
    payload: PlaylistUpdate,
    db_session: AsyncSession,
    owner_id: str = "test-user",
) -> Playlist:
    playlist = await get_playlist_by_id(playlist_id, db_session, owner_id=owner_id)

    if payload.name is not None:
        playlist.name = payload.name
    if payload.description is not None:
        playlist.description = payload.description

    db_session.add(playlist)
    await db_session.commit()
    await db_session.refresh(playlist)
    return playlist


async def delete_playlist_by_id(
    playlist_id: str, db_session: AsyncSession, owner_id: str = "test-user"
) -> None:
    playlist = await get_playlist_by_id(playlist_id, db_session, owner_id=owner_id)
    await crud_playlist.delete_playlist(db_session, playlist)


async def set_playlist_videos(
    playlist_id: str,
    payload: PlaylistSetVideos,
    db_session: AsyncSession,
    owner_id: str = "test-user",
) -> PlaylistDetailOut:
    playlist = await get_playlist_by_id(playlist_id, db_session, owner_id=owner_id)

    # Validate all video IDs exist
    if payload.video_ids:
        existing_videos = await get_videos(
            db_session, owner_id=owner_id, id=payload.video_ids
        )
        found_ids = {v.id for v in existing_videos}
        missing = set(payload.video_ids) - found_ids
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Videos not found: {', '.join(sorted(missing))}",
            )

    await crud_playlist.set_playlist_videos(
        db_session, playlist_id, payload.video_ids, owner_id=owner_id
    )

    # Reset current_position if playlist was cleared or position is now out of bounds
    if not payload.video_ids:
        playlist.current_position = None
    elif playlist.current_position is not None and playlist.current_position >= len(
        payload.video_ids
    ):
        playlist.current_position = None

    db_session.add(playlist)
    await db_session.commit()
    await db_session.refresh(playlist)

    return await _build_detail_out(playlist, db_session, owner_id=owner_id)


async def add_video_to_playlist(
    playlist_id: str,
    payload: PlaylistAddVideo,
    db_session: AsyncSession,
    owner_id: str = "test-user",
) -> PlaylistDetailOut:
    playlist = await get_playlist_by_id(playlist_id, db_session, owner_id=owner_id)

    # Validate video exists
    video = await get_videos(
        db_session, owner_id=owner_id, id=payload.video_id, first=True
    )
    if not video:
        raise HTTPException(
            status_code=400, detail=f"Video '{payload.video_id}' not found"
        )

    await crud_playlist.add_video_to_playlist(
        db_session, playlist_id, payload.video_id, payload.position, owner_id=owner_id
    )

    return await _build_detail_out(playlist, db_session, owner_id=owner_id)


async def add_videos_to_playlist(
    playlist_id: str,
    payload: PlaylistAddVideos,
    db_session: AsyncSession,
    owner_id: str = "test-user",
) -> PlaylistDetailOut:
    playlist = await get_playlist_by_id(playlist_id, db_session, owner_id=owner_id)

    # Validate all video IDs exist
    existing_videos = await get_videos(
        db_session, owner_id=owner_id, id=payload.video_ids
    )
    found_ids = {v.id for v in existing_videos}
    missing = set(payload.video_ids) - found_ids
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Videos not found: {', '.join(sorted(missing))}",
        )

    await crud_playlist.bulk_add_videos_to_playlist(
        db_session, playlist_id, payload.video_ids, payload.position, owner_id=owner_id
    )

    return await _build_detail_out(playlist, db_session, owner_id=owner_id)


async def move_video_in_playlist(
    playlist_id: str,
    payload: PlaylistMoveVideo,
    db_session: AsyncSession,
    owner_id: str = "test-user",
) -> PlaylistDetailOut:
    playlist = await get_playlist_by_id(playlist_id, db_session, owner_id=owner_id)

    try:
        await crud_playlist.move_video_in_playlist(
            db_session,
            playlist_id,
            payload.video_id,
            payload.new_position,
            owner_id=owner_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return await _build_detail_out(playlist, db_session, owner_id=owner_id)


async def set_playlist_position(
    playlist_id: str,
    payload: PlaylistSetPosition,
    db_session: AsyncSession,
    owner_id: str = "test-user",
) -> PlaylistDetailOut:
    playlist = await get_playlist_by_id(playlist_id, db_session, owner_id=owner_id)

    if payload.current_position is not None:
        # Validate position is within bounds
        max_pos = await crud_playlist.get_max_position(
            db_session, playlist_id, owner_id=owner_id
        )
        if max_pos == -1:
            raise HTTPException(status_code=400, detail="Playlist is empty")
        if payload.current_position > max_pos:
            raise HTTPException(
                status_code=400,
                detail=f"Position {payload.current_position} out of bounds (max: {max_pos})",
            )

    playlist.current_position = payload.current_position
    db_session.add(playlist)
    await db_session.commit()
    await db_session.refresh(playlist)

    return await _build_detail_out(playlist, db_session, owner_id=owner_id)


async def remove_video_from_playlist(
    playlist_id: str,
    video_id: str,
    db_session: AsyncSession,
    owner_id: str = "test-user",
) -> None:
    playlist = await get_playlist_by_id(playlist_id, db_session, owner_id=owner_id)

    # Get position of video being removed (for current_position adjustment)
    video_ids = await crud_playlist.get_playlist_video_ids(
        db_session, playlist_id, owner_id=owner_id
    )
    if video_id not in video_ids:
        raise HTTPException(status_code=404, detail="Video not found in playlist")
    removed_index = video_ids.index(video_id)

    rows = await crud_playlist.remove_video_from_playlist(
        db_session, playlist_id, video_id, owner_id=owner_id
    )
    if rows == 0:
        raise HTTPException(status_code=404, detail="Video not found in playlist")

    # Adjust current_position
    if playlist.current_position is not None:
        new_total = len(video_ids) - 1
        if new_total == 0:
            playlist.current_position = None
        elif removed_index < playlist.current_position:
            playlist.current_position -= 1
        elif removed_index == playlist.current_position:
            # Current video removed — stay at same index if possible, else go to last
            if playlist.current_position >= new_total:
                playlist.current_position = new_total - 1 if new_total > 0 else None

        db_session.add(playlist)
        await db_session.commit()
        await db_session.refresh(playlist)


async def clear_playlist(
    playlist_id: str, db_session: AsyncSession, owner_id: str = "test-user"
) -> PlaylistDetailOut:
    playlist = await get_playlist_by_id(playlist_id, db_session, owner_id=owner_id)

    await crud_playlist.clear_playlist_videos(
        db_session, playlist_id, owner_id=owner_id
    )

    playlist.current_position = None
    db_session.add(playlist)
    await db_session.commit()
    await db_session.refresh(playlist)

    return await _build_detail_out(playlist, db_session, owner_id=owner_id)


async def shuffle_playlist(
    playlist_id: str, db_session: AsyncSession, owner_id: str = "test-user"
) -> PlaylistDetailOut:
    playlist = await get_playlist_by_id(playlist_id, db_session, owner_id=owner_id)

    video_ids = await crud_playlist.get_playlist_video_ids(
        db_session, playlist_id, owner_id=owner_id
    )
    if len(video_ids) <= 1:
        return await _build_detail_out(playlist, db_session, owner_id=owner_id)

    current_pos = playlist.current_position

    if current_pos is not None and 0 <= current_pos < len(video_ids):
        # Keep current video in place, shuffle the rest after it
        before = video_ids[: current_pos + 1]
        after = video_ids[current_pos + 1 :]
        random.shuffle(after)
        new_order = before + after
    else:
        # No current position — shuffle everything
        random.shuffle(video_ids)
        new_order = video_ids

    await crud_playlist.set_playlist_videos(
        db_session, playlist_id, new_order, owner_id=owner_id
    )

    return await _build_detail_out(playlist, db_session, owner_id=owner_id)
