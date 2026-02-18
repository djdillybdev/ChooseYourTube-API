"""
Tests for channel tag management through the service layer.

Tests the update_channel service method's tag synchronization functionality.
"""

import pytest
import pytest_asyncio
from fastapi import HTTPException
from app.services.channel_service import update_channel
from app.db.crud.crud_channel import create_channel, delete_channel, get_channels
from app.db.crud.crud_tag import create_tag, get_tags
from app.db.models.channel import Channel
from app.db.models.tag import Tag
from app.schemas.channel import ChannelUpdate


@pytest_asyncio.fixture
async def sample_tags(db_session):
    """Create sample tags for testing."""
    import uuid

    tag_names = ["python", "javascript", "tutorial", "advanced", "beginner"]
    tags = []
    for name in tag_names:
        tag = Tag(id=str(uuid.uuid4()), name=name)
        created_tag = await create_tag(db_session, tag)
        tags.append(created_tag)
    return tags


@pytest_asyncio.fixture
async def sample_channel(db_session):
    """Create a sample channel for testing."""
    channel = Channel(
        id="UC001",
        title="Python Tutorials",
        handle="@pythontutorials",
        uploads_playlist_id="UU001",
    )
    return await create_channel(db_session, channel)


@pytest.mark.asyncio
class TestUpdateChannelWithTags:
    """Tests for updating channel tags through the service layer."""

    async def test_add_tags_to_channel(self, db_session, sample_channel, sample_tags):
        """Add tags to a channel using update_channel."""
        tag_ids = [sample_tags[0].id, sample_tags[1].id]

        payload = ChannelUpdate(tag_ids=tag_ids)
        await update_channel(sample_channel.id, payload, db_session)

        # Verify tags were added
        refreshed = await get_channels(db_session, id=sample_channel.id, first=True)
        assert len(refreshed.tags) == 2

        result_tag_ids = {t.id for t in refreshed.tags}
        assert result_tag_ids == set(tag_ids)

    async def test_replace_channel_tags(self, db_session, sample_channel, sample_tags):
        """Replace existing tags with new ones."""
        # First, add some tags
        initial_tag_ids = [sample_tags[0].id, sample_tags[1].id]
        payload = ChannelUpdate(tag_ids=initial_tag_ids)
        await update_channel(sample_channel.id, payload, db_session)

        # Verify initial tags
        refreshed = await get_channels(db_session, id=sample_channel.id, first=True)
        assert len(refreshed.tags) == 2

        # Now replace with different tags
        new_tag_ids = [sample_tags[2].id, sample_tags[3].id, sample_tags[4].id]
        payload = ChannelUpdate(tag_ids=new_tag_ids)
        await update_channel(sample_channel.id, payload, db_session)

        # Verify tags were replaced
        refreshed = await get_channels(db_session, id=sample_channel.id, first=True)
        assert len(refreshed.tags) == 3

        result_tag_ids = {t.id for t in refreshed.tags}
        assert result_tag_ids == set(new_tag_ids)

    async def test_remove_all_tags_with_empty_list(
        self, db_session, sample_channel, sample_tags
    ):
        """Remove all tags by providing an empty list."""
        # First, add some tags
        tag_ids = [sample_tags[0].id, sample_tags[1].id]
        payload = ChannelUpdate(tag_ids=tag_ids)
        await update_channel(sample_channel.id, payload, db_session)

        # Verify tags were added
        refreshed = await get_channels(db_session, id=sample_channel.id, first=True)
        assert len(refreshed.tags) == 2

        # Remove all tags with empty list
        payload = ChannelUpdate(tag_ids=[])
        await update_channel(sample_channel.id, payload, db_session)

        # Verify all tags removed
        refreshed = await get_channels(db_session, id=sample_channel.id, first=True)
        assert len(refreshed.tags) == 0

    async def test_update_without_tag_ids_preserves_tags(
        self, db_session, sample_channel, sample_tags
    ):
        """Updating other fields without tag_ids should preserve existing tags."""
        # Add some tags
        tag_ids = [sample_tags[0].id, sample_tags[1].id]
        payload = ChannelUpdate(tag_ids=tag_ids)
        await update_channel(sample_channel.id, payload, db_session)

        # Update is_favorited without touching tag_ids
        payload = ChannelUpdate(is_favorited=True)
        await update_channel(sample_channel.id, payload, db_session)

        # Verify tags are still there
        refreshed = await get_channels(db_session, id=sample_channel.id, first=True)
        assert len(refreshed.tags) == 2
        assert refreshed.is_favorited is True

    async def test_add_duplicate_tag_ids_in_list(
        self, db_session, sample_channel, sample_tags
    ):
        """Providing duplicate tag IDs in the list should deduplicate."""
        # Provide duplicate IDs
        tag_ids = [sample_tags[0].id, sample_tags[0].id, sample_tags[1].id]

        payload = ChannelUpdate(tag_ids=tag_ids)
        await update_channel(sample_channel.id, payload, db_session)

        # Verify only unique tags were added
        refreshed = await get_channels(db_session, id=sample_channel.id, first=True)
        assert len(refreshed.tags) == 2

    async def test_update_channel_with_nonexistent_tag_raises_error(
        self, db_session, sample_channel
    ):
        """Providing a non-existent tag ID should raise HTTPException."""
        payload = ChannelUpdate(tag_ids=["nonexistent-tag"])

        with pytest.raises(HTTPException) as exc_info:
            await update_channel(sample_channel.id, payload, db_session)

        assert exc_info.value.status_code == 400
        assert "does not exist" in exc_info.value.detail

    async def test_partial_invalid_tag_ids_raises_error(
        self, db_session, sample_channel, sample_tags
    ):
        """Providing a mix of valid and invalid tag IDs should raise error."""
        # Mix valid and invalid IDs
        tag_ids = [sample_tags[0].id, "nonexistent-uuid", sample_tags[1].id]

        payload = ChannelUpdate(tag_ids=tag_ids)

        with pytest.raises(HTTPException) as exc_info:
            await update_channel(sample_channel.id, payload, db_session)

        assert exc_info.value.status_code == 400

    async def test_update_nonexistent_channel_with_tags_raises_error(
        self, db_session, sample_tags
    ):
        """Updating a non-existent channel should raise 404."""
        payload = ChannelUpdate(tag_ids=[sample_tags[0].id])

        with pytest.raises(HTTPException) as exc_info:
            await update_channel("UC_NONEXISTENT", payload, db_session)

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()


@pytest.mark.asyncio
class TestChannelTagRelationships:
    """Tests for tag relationship access and behavior."""

    async def test_access_tags_through_channel_relationship(
        self, db_session, sample_channel, sample_tags
    ):
        """Access tags through channel.tags relationship."""
        tag_ids = [sample_tags[0].id, sample_tags[1].id]
        payload = ChannelUpdate(tag_ids=tag_ids)
        await update_channel(sample_channel.id, payload, db_session)

        # Access through relationship
        refreshed = await get_channels(db_session, id=sample_channel.id, first=True)
        assert len(refreshed.tags) == 2

        tag_names = {t.name for t in refreshed.tags}
        expected_names = {sample_tags[0].name, sample_tags[1].name}
        assert tag_names == expected_names

    async def test_access_channels_through_tag_relationship(
        self, db_session, sample_tags
    ):
        """Access channels through tag.channels relationship."""
        # Create multiple channels and add same tag to all
        channels = []
        for i in range(3):
            channel = Channel(
                id=f"UC{i:03d}",
                title=f"Channel {i}",
                handle=f"@channel{i}",
                uploads_playlist_id=f"UU{i:03d}",
            )
            created = await create_channel(db_session, channel)
            channels.append(created)

            # Add the same tag to each channel
            payload = ChannelUpdate(tag_ids=[sample_tags[0].id])
            await update_channel(created.id, payload, db_session)

        # Access channels through tag relationship
        refreshed_tag = await get_tags(db_session, id=sample_tags[0].id, first=True)
        assert len(refreshed_tag.channels) == 3

        channel_ids = {c.id for c in refreshed_tag.channels}
        expected_ids = {c.id for c in channels}
        assert channel_ids == expected_ids

    async def test_delete_channel_removes_tag_associations(
        self, db_session, sample_channel, sample_tags
    ):
        """Deleting a channel should remove tag associations but keep the tags."""
        # Add tags to channel
        tag_ids = [sample_tags[0].id, sample_tags[1].id]
        payload = ChannelUpdate(tag_ids=tag_ids)
        await update_channel(sample_channel.id, payload, db_session)

        # Verify associations exist
        refreshed_channel = await get_channels(
            db_session, id=sample_channel.id, first=True
        )
        assert len(refreshed_channel.tags) == 2

        # Delete the channel
        await delete_channel(db_session, refreshed_channel)

        # Verify channel is gone
        deleted_channel = await get_channels(
            db_session, id=sample_channel.id, first=True
        )
        assert deleted_channel is None

        # Verify tags still exist
        for tag_id in tag_ids:
            tag = await get_tags(db_session, id=tag_id, first=True)
            assert tag is not None

    async def test_channel_with_no_tags(self, db_session, sample_channel):
        """Channel with no tags should have empty tags list."""
        refreshed = await get_channels(db_session, id=sample_channel.id, first=True)
        assert len(refreshed.tags) == 0
        assert refreshed.tags == []


@pytest.mark.asyncio
class TestChannelTagEdgeCases:
    """Tests for edge cases in channel tag management."""

    async def test_channel_with_many_tags(
        self, db_session, sample_channel, sample_tags
    ):
        """A channel can have many tags."""
        # Add all tags to the channel
        tag_ids = [t.id for t in sample_tags]
        payload = ChannelUpdate(tag_ids=tag_ids)
        await update_channel(sample_channel.id, payload, db_session)

        refreshed = await get_channels(db_session, id=sample_channel.id, first=True)
        assert len(refreshed.tags) == len(sample_tags)

    async def test_tag_used_by_many_channels(self, db_session, sample_tags):
        """A tag can be used by many channels."""
        # Create multiple channels
        channels = []
        for i in range(5):
            channel = Channel(
                id=f"UC{i:03d}",
                title=f"Channel {i}",
                handle=f"@channel{i}",
                uploads_playlist_id=f"UU{i:03d}",
            )
            created = await create_channel(db_session, channel)
            channels.append(created)

            # Add same tag to each
            payload = ChannelUpdate(tag_ids=[sample_tags[0].id])
            await update_channel(created.id, payload, db_session)

        # Verify tag has all channels
        refreshed_tag = await get_tags(db_session, id=sample_tags[0].id, first=True)
        assert len(refreshed_tag.channels) == 5

    async def test_add_remove_add_tags_multiple_times(
        self, db_session, sample_channel, sample_tags
    ):
        """Add and remove tags multiple times (idempotent operations)."""
        tag_ids = [sample_tags[0].id]

        # Add tags
        payload = ChannelUpdate(tag_ids=tag_ids)
        await update_channel(sample_channel.id, payload, db_session)
        refreshed = await get_channels(db_session, id=sample_channel.id, first=True)
        assert len(refreshed.tags) == 1

        # Remove tags
        payload = ChannelUpdate(tag_ids=[])
        await update_channel(sample_channel.id, payload, db_session)
        refreshed = await get_channels(db_session, id=sample_channel.id, first=True)
        assert len(refreshed.tags) == 0

        # Add again
        payload = ChannelUpdate(tag_ids=tag_ids)
        await update_channel(sample_channel.id, payload, db_session)
        refreshed = await get_channels(db_session, id=sample_channel.id, first=True)
        assert len(refreshed.tags) == 1

        # Remove again
        payload = ChannelUpdate(tag_ids=[])
        await update_channel(sample_channel.id, payload, db_session)
        refreshed = await get_channels(db_session, id=sample_channel.id, first=True)
        assert len(refreshed.tags) == 0

    async def test_combined_updates(self, db_session, sample_channel, sample_tags):
        """Update tags along with other channel fields."""
        tag_ids = [sample_tags[0].id, sample_tags[1].id]

        payload = ChannelUpdate(tag_ids=tag_ids, is_favorited=True, folder_id="f5")
        await update_channel(sample_channel.id, payload, db_session)

        # Verify all fields updated
        refreshed = await get_channels(db_session, id=sample_channel.id, first=True)
        assert len(refreshed.tags) == 2
        assert refreshed.is_favorited is True
        assert refreshed.folder_id == "f5"
