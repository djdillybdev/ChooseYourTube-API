"""Tests for channel playlist sync and listing service."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from app.db.crud.crud_playlist import get_playlist_video_ids
from app.db.models.channel import Channel
from app.db.models.playlist import Playlist
from app.db.models.video import Video
from app.services.channel_playlist_service import (
    get_channel_playlists,
    sync_channel_playlists,
)


@pytest_asyncio.fixture
async def sample_channel(db_session):
    channel = Channel(
        id="UC_sync_channel",
        handle="syncchannel",
        title="Sync Channel",
        uploads_playlist_id="UU_sync_channel",
    )
    db_session.add(channel)
    await db_session.commit()
    await db_session.refresh(channel)
    return channel


@pytest_asyncio.fixture
async def sample_other_channel(db_session):
    channel = Channel(
        id="UC_other_channel",
        handle="otherchannel",
        title="Other Channel",
        uploads_playlist_id="UU_other_channel",
    )
    db_session.add(channel)
    await db_session.commit()
    await db_session.refresh(channel)
    return channel


@pytest_asyncio.fixture
async def sample_channel_videos(db_session, sample_channel):
    v1 = Video(
        id="sync_v1",
        channel_id=sample_channel.id,
        title="Sync V1",
        published_at=datetime.now(timezone.utc),
        duration_seconds=120,
        is_short=False,
    )
    v2 = Video(
        id="sync_v2",
        channel_id=sample_channel.id,
        title="Sync V2",
        published_at=datetime.now(timezone.utc),
        duration_seconds=240,
        is_short=False,
    )
    db_session.add(v1)
    db_session.add(v2)
    await db_session.commit()


@pytest_asyncio.fixture
async def sample_off_channel_video(db_session, sample_other_channel):
    v = Video(
        id="off_channel_v1",
        channel_id=sample_other_channel.id,
        title="Off Channel",
        published_at=datetime.now(timezone.utc),
        duration_seconds=300,
        is_short=False,
    )
    db_session.add(v)
    await db_session.commit()


@pytest.mark.asyncio
class TestSyncChannelPlaylists:
    async def test_sync_filters_and_orders_channel_videos(
        self,
        db_session,
        sample_channel,
        sample_other_channel,
        sample_channel_videos,
        sample_off_channel_video,
    ):
        stale = Playlist(
            id="stale_playlist",
            name="Stale",
            is_system=True,
            source_type="channel",
            source_channel_id=sample_channel.id,
            source_youtube_playlist_id="PL_STALE",
            source_is_active=True,
        )
        db_session.add(stale)
        await db_session.commit()

        youtube_client = MagicMock()
        youtube_client.playlists_list_async = AsyncMock(
            return_value={
                "items": [
                    {
                        "id": "PL_KEEP",
                        "snippet": {
                            "title": "Keep Playlist",
                            "description": "desc",
                            "thumbnails": {"high": {"url": "https://example.com/pl.jpg"}},
                        },
                    },
                    {
                        "id": "PL_DROP",
                        "snippet": {
                            "title": "Drop Playlist",
                            "description": "drop",
                            "thumbnails": {},
                        },
                    },
                ]
            }
        )

        youtube_client.playlist_items_list_async = AsyncMock(
            side_effect=[
                {
                    "items": [
                        {
                            "snippet": {"videoOwnerChannelId": sample_channel.id},
                            "contentDetails": {"videoId": "missing_video"},
                        },
                        {
                            "snippet": {"videoOwnerChannelId": sample_other_channel.id},
                            "contentDetails": {"videoId": "off_channel_v1"},
                        },
                        {
                            "snippet": {"videoOwnerChannelId": sample_channel.id},
                            "contentDetails": {"videoId": "sync_v2"},
                        },
                        {
                            "snippet": {"videoOwnerChannelId": sample_channel.id},
                            "contentDetails": {"videoId": "sync_v1"},
                        },
                    ]
                },
                {
                    "items": [
                        {
                            "snippet": {"videoOwnerChannelId": sample_other_channel.id},
                            "contentDetails": {"videoId": "off_channel_v1"},
                        }
                    ]
                },
            ]
        )

        await sync_channel_playlists(
            channel_id=sample_channel.id,
            db_session=db_session,
            youtube_client=youtube_client,
        )

        playlists = await get_channel_playlists(
            channel_id=sample_channel.id,
            db_session=db_session,
            owner_id="test-user",
            include_inactive=True,
        )

        assert playlists.total == 2
        active = [p for p in playlists.items if p.source_is_active]
        inactive = [p for p in playlists.items if not p.source_is_active]

        assert len(active) == 1
        assert active[0].source_youtube_playlist_id == "PL_KEEP"
        assert active[0].thumbnail_url == "https://example.com/pl.jpg"
        assert active[0].is_system is True

        video_ids = await get_playlist_video_ids(
            db_session, active[0].id, owner_id="test-user"
        )
        assert video_ids == ["sync_v2", "sync_v1"]

        assert len(inactive) == 1
        assert inactive[0].source_youtube_playlist_id == "PL_STALE"

    async def test_list_hides_inactive_by_default(self, db_session, sample_channel):
        active = Playlist(
            id="active_channel_playlist",
            name="Active",
            is_system=True,
            source_type="channel",
            source_channel_id=sample_channel.id,
            source_youtube_playlist_id="PL_ACTIVE",
            source_is_active=True,
        )
        inactive = Playlist(
            id="inactive_channel_playlist",
            name="Inactive",
            is_system=True,
            source_type="channel",
            source_channel_id=sample_channel.id,
            source_youtube_playlist_id="PL_INACTIVE",
            source_is_active=False,
        )
        db_session.add(active)
        db_session.add(inactive)
        await db_session.commit()

        visible = await get_channel_playlists(
            channel_id=sample_channel.id,
            db_session=db_session,
            owner_id="test-user",
        )
        all_items = await get_channel_playlists(
            channel_id=sample_channel.id,
            db_session=db_session,
            owner_id="test-user",
            include_inactive=True,
        )

        assert visible.total == 1
        assert visible.items[0].source_youtube_playlist_id == "PL_ACTIVE"
        assert all_items.total == 2
