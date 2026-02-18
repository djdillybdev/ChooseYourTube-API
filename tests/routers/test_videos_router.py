"""
Tests for videos router endpoints.

Tests the API endpoints for video management, including
listing videos, filtering by channel, and pagination.
"""

import pytest
from datetime import datetime, timezone


@pytest.mark.asyncio
class TestVideosRouter:
    """Test videos router endpoints."""

    async def test_list_videos_empty(self, test_client, db_session):
        """Test GET /videos/ returns empty list when no videos exist."""
        response = test_client.get("/videos/")

        assert response.status_code == 200
        assert response.json()["total"] == 0

    async def test_list_videos_with_data(self, test_client, db_session):
        """Test GET /videos/ returns list of videos."""
        from app.db.models.channel import Channel
        from app.db.models.video import Video

        # Create channel
        channel = Channel(
            id="UC_test_channel",
            handle="testchannel",
            title="Test Channel",
            uploads_playlist_id="UU_test",
        )
        db_session.add(channel)
        await db_session.commit()

        # Create videos
        video1 = Video(
            id="video_1",
            channel_id=channel.id,
            title="Video 1",
            description="Description 1",
            published_at=datetime.now(timezone.utc),
            duration_seconds=300,
            is_short=False,
        )
        video2 = Video(
            id="video_2",
            channel_id=channel.id,
            title="Video 2",
            description="Description 2",
            published_at=datetime.now(timezone.utc),
            duration_seconds=45,
            is_short=True,
        )
        db_session.add(video1)
        db_session.add(video2)
        await db_session.commit()

        response = test_client.get("/videos/")

        assert response.status_code == 200
        data = response.json()
        data = data["items"]
        assert len(data) == 2

    async def test_list_videos_with_pagination(self, test_client, db_session):
        """Test GET /videos/ with pagination parameters."""
        from app.db.models.channel import Channel
        from app.db.models.video import Video

        # Create channel
        channel = Channel(
            id="UC_pagination_test",
            handle="paginationtest",
            title="Pagination Test",
            uploads_playlist_id="UU_pagination",
        )
        db_session.add(channel)
        await db_session.commit()

        # Create 5 videos
        for i in range(5):
            video = Video(
                id=f"video_{i}",
                channel_id=channel.id,
                title=f"Video {i}",
                description=f"Description {i}",
                published_at=datetime.now(timezone.utc),
                duration_seconds=300,
                is_short=False,
            )
            db_session.add(video)
        await db_session.commit()

        # Test with limit
        response = test_client.get("/videos/?limit=2")
        assert response.status_code == 200
        data = response.json()
        data = data["items"]
        assert len(data) == 2

        # Test with offset
        response = test_client.get("/videos/?limit=2&offset=2")
        assert response.status_code == 200
        data = response.json()
        data = data["items"]
        assert len(data) == 2

    async def test_list_videos_pagination_limits(self, test_client, db_session):
        """Test GET /videos/ pagination limit constraints."""
        # Test minimum limit (1)
        response = test_client.get("/videos/?limit=1")
        assert response.status_code == 200

        # Test maximum limit (200)
        response = test_client.get("/videos/?limit=200")
        assert response.status_code == 200

        # Test invalid limit (< 1)
        response = test_client.get("/videos/?limit=0")
        assert response.status_code == 422  # Validation error

        # Test invalid limit (> 200)
        response = test_client.get("/videos/?limit=201")
        assert response.status_code == 422  # Validation error

    async def test_get_video_by_id_success(self, test_client, db_session):
        """Test GET /videos/{id} returns video by ID."""
        from app.db.models.channel import Channel
        from app.db.models.video import Video

        # Create channel
        channel = Channel(
            id="UC_video_by_id",
            handle="videobyid",
            title="Video By ID",
            uploads_playlist_id="UU_video_by_id",
        )
        db_session.add(channel)
        await db_session.commit()

        # Create video
        video = Video(
            id="specific_video_id",
            channel_id=channel.id,
            title="Specific Video",
            description="Specific Description",
            published_at=datetime.now(timezone.utc),
            duration_seconds=600,
            is_short=False,
        )
        db_session.add(video)
        await db_session.commit()

        response = test_client.get("/videos/specific_video_id")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "specific_video_id"
        assert data["title"] == "Specific Video"
        assert data["duration_seconds"] == 600

    async def test_get_video_by_id_not_found(self, test_client, db_session):
        """Test GET /videos/{id} returns 404 for non-existent video."""
        response = test_client.get("/videos/nonexistent_video")

        assert response.status_code == 404

    async def test_list_videos_by_channel(self, test_client, db_session):
        """Test GET /videos/by-channel/{channel_id} filters by channel."""
        from app.db.models.channel import Channel
        from app.db.models.video import Video

        # Create two channels
        channel1 = Channel(
            id="UC_channel_1",
            handle="channel1",
            title="Channel 1",
            uploads_playlist_id="UU_channel_1",
        )
        channel2 = Channel(
            id="UC_channel_2",
            handle="channel2",
            title="Channel 2",
            uploads_playlist_id="UU_channel_2",
        )
        db_session.add(channel1)
        db_session.add(channel2)
        await db_session.commit()

        # Create videos for both channels
        video1 = Video(
            id="video_channel1_1",
            channel_id=channel1.id,
            title="Channel 1 Video",
            description="Description",
            published_at=datetime.now(timezone.utc),
            duration_seconds=300,
            is_short=False,
        )
        video2 = Video(
            id="video_channel2_1",
            channel_id=channel2.id,
            title="Channel 2 Video",
            description="Description",
            published_at=datetime.now(timezone.utc),
            duration_seconds=300,
            is_short=False,
        )
        db_session.add(video1)
        db_session.add(video2)
        await db_session.commit()

        # Get videos for channel 1
        response = test_client.get("/videos/by-channel/UC_channel_1")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["channel_id"] == "UC_channel_1"

    async def test_list_videos_by_channel_with_pagination(
        self, test_client, db_session
    ):
        """Test GET /videos/by-channel/{channel_id} with pagination."""
        from app.db.models.channel import Channel
        from app.db.models.video import Video

        # Create channel
        channel = Channel(
            id="UC_pagination_by_channel",
            handle="paginationbychannel",
            title="Pagination By Channel",
            uploads_playlist_id="UU_pagination_by_channel",
        )
        db_session.add(channel)
        await db_session.commit()

        # Create 10 videos for this channel
        for i in range(10):
            video = Video(
                id=f"video_paginated_{i}",
                channel_id=channel.id,
                title=f"Video {i}",
                description=f"Description {i}",
                published_at=datetime.now(timezone.utc),
                duration_seconds=300,
                is_short=False,
            )
            db_session.add(video)
        await db_session.commit()

        # Test with limit
        response = test_client.get(
            "/videos/by-channel/UC_pagination_by_channel?limit=5"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5

        # Test with offset
        response = test_client.get(
            "/videos/by-channel/UC_pagination_by_channel?limit=5&offset=5"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5

    async def test_list_videos_by_nonexistent_channel(self, test_client, db_session):
        """Test GET /videos/by-channel/{channel_id} with non-existent channel returns empty."""
        response = test_client.get("/videos/by-channel/UC_nonexistent")

        assert response.status_code == 200
        assert response.json() == []

    async def test_list_videos_search_q_param(self, test_client, db_session):
        """Test GET /videos/?q=... returns matching videos."""
        from app.db.models.channel import Channel
        from app.db.models.video import Video

        channel = Channel(
            id="UC_search_test",
            handle="searchtest",
            title="Search Test Channel",
            uploads_playlist_id="UU_search_test",
        )
        db_session.add(channel)
        await db_session.commit()

        video1 = Video(
            id="search_vid_1",
            channel_id=channel.id,
            title="Python Tutorial for Beginners",
            description="Learn Python",
            published_at=datetime.now(timezone.utc),
            duration_seconds=600,
            is_short=False,
        )
        video2 = Video(
            id="search_vid_2",
            channel_id=channel.id,
            title="JavaScript Basics",
            description="Learn JavaScript",
            published_at=datetime.now(timezone.utc),
            duration_seconds=500,
            is_short=False,
        )
        video3 = Video(
            id="search_vid_3",
            channel_id=channel.id,
            title="Advanced React Patterns",
            description="Deep dive into React",
            published_at=datetime.now(timezone.utc),
            duration_seconds=900,
            is_short=False,
        )
        db_session.add_all([video1, video2, video3])
        await db_session.commit()

        response = test_client.get("/videos/?q=Python")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == "search_vid_1"

    async def test_list_videos_search_pagination_accurate(
        self, test_client, db_session
    ):
        """Test that total and has_more are accurate when using search + filters."""
        from app.db.models.channel import Channel
        from app.db.models.video import Video
        from app.db.models.tag import Tag
        from app.db.models.association_tables import video_tags

        channel = Channel(
            id="UC_pagination_acc",
            handle="paginationacc",
            title="Pagination Accuracy",
            uploads_playlist_id="UU_pagination_acc",
        )
        db_session.add(channel)
        await db_session.commit()

        # Create 5 videos, only 2 will match search "Tutorial"
        for i in range(5):
            title = f"Tutorial Part {i}" if i < 2 else f"Unrelated Video {i}"
            video = Video(
                id=f"acc_vid_{i}",
                channel_id=channel.id,
                title=title,
                description=f"Description {i}",
                published_at=datetime.now(timezone.utc),
                duration_seconds=300,
                is_short=False,
            )
            db_session.add(video)
        await db_session.commit()

        response = test_client.get("/videos/?q=Tutorial")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["has_more"] is False

    async def test_list_videos_invalid_date_format(self, test_client, db_session):
        """Test that invalid date format returns 400."""
        response = test_client.get("/videos/?published_after=not-a-date")

        assert response.status_code == 400

    async def test_list_videos_order_by_relevance(self, test_client, db_session):
        """Test GET /videos/?q=...&order_by=relevance returns 200."""
        from app.db.models.channel import Channel
        from app.db.models.video import Video

        channel = Channel(
            id="UC_relevance_test",
            handle="relevancetest",
            title="Relevance Test Channel",
            uploads_playlist_id="UU_relevance_test",
        )
        db_session.add(channel)
        await db_session.commit()

        video = Video(
            id="rel_vid_1",
            channel_id=channel.id,
            title="Python Tutorial",
            description="Learn Python",
            published_at=datetime.now(timezone.utc),
            duration_seconds=600,
            is_short=False,
        )
        db_session.add(video)
        await db_session.commit()

        response = test_client.get("/videos/?q=Python&order_by=relevance")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    async def test_list_videos_invalid_order_by(self, test_client, db_session):
        """Test GET /videos/?order_by=nonexistent returns 400."""
        response = test_client.get("/videos/?order_by=nonexistent")

        assert response.status_code == 400

    async def test_list_videos_order_direction(self, test_client, db_session):
        """Test GET /videos/?order_by=title&order_direction=asc returns 200."""
        response = test_client.get("/videos/?order_by=title&order_direction=asc")

        assert response.status_code == 200
