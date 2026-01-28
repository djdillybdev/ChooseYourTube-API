from fastapi import APIRouter, Query
from ..dependencies import DBSessionDep
from ..schemas.video import VideoOut
from ..services import video_service

router = APIRouter(prefix="/videos", tags=["Videos"])


@router.get("/", response_model=list[VideoOut])
async def list_videos(
    db_session: DBSessionDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await video_service.get_all_videos(
        db_session=db_session, limit=limit, offset=offset
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
