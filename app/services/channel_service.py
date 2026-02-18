import asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.base import PaginatedResponse

from ..clients.youtube import YouTubeAPI
from ..db.crud import crud_channel
from ..db.models.channel import Channel
from ..schemas.channel import ChannelCreate, ChannelUpdate, ChannelOut
from .video_service import refresh_latest_channel_videos


def _get_best_thumbnail_url(thumbnails: dict) -> str | None:
    """Helper to extract the best available thumbnail URL."""
    for quality in ["high", "medium", "default"]:
        if quality in thumbnails:
            return thumbnails[quality]["url"]
    return None


async def get_channel_by_id(
    channel_id: str, db_session: AsyncSession, owner_id: str = "test-user"
) -> Channel:
    """
    Retrieves a channel by its ID, raising a 404 error if not found.
    """
    channel = await crud_channel.get_channels(
        db_session, owner_id=owner_id, id=channel_id, first=True
    )
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


async def get_all_channels(
    db_session: AsyncSession,
    owner_id: str = "test-user",
    is_favorited: bool | None = None,
    folder_id: str | None = None,
    tag_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedResponse[ChannelOut]:
    """
    Retrieves all channels with optional filtering and pagination.

    Args:
        db_session: Database session
        is_favorited: Filter by favorited status
        folder_id: Filter by folder ID (use 0 for root/no folder)
        tag_id: Filter by tag ID
        limit: Number of items per page
        offset: Number of items to skip

    Returns:
        Dictionary with pagination metadata and channel items
    """
    # Build filter kwargs
    filters = {}
    if is_favorited is not None:
        filters["is_favorited"] = is_favorited
    if folder_id is not None:
        # Support folder_id=0 to mean "no folder" (None in database)
        filters["folder_id"] = None if folder_id == 0 else folder_id

    # Get ALL channels matching database filters first (no limit/offset yet)
    all_channels = await crud_channel.get_channels(
        db_session, owner_id=owner_id, **filters
    )

    # Post-filter for tag_id (since tags are a relationship, not a direct field)
    if tag_id is not None:
        all_channels = [
            c for c in all_channels if any(tag.id == tag_id for tag in c.tags)
        ]

    # Get total count after all filters
    total = len(all_channels)

    # Apply pagination manually
    paginated_channels = all_channels[offset : offset + limit]

    # Build pagination response
    return PaginatedResponse[ChannelOut](
        total=total,
        items=paginated_channels,
        limit=limit,
        offset=offset,
        has_more=offset + len(paginated_channels) < total,
    )


async def refresh_channel_by_id(
    channel_id: str,
    db_session: AsyncSession,
    youtube_client: YouTubeAPI,
    owner_id: str = "test-user",
) -> Channel:
    """
    Refresh the given channel to get its latest videos
    """
    channel = await crud_channel.get_channels(
        db_session, owner_id=owner_id, id=channel_id, first=True
    )
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    await refresh_latest_channel_videos(
        channel_id, db_session, youtube_client, owner_id=owner_id
    )

    return channel


async def create_channel(
    channel_data: ChannelCreate,
    db_session: AsyncSession,
    youtube_client: YouTubeAPI,
    owner_id: str = "test-user",
) -> Channel:
    """
    Orchestrates creating a new channel.
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

    existing_channel = await crud_channel.get_channels(
        db_session, owner_id=owner_id, id=channel_id, first=True
    )
    if existing_channel:
        raise HTTPException(
            status_code=409, detail="This channel has already been added."
        )

    # 3. Prepare and create the new channel in the database
    snippet = yt_channel_data.get("snippet", {})
    content_details = yt_channel_data.get("contentDetails", {})

    new_channel = Channel(
        owner_id=owner_id,
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
    channel_id: str,
    payload: ChannelUpdate,
    db_session: AsyncSession,
    owner_id: str = "test-user",
) -> Channel:
    """
    Updates a channel by its ID. Allows favoriting a channel, changing its folder, and managing tags.
    """
    channel = await crud_channel.get_channels(
        db_session, owner_id=owner_id, id=channel_id, first=True
    )
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Update simple fields
    if payload.is_favorited is not None:
        channel.is_favorited = payload.is_favorited
    if payload.folder_id is not None or payload.folder_id is None:
        channel.folder_id = payload.folder_id

    # Handle tag synchronization
    if payload.tag_ids is not None:
        from .tag_service import sync_entity_tags

        await sync_entity_tags(channel, payload.tag_ids, db_session, owner_id=owner_id)

    return await crud_channel.update_channel(db_session, channel)


async def delete_channel_by_id(
    channel_id: str, db_session: AsyncSession, owner_id: str = "test-user"
) -> None:
    """
    Deletes a channel by its ID. Verifies it exists first.
    """
    # First, get the channel to ensure it exists (this also handles the 404 case)
    channel_to_delete = await get_channel_by_id(channel_id, db_session, owner_id=owner_id)

    # Now, pass the object to the CRUD layer for deletion
    await crud_channel.delete_channel(db_session, channel_to_delete)


async def delete_all_channels(
    db_session: AsyncSession, owner_id: str = "test-user"
) -> int:
    """
    Deletes all channels and returns the number of channels deleted.
    """
    return await crud_channel.delete_all_channels(db_session, owner_id=owner_id)
