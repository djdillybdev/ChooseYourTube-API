from fastapi import APIRouter, Query, status

from app.schemas.base import PaginatedResponse
from ..dependencies import DBSessionDep, CurrentUserDep
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
from ..services import playlist_service

router = APIRouter(prefix="/playlists", tags=["Playlists"])


@router.get("/", response_model=PaginatedResponse[PlaylistOut])
async def list_playlists(
    db_session: DBSessionDep,
    user: CurrentUserDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    is_system: bool | None = Query(None, description="Filter by system playlist flag"),
):
    """List all playlists with pagination."""
    return await playlist_service.get_all_playlists(
        db_session=db_session,
        limit=limit,
        offset=offset,
        is_system=is_system,
        owner_id=str(user.id),
    )


@router.get("/{playlist_id}", response_model=PlaylistDetailOut)
async def get_playlist(
    playlist_id: str, db_session: DBSessionDep, user: CurrentUserDep
):
    """Get a playlist with its ordered video IDs."""
    return await playlist_service.get_playlist_detail(
        playlist_id=playlist_id, db_session=db_session, owner_id=str(user.id)
    )


@router.post("/", response_model=PlaylistOut, status_code=status.HTTP_201_CREATED)
async def create_playlist(
    payload: PlaylistCreate, db_session: DBSessionDep, user: CurrentUserDep
):
    """Create a new playlist."""
    return await playlist_service.create_new_playlist(
        payload=payload, db_session=db_session, owner_id=str(user.id)
    )


@router.patch("/{playlist_id}", response_model=PlaylistOut)
async def update_playlist(
    playlist_id: str,
    payload: PlaylistUpdate,
    db_session: DBSessionDep,
    user: CurrentUserDep,
):
    """Update a playlist's name or description."""
    return await playlist_service.update_playlist(
        playlist_id=playlist_id,
        payload=payload,
        db_session=db_session,
        owner_id=str(user.id),
    )


@router.delete("/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_playlist(
    playlist_id: str, db_session: DBSessionDep, user: CurrentUserDep
):
    """Delete a playlist."""
    await playlist_service.delete_playlist_by_id(
        playlist_id=playlist_id, db_session=db_session, owner_id=str(user.id)
    )


@router.put("/{playlist_id}/videos", response_model=PlaylistDetailOut)
async def set_playlist_videos(
    playlist_id: str,
    payload: PlaylistSetVideos,
    db_session: DBSessionDep,
    user: CurrentUserDep,
):
    """Set the full ordered video list for a playlist."""
    return await playlist_service.set_playlist_videos(
        playlist_id=playlist_id,
        payload=payload,
        db_session=db_session,
        owner_id=str(user.id),
    )


@router.post(
    "/{playlist_id}/videos",
    response_model=PlaylistDetailOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_video_to_playlist(
    playlist_id: str,
    payload: PlaylistAddVideo,
    db_session: DBSessionDep,
    user: CurrentUserDep,
):
    """Add a video to a playlist. If already present, moves it to the requested position."""
    return await playlist_service.add_video_to_playlist(
        playlist_id=playlist_id,
        payload=payload,
        db_session=db_session,
        owner_id=str(user.id),
    )


@router.post(
    "/{playlist_id}/videos/bulk",
    response_model=PlaylistDetailOut,
    status_code=status.HTTP_201_CREATED,
)
async def bulk_add_videos(
    playlist_id: str,
    payload: PlaylistAddVideos,
    db_session: DBSessionDep,
    user: CurrentUserDep,
):
    """Bulk add videos to a playlist with optional insert position."""
    return await playlist_service.add_videos_to_playlist(
        playlist_id=playlist_id,
        payload=payload,
        db_session=db_session,
        owner_id=str(user.id),
    )


@router.patch("/{playlist_id}/videos/move", response_model=PlaylistDetailOut)
async def move_video(
    playlist_id: str,
    payload: PlaylistMoveVideo,
    db_session: DBSessionDep,
    user: CurrentUserDep,
):
    """Move a video to a new position in the playlist."""
    return await playlist_service.move_video_in_playlist(
        playlist_id=playlist_id,
        payload=payload,
        db_session=db_session,
        owner_id=str(user.id),
    )


@router.patch("/{playlist_id}/position", response_model=PlaylistDetailOut)
async def set_position(
    playlist_id: str,
    payload: PlaylistSetPosition,
    db_session: DBSessionDep,
    user: CurrentUserDep,
):
    """Set the current playback position."""
    return await playlist_service.set_playlist_position(
        playlist_id=playlist_id,
        payload=payload,
        db_session=db_session,
        owner_id=str(user.id),
    )


@router.post("/{playlist_id}/shuffle", response_model=PlaylistDetailOut)
async def shuffle_playlist(
    playlist_id: str, db_session: DBSessionDep, user: CurrentUserDep
):
    """Shuffle videos after the current position."""
    return await playlist_service.shuffle_playlist(
        playlist_id=playlist_id, db_session=db_session, owner_id=str(user.id)
    )


@router.delete(
    "/{playlist_id}/videos",
    response_model=PlaylistDetailOut,
)
async def clear_playlist_videos(
    playlist_id: str, db_session: DBSessionDep, user: CurrentUserDep
):
    """Clear all videos from a playlist."""
    return await playlist_service.clear_playlist(
        playlist_id=playlist_id, db_session=db_session, owner_id=str(user.id)
    )


@router.delete(
    "/{playlist_id}/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_video_from_playlist(
    playlist_id: str, video_id: str, db_session: DBSessionDep, user: CurrentUserDep
):
    """Remove a video from a playlist."""
    await playlist_service.remove_video_from_playlist(
        playlist_id=playlist_id,
        video_id=video_id,
        db_session=db_session,
        owner_id=str(user.id),
    )
