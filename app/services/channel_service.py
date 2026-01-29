import asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..clients.youtube import YouTubeAPI
from ..db.crud import crud_channel
from ..db.models.channel import Channel
from ..schemas.channel import ChannelCreate, ChannelUpdate
from .video_service import refresh_latest_channel_videos


def _get_best_thumbnail_url(thumbnails: dict) -> str | None:
    """Helper to extract the best available thumbnail URL."""
    for quality in ["high", "medium", "default"]:
        if quality in thumbnails:
            return thumbnails[quality]["url"]
    return None


async def get_channel_by_id(channel_id: str, db_session: AsyncSession) -> Channel:
    """
    Retrieves a channel by its ID, raising a 404 error if not found.
    """
    channel = await crud_channel.get_channels(db_session, id=channel_id, first=True)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


async def get_all_channels(db_session: AsyncSession) -> list[Channel]:
    """
    Retrieves all channels.
    """
    return await crud_channel.get_channels(db_session)


async def refresh_channel_by_id(
    channel_id: str, db_session: AsyncSession, youtube_client: YouTubeAPI
) -> Channel:
    """
    Refresh the given channel to get its latest videos
    """
    channel = await crud_channel.get_channels(db_session, id=channel_id, first=True)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    await refresh_latest_channel_videos(channel_id, db_session, youtube_client)

    return channel


async def add_new_channel(
    channel_data: ChannelCreate, db_session: AsyncSession, youtube_client: YouTubeAPI
) -> Channel:
    """
    Orchestrates adding a new channel.
    1. Fetches data from YouTube API.
    2. Checks if channel already exists.
    3. Creates the channel in the database.
    """
    # 1. Fetch data from YouTube API using an async thread
    channel_data.handle = channel_data.handle.lstrip("@")
    try:
        response = await asyncio.to_thread(
            youtube_client.get_channel_info, handle=channel_data.handle
        )
        items = response.get("items", [])
        if not items:
            raise HTTPException(
                status_code=404,
                detail=f"Channel with handle '{channel_data.handle}' not found on YouTube.",
            )
    except Exception as e:
        # Handle potential googleapiclient errors
        raise HTTPException(
            status_code=500, detail=f"An error occurred with the YouTube API: {e}"
        )

    # 2. Extract data and check if channel already exists in our DB
    yt_channel_data = items[0]
    channel_id = yt_channel_data["id"]

    existing_channel = await crud_channel.get_channels(db_session, id=channel_id, first=True)
    if existing_channel:
        raise HTTPException(
            status_code=409, detail="This channel has already been added."
        )

    # 3. Prepare and create the new channel in the database
    snippet = yt_channel_data.get("snippet", {})
    content_details = yt_channel_data.get("contentDetails", {})

    new_channel = Channel(
        id=channel_id,
        title=snippet.get("title"),
        handle=channel_data.handle,  # Use the handle provided by the user
        description=snippet.get("description"),
        thumbnail_url=_get_best_thumbnail_url(snippet.get("thumbnails", {})),
        uploads_playlist_id=content_details.get("relatedPlaylists", {}).get("uploads"),
        folder_id=channel_data.folder_id,
    )

    return await crud_channel.create_channel(db_session, new_channel)


async def update_channel(
    channel_id: str, payload: ChannelUpdate, db_session: AsyncSession
) -> Channel:
    """
    Updates a channel by its ID. Allows favoriting a channel and changing its folder.
    """
    channel = await crud_channel.get_channels(db_session, id=channel_id, first=True)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    if payload.is_favorited is not None:
        channel.is_favorited = payload.is_favorited
    if payload.folder_id is not None or payload.folder_id is None:
        channel.folder_id = payload.folder_id
    return await crud_channel.update_channel(db_session, channel)


async def delete_channel_by_id(channel_id: str, db_session: AsyncSession) -> None:
    """
    Deletes a channel by its ID. Verifies it exists first.
    """
    # First, get the channel to ensure it exists (this also handles the 404 case)
    channel_to_delete = await get_channel_by_id(channel_id, db_session)

    # Now, pass the object to the CRUD layer for deletion
    await crud_channel.delete_channel(db_session, channel_to_delete)


async def delete_all_channels(db_session: AsyncSession) -> int:
    """
    Deletes all channels and returns the number of channels deleted.
    """
    return await crud_channel.delete_all_channels(db_session)
