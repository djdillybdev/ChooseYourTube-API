from fastapi import APIRouter, status, Query, HTTPException
from ..dependencies import DBSessionDep, YouTubeAPIDep, ArqDep
from ..schemas.channel import ChannelCreate, ChannelOut, ChannelUpdate
from ..schemas.base import PaginatedResponse
from ..services import channel_service

router = APIRouter(prefix="/channels", tags=["Channels"])


@router.get("/", response_model=PaginatedResponse[ChannelOut])
async def list_channels(
    db_session: DBSessionDep,
    is_favorited: bool | None = Query(None, description="Filter by favorited status"),
    folder_id: int | None = Query(
        None, description="Filter by folder ID (use 0 for root/no folder)"
    ),
    tag_id: int | None = Query(None, description="Filter by tag ID"),
    limit: int = Query(50, ge=1, le=200, description="Number of items per page"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
):
    """
    Retrieves a list of all channels with optional filtering and pagination.

    Filters:
    - is_favorited: Show only favorited channels
    - folder_id: Show only channels in a specific folder (use 0 for channels with no folder)
    - tag_id: Show only channels with a specific tag

    Pagination:
    - limit: Number of items per page (default: 50, max: 200)
    - offset: Number of items to skip
    """
    return await channel_service.get_all_channels(
        db_session=db_session,
        is_favorited=is_favorited,
        folder_id=folder_id,
        tag_id=tag_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{channel_id}", response_model=ChannelOut)
async def get_channel_by_id(channel_id: str, db_session: DBSessionDep):
    """
    Retrieves a single channel by its YouTube Channel ID.
    """
    return await channel_service.get_channel_by_id(channel_id, db_session)


@router.post("/", response_model=ChannelOut, status_code=status.HTTP_201_CREATED)
async def create_channel(
    channel_data: ChannelCreate,
    db_session: DBSessionDep,
    youtube_client: YouTubeAPIDep,
    redis: ArqDep,
):
    """
    Creates a new YouTube channel in the application.
    - Fetches channel details from the YouTube Data API.
    - Stores the channel information in the database.
    """
    new_channel = await channel_service.create_channel(
        channel_data=channel_data, db_session=db_session, youtube_client=youtube_client
    )

    await redis.enqueue_job(
        "fetch_and_store_all_channel_videos_task",
        channel_id=new_channel.id,
    )

    return new_channel


@router.patch("/{channel_id}", response_model=ChannelOut)
async def update_channel(
    channel_id: str, payload: ChannelUpdate, db_session: DBSessionDep
):
    return await channel_service.update_channel(channel_id, payload, db_session)


@router.post("/{channel_id}/refresh", response_model=ChannelOut)
async def refresh_channel(
    channel_id: str, db_session: DBSessionDep, youtube_client: YouTubeAPIDep
):
    """
    Refresh the given YouTube channel to add and update the first 50 videos in its uploads playlist
    """
    return await channel_service.refresh_channel_by_id(
        channel_id, db_session, youtube_client
    )


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel(channel_id: str, db_session: DBSessionDep):
    """
    Deletes a single channel by its YouTube Channel ID.
    All associated videos will also be deleted.
    """
    await channel_service.delete_channel_by_id(channel_id, db_session)


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_channels(
    db_session: DBSessionDep,
    confirm: str = Query(
        ...,
        description="Must be exactly 'DELETE_ALL_CHANNELS' to confirm this destructive operation",
    ),
):
    """
    Deletes ALL channels from the database.
    This is a destructive operation intended for testing.

    Requires confirmation parameter: ?confirm=DELETE_ALL_CHANNELS
    """
    if confirm != "DELETE_ALL_CHANNELS":
        raise HTTPException(
            status_code=400,
            detail="Deletion not confirmed. Must provide ?confirm=DELETE_ALL_CHANNELS",
        )

    await channel_service.delete_all_channels(db_session)
