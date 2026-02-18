from __future__ import annotations

from datetime import datetime, timezone
import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.youtube import YouTubeAPI
from app.core.config import settings
from app.db.crud import crud_channel, crud_playlist, crud_video
from app.db.models.playlist import Playlist
from app.db.session import sessionmanager
from app.schemas.base import PaginatedResponse
from app.schemas.playlist import ChannelPlaylistOut

CHANNEL_PLAYLISTS_SYNC_MAX_PLAYLISTS = getattr(
    settings, "CHANNEL_PLAYLISTS_SYNC_MAX_PLAYLISTS", 100
)
CHANNEL_PLAYLISTS_SYNC_MAX_ITEMS_PER_PLAYLIST = getattr(
    settings, "CHANNEL_PLAYLISTS_SYNC_MAX_ITEMS_PER_PLAYLIST", 500
)


def _get_best_thumbnail_url(thumbnails: dict) -> str | None:
    for quality in ["high", "medium", "default"]:
        if quality in thumbnails:
            return thumbnails[quality].get("url")
    return None


async def _fetch_channel_playlists(
    youtube_client: YouTubeAPI,
    channel_id: str,
) -> list[dict]:
    playlists: list[dict] = []
    page_token: str | None = None

    while len(playlists) < CHANNEL_PLAYLISTS_SYNC_MAX_PLAYLISTS:
        response = await youtube_client.playlists_list_async(
            part="snippet,contentDetails",
            channelId=channel_id,
            maxResults=50,
            pageToken=page_token,
        )
        items = response.get("items", [])
        if not items:
            break

        playlists.extend(items)
        if len(playlists) >= CHANNEL_PLAYLISTS_SYNC_MAX_PLAYLISTS:
            playlists = playlists[:CHANNEL_PLAYLISTS_SYNC_MAX_PLAYLISTS]
            break

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return playlists


async def _fetch_playlist_video_ids(
    youtube_client: YouTubeAPI, playlist_id: str
) -> list[tuple[str, str | None]]:
    playlist_video_ids: list[str] = []
    page_token: str | None = None

    while len(playlist_video_ids) < CHANNEL_PLAYLISTS_SYNC_MAX_ITEMS_PER_PLAYLIST:
        response = await youtube_client.playlist_items_list_async(
            part="snippet,contentDetails",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=page_token,
        )
        items = response.get("items", [])
        if not items:
            break

        for item in items:
            snippet = item.get("snippet", {})
            content_details = item.get("contentDetails", {})

            video_id = content_details.get("videoId")
            if not video_id:
                video_id = snippet.get("resourceId", {}).get("videoId")
            if not video_id:
                continue

            # Keep only videos belonging to this channel playlist owner.
            owner_channel_id = snippet.get("videoOwnerChannelId") or snippet.get(
                "channelId"
            )
            playlist_video_ids.append((video_id, owner_channel_id))

        if len(playlist_video_ids) >= CHANNEL_PLAYLISTS_SYNC_MAX_ITEMS_PER_PLAYLIST:
            playlist_video_ids = playlist_video_ids[
                :CHANNEL_PLAYLISTS_SYNC_MAX_ITEMS_PER_PLAYLIST
            ]
            break

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return playlist_video_ids


async def sync_channel_playlists(
    channel_id: str,
    db_session: AsyncSession,
    youtube_client: YouTubeAPI,
    owner_id: str = "test-user",
) -> None:
    channel = await crud_channel.get_channels(
        db_session, owner_id=owner_id, id=channel_id, first=True
    )
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    now = datetime.now(timezone.utc)
    active_playlist_source_ids: set[str] = set()

    yt_playlists = await _fetch_channel_playlists(youtube_client, channel_id)

    for yt_playlist in yt_playlists:
        yt_playlist_id = yt_playlist.get("id")
        if not yt_playlist_id:
            continue

        snippet = yt_playlist.get("snippet", {})
        ordered_items = await _fetch_playlist_video_ids(youtube_client, yt_playlist_id)

        channel_owned_ids = [
            video_id
            for video_id, owner_channel in ordered_items
            if owner_channel == channel_id
        ]
        if not channel_owned_ids:
            continue

        existing_videos = await crud_video.get_videos(
            db_session, owner_id=owner_id, id=channel_owned_ids
        )
        existing_same_channel_ids = {
            video.id for video in existing_videos if video.channel_id == channel_id
        }

        filtered_video_ids = [
            video_id
            for video_id in channel_owned_ids
            if video_id in existing_same_channel_ids
        ]

        if not filtered_video_ids:
            continue

        playlist = await crud_playlist.get_playlists(
            db_session,
            owner_id=owner_id,
            source_type="channel",
            source_youtube_playlist_id=yt_playlist_id,
            first=True,
        )
        if not playlist:
            playlist = Playlist(
                id=str(uuid.uuid4()),
                owner_id=owner_id,
                name=snippet.get("title") or "Untitled Playlist",
                description=snippet.get("description"),
                thumbnail_url=_get_best_thumbnail_url(snippet.get("thumbnails", {})),
                is_system=True,
                source_type="channel",
                source_channel_id=channel_id,
                source_youtube_playlist_id=yt_playlist_id,
                source_is_active=True,
                source_last_synced_at=now,
            )
            playlist = await crud_playlist.create_playlist(db_session, playlist)
        else:
            playlist.name = snippet.get("title") or playlist.name
            playlist.description = snippet.get("description")
            playlist.thumbnail_url = _get_best_thumbnail_url(
                snippet.get("thumbnails", {})
            )
            playlist.is_system = True
            playlist.source_type = "channel"
            playlist.source_channel_id = channel_id
            playlist.source_youtube_playlist_id = yt_playlist_id
            playlist.source_is_active = True
            playlist.source_last_synced_at = now

        await crud_playlist.set_playlist_videos(
            db_session,
            playlist.id,
            filtered_video_ids,
            owner_id=owner_id,
        )
        active_playlist_source_ids.add(yt_playlist_id)

    existing_channel_playlists = await crud_playlist.get_playlists(
        db_session,
        owner_id=owner_id,
        source_type="channel",
        source_channel_id=channel_id,
    )

    needs_commit = False
    for existing in existing_channel_playlists:
        if existing.source_youtube_playlist_id not in active_playlist_source_ids:
            existing.source_is_active = False
            existing.source_last_synced_at = now
            db_session.add(existing)
            needs_commit = True

    if needs_commit:
        await db_session.commit()


async def get_channel_playlists(
    channel_id: str,
    db_session: AsyncSession,
    owner_id: str = "test-user",
    include_inactive: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedResponse[ChannelPlaylistOut]:
    channel = await crud_channel.get_channels(
        db_session, owner_id=owner_id, id=channel_id, first=True
    )
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    source_is_active = None if include_inactive else True

    total = await crud_playlist.count_playlists(
        db_session,
        owner_id=owner_id,
        source_type="channel",
        source_channel_id=channel_id,
        source_is_active=source_is_active,
    )

    playlists = await crud_playlist.get_playlists(
        db_session,
        owner_id=owner_id,
        source_type="channel",
        source_channel_id=channel_id,
        source_is_active=source_is_active,
        limit=limit,
        offset=offset,
        order_by="name",
        order_direction="asc",
    )

    items: list[ChannelPlaylistOut] = []
    for playlist in playlists:
        video_ids = await crud_playlist.get_playlist_video_ids(
            db_session, playlist.id, owner_id=owner_id
        )
        items.append(
            ChannelPlaylistOut(
                id=playlist.id,
                name=playlist.name,
                description=playlist.description,
                thumbnail_url=playlist.thumbnail_url,
                is_system=playlist.is_system,
                source_type=playlist.source_type,
                source_channel_id=playlist.source_channel_id,
                source_youtube_playlist_id=playlist.source_youtube_playlist_id,
                source_is_active=playlist.source_is_active,
                source_last_synced_at=playlist.source_last_synced_at,
                total_videos=len(video_ids),
                created_at=playlist.created_at,
            )
        )

    return PaginatedResponse[ChannelPlaylistOut](
        total=total,
        items=items,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


async def sync_channel_playlists_task(
    ctx, channel_id: str, owner_id: str = "test-user"
):
    youtube_client = YouTubeAPI(api_key=settings.YOUTUBE_API_KEY)
    async with sessionmanager.session() as db_session:
        await sync_channel_playlists(
            channel_id=channel_id,
            db_session=db_session,
            youtube_client=youtube_client,
            owner_id=owner_id,
        )
