from fastapi import APIRouter, status, Query, HTTPException
from ..dependencies import DBSessionDep, YouTubeAPIDep, ArqDep
from ..schemas.channel import ChannelCreate, ChannelOut, ChannelUpdate
from ..services import channel_service

router = APIRouter(prefix="/channels", tags=["Channels"])


@router.get("/", response_model=list[ChannelOut])
async def read_all_channels(db_session: DBSessionDep):
    """
    Retrieves a list of all channels stored in the database.
    """
    return await channel_service.get_all_channels(db_session)


@router.get("/{channel_id}", response_model=ChannelOut)
async def read_channel_by_id(channel_id: str, db_session: DBSessionDep):
    """
    Retrieves a single channel by its YouTube Channel ID.
    """
    return await channel_service.get_channel_by_id(channel_id, db_session)


@router.post("/", response_model=ChannelOut, status_code=status.HTTP_201_CREATED)
async def create_new_channel(
    channel_data: ChannelCreate,
    db_session: DBSessionDep,
    youtube_client: YouTubeAPIDep,
    redis: ArqDep,
):
    """
    Adds a new YouTube channel to the application.
    - Fetches channel details from the YouTube Data API.
    - Stores the channel information in the database.
    """
    new_channel = await channel_service.add_new_channel(
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
async def delete_channel_by_id(channel_id: str, db_session: DBSessionDep):
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
        description="Must be exactly 'DELETE_ALL_CHANNELS' to confirm this destructive operation"
    )
):
    """
    Deletes ALL channels from the database.
    This is a destructive operation intended for testing.

    Requires confirmation parameter: ?confirm=DELETE_ALL_CHANNELS
    """
    if confirm != "DELETE_ALL_CHANNELS":
        raise HTTPException(
            status_code=400,
            detail="Deletion not confirmed. Must provide ?confirm=DELETE_ALL_CHANNELS"
        )

    await channel_service.delete_all_channels(db_session)
