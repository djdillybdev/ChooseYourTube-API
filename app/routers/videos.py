from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.base import PaginatedResponse
from ..dependencies import DBSessionDep
from ..schemas.video import VideoOut, VideoUpdate
from ..services import video_service

VALID_ORDER_BY = {"published_at", "title", "duration_seconds", "created_at", "relevance"}

router = APIRouter(prefix="/videos", tags=["Videos"])


def _parse_iso_date(value: str, param_name: str) -> datetime:
    """Parse an ISO 8601 date string, raising 400 on failure."""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format for {param_name}. Use ISO 8601 (e.g. 2026-01-01T00:00:00Z).",
        )


@router.get("/", response_model=PaginatedResponse[VideoOut])
async def list_videos(
    db_session: DBSessionDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    is_favorited: bool | None = Query(None, description="Filter by favorited status"),
    is_watched: bool | None = Query(None, description="Filter by watched status"),
    is_short: bool | None = Query(None, description="Filter by YouTube Shorts"),
    channel_id: str | None = Query(
        None,
        description="Filter by channel ID (single ID or comma-separated list)",
        examples=["ch001", "ch001,ch002,ch003"],
    ),
    tag_id: str | None = Query(None, description="Filter by tag ID"),
    published_after: str | None = Query(
        None, description="Filter videos published after this date (ISO 8601 format)"
    ),
    published_before: str | None = Query(
        None, description="Filter videos published before this date (ISO 8601 format)"
    ),
    q: str | None = Query(
        None, description="Search videos by title, description, or tag name"
    ),
    order_by: str = Query(
        "published_at",
        description="Sort field: published_at, title, created_at, duration_seconds, relevance (with q)",
    ),
    order_direction: Literal["asc", "desc"] = Query(
        "desc", description="Sort direction"
    ),
):
    """
    List videos with optional filtering and search.

    Filters:
    - is_favorited: Show only favorited videos
    - is_watched: Show only watched/unwatched videos
    - is_short: Show only YouTube Shorts or exclude them
    - channel_id: Filter by single channel ID or multiple IDs (comma-separated)
    - tag_id: Show only videos with a specific tag
    - published_after: Show videos published after a date (e.g., "2026-01-01T00:00:00Z")
    - published_before: Show videos published before a date (e.g., "2026-12-31T23:59:59Z")
    - q: Full-text search across video title, description, and tag names
    - order_by: Sort field (default: published_at; use "relevance" with search queries)
    - order_direction: Sort direction (asc or desc)
    """
    # Validate order_by
    if order_by not in VALID_ORDER_BY:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid order_by value '{order_by}'. Must be one of: {', '.join(sorted(VALID_ORDER_BY))}",
        )

    # Parse channel_id: support both single ID and comma-separated list
    parsed_channel_id = None
    if channel_id is not None:
        if "," in channel_id:
            parsed_channel_id = [cid.strip() for cid in channel_id.split(",") if cid.strip()]
            if not parsed_channel_id:
                raise HTTPException(
                    status_code=400,
                    detail="channel_id cannot be empty when using comma-separated values",
                )
        else:
            parsed_channel_id = channel_id.strip()

    # Parse date strings to datetime objects
    parsed_after = _parse_iso_date(published_after, "published_after") if published_after else None
    parsed_before = _parse_iso_date(published_before, "published_before") if published_before else None

    return await video_service.get_all_videos(
        db_session=db_session,
        limit=limit,
        offset=offset,
        is_favorited=is_favorited,
        is_watched=is_watched,
        is_short=is_short,
        channel_id=parsed_channel_id,
        tag_id=tag_id,
        published_after=parsed_after,
        published_before=parsed_before,
        q=q,
        order_by=order_by,
        order_direction=order_direction,
    )


@router.get("/{video_id}", response_model=VideoOut)
async def get_video_by_id(video_id: str, db_session: DBSessionDep):
    return await video_service.get_video_by_id(video_id=video_id, db_session=db_session)


@router.get("/by-channel/{channel_id}", response_model=list[VideoOut])
async def list_videos_by_channel(
    channel_id: str,
    db_session: DBSessionDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await video_service.get_videos_for_channel(
        channel_id=channel_id, db_session=db_session, limit=limit, offset=offset
    )


@router.patch("/{video_id}", response_model=VideoOut)
async def update_video(video_id: str, payload: VideoUpdate, db_session: DBSessionDep):
    """
    Update video metadata (favorited, watched, short status, tags).
    """
    return await video_service.update_video(
        video_id=video_id, payload=payload, db_session=db_session
    )


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(video_id: str, db_session: DBSessionDep):
    """
    Delete a video by its ID.
    """
    await video_service.delete_video_by_id(video_id=video_id, db_session=db_session)
