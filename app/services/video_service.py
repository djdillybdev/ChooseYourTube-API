import re
import feedparser

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime, timedelta
from ..core.config import settings
from ..schemas.video import VideoCreate
from ..db.session import sessionmanager
from ..db.crud import crud_channel, crud_video
from ..db.models.video import Video
from ..clients.youtube import YouTubeAPI

INITIAL_VIDEO_FETCH_LIMIT = 1000
VIDEO_BATCH_SIZE = 500

YT_RSS_BASE_URL = "https://www.youtube.com/feeds/videos.xml?channel_id="

# Configurable with safe fallbacks
SHORTS_MAX_SECONDS = getattr(
    settings, "SHORTS_MAX_SECONDS", 180
)  # Shorts can be up to 3 minutes now
SHORTS_DEFAULT_TO_SHORT = getattr(settings, "SHORTS_DEFAULT_TO_SHORT", True)

_SHORTS_TAG_PATTERN = re.compile(r"(?<!\w)#?shorts?\b", re.IGNORECASE)


def parse_iso8601_duration(duration_string: str) -> int:
    """
    Parses an ISO 8601 duration string (e.g., PT4M13S) into seconds.
    """
    if not duration_string or duration_string == "P0D":
        return 0

    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration_string)
    if not match:
        return 0

    hours = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2)) if match.group(2) else 0
    seconds = int(match.group(3)) if match.group(3) else 0

    return int(timedelta(hours=hours, minutes=minutes, seconds=seconds).total_seconds())


def _get_best_thumbnail_url(thumbnails: dict) -> str | None:
    """Helper to extract the best available thumbnail URL."""
    for quality in ["high", "medium", "default"]:
        if quality in thumbnails:
            return thumbnails[quality]["url"]
    return None


# async def _is_short(video_id: str) -> bool:
#     url = 'https://www.youtube.com/shorts/' + video_id
#     async with httpx.AsyncClient() as client:
#         response = await client.get(url)
#     return response.status_code == 200


def _has_shorts_text_cues(snippet: dict) -> bool:
    """Detect #short / #shorts in title, description, or tags."""
    title = snippet.get("title") or ""
    desc = snippet.get("description") or ""
    tags = snippet.get("tags") or []
    if _SHORTS_TAG_PATTERN.search(title) or _SHORTS_TAG_PATTERN.search(desc):
        return True
    for t in tags:
        if _SHORTS_TAG_PATTERN.search(str(t) if t is not None else ""):
            return True
    return False


def _classify_is_short(duration_seconds: int, snippet: dict) -> bool:
    """
    API-only heuristic:
    - If duration > SHORTS_MAX_SECONDS ⇒ not a Short.
    - If #short(s) present ⇒ Short.
    - Otherwise (≤ SHORTS_MAX_SECONDS, no cues) ⇒ default via SHORTS_DEFAULT_TO_SHORT.
    """
    duration_seconds = duration_seconds or 0
    if duration_seconds > SHORTS_MAX_SECONDS:
        return False
    if _has_shorts_text_cues(snippet):
        return True
    return SHORTS_DEFAULT_TO_SHORT  # ambiguous case


async def fetch_and_store_all_channel_videos_task(ctx, channel_id: str):
    """
    Background TASK to fetch all videos. Accepts a channel_id.
    Manages its own DB session and YouTube client.
    """
    print(f"Starting background video fetch for channel ID: {channel_id}")

    youtube_client = YouTubeAPI(api_key=settings.YOUTUBE_API_KEY)

    async with sessionmanager.session() as db_session:
        channel = await crud_channel.get_channels(db_session, id=channel_id, first=True)
        if not channel:
            print(f"Channel {channel_id} not found in DB. Exiting task.")
            return

        uploaded_videos = []
        next_page_token = None
        print("get playlists items")
        while len(uploaded_videos) < INITIAL_VIDEO_FETCH_LIMIT:
            response = await youtube_client.playlist_items_list_async(
                part="snippet,contentDetails",
                playlistId=channel.uploads_playlist_id,
                maxResults=50,
                pageToken=next_page_token,
            )
            items = response.get("items", [])

            if not items:
                break

            uploaded_videos.extend(items)

            next_page_token = response.get("nextPageToken")

            if not next_page_token:
                break

        video_ids = []

        for video_item in uploaded_videos:
            snippet = video_item.get("snippet", {})
            content_details = video_item.get("contentDetails", {})
            video_id = content_details.get("videoId")
            if not video_id:
                # Sometimes "contentDetails" may not have a videoId (rare, but could happen)
                resource_id = snippet.get("resourceId", {})
                video_id = resource_id.get("videoId")

            video_ids.append(video_id)

        # De-duplicate while preserving order
        seen = set()
        video_ids = [v for v in video_ids if not (v in seen or seen.add(v))]

        if not video_ids:
            print("No video IDs found. Exiting task.")
            return

        await create_and_update_videos(
            video_ids, channel_id, db_session, youtube_client
        )


async def refresh_latest_channel_videos_task(ctx, channel_id: str):
    """
    Background TASK to fetch and add the latest videos for a channel
    """
    print(f"Starting background refresh new videos fetch for channel ID: {channel_id}")

    youtube_client = YouTubeAPI(api_key=settings.YOUTUBE_API_KEY)

    async with sessionmanager.session() as db_session:
        await refresh_latest_channel_videos(channel_id, db_session, youtube_client)


async def refresh_latest_channel_videos(
    channel_id: str, db_session: AsyncSession, youtube_client: YouTubeAPI
):
    """
    Fetch and add the latest videos for a channel
    """

    # first, check the RSS feed for a channel to see if there have been updates
    channel_rss = YT_RSS_BASE_URL + channel_id
    parsed_feed_data = feedparser.parse(channel_rss)

    parsed_video_ids = []
    # can maybe parse out shorts here to ignore new shorts being added, but again it is tough to in any other method

    video_entries = parsed_feed_data.entries
    for entry in video_entries:
        video_id = entry.yt_videoid
        if "shorts" not in entry.link:
            parsed_video_ids.append(video_id)

    total_parsed_videos = len(parsed_video_ids)

    seen_video_ids = []
    latest_videos = await crud_video.get_videos(db_session, channel_id=channel_id)
    for video in latest_videos:
        if video.id in parsed_video_ids:
            seen_video_ids.append(video.id)

    video_ids_to_update = []

    if len(seen_video_ids) == total_parsed_videos:
        return
    if len(seen_video_ids) == 0:
        channel = await crud_channel.get_channels(db_session, id=channel_id, first=True)
        if not channel:
            print(f"Channel {channel_id} not found in DB. Exiting task.")
            return

        response = await youtube_client.playlist_items_list_async(
            part="snippet,contentDetails",
            playlistId=channel.uploads_playlist_id,
            maxResults=50,
        )
        items = response.get("items", [])

        for video_item in items:
            snippet = video_item.get("snippet", {})
            content_details = video_item.get("contentDetails", {})
            video_id = content_details.get("videoId")
            if not video_id:
                # Sometimes "contentDetails" may not have a videoId (rare, but could happen)
                resource_id = snippet.get("resourceId", {})
                video_id = resource_id.get("videoId")

            video_ids_to_update.append(video_id)

    else:
        video_ids_to_update = parsed_video_ids

    await create_and_update_videos(
        video_ids_to_update, channel_id, db_session, youtube_client
    )


async def create_and_update_videos(
    video_ids: list[str],
    channel_id: str,
    db_session: AsyncSession,
    youtube_client: YouTubeAPI,
):
    full_video_items = []
    print("get video items")
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        response = await youtube_client.videos_list_async(
            part="snippet,contentDetails", id=",".join(chunk)
        )
        items = response.get("items", [])
        full_video_items.extend(items)

    videos_to_create = []

    for video_item in full_video_items:
        snippet = video_item.get("snippet", {})
        content_details = video_item.get("contentDetails", {})
        video_id = video_item.get("id")
        if not video_id:
            continue
        duration_seconds = parse_iso8601_duration(content_details.get("duration"))

        is_short = _classify_is_short(duration_seconds, snippet)

        new_video = VideoCreate(
            id=video_id,
            channel_id=channel_id,
            title=snippet.get("title"),
            description=snippet.get("description"),
            thumbnail_url=_get_best_thumbnail_url(snippet.get("thumbnails", {})),
            published_at=datetime.fromisoformat(
                snippet.get("publishedAt").replace("Z", "+00:00")
            ),
            duration_seconds=duration_seconds,
            is_short=is_short,
            yt_tags=snippet.get("tags", []),
        )

        videos_to_create.append(new_video)

    if videos_to_create:
        print("add videos to db")
        await crud_video.create_videos_bulk(db_session, videos_to_create)
        print("job success")


async def get_video_by_id(video_id: str, db_session: AsyncSession) -> Video:
    video = await crud_video.get_videos(db_session, id=video_id, first=True)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


async def get_all_videos(
    db_session: AsyncSession, limit: int = 50, offset: int = 0
) -> list[Video]:
    return await crud_video.get_videos(db_session, limit=limit, offset=offset)


async def get_videos_for_channel(
    channel_id: str, db_session: AsyncSession, limit: int = 50, offset: int = 0
) -> list[Video]:
    return await crud_video.get_videos(
        db_session, channel_id=channel_id, limit=limit, offset=offset
    )
