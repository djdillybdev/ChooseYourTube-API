"""
Comprehensive tests for channel write operations (create, delete).

Tests create_channel(), delete_channel(), and delete_all_channels() methods.
"""

import pytest
import pytest_asyncio
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from app.db.crud.crud_channel import (
    create_channel,
    delete_channel,
    delete_all_channels,
    get_channels,
)
from app.db.models.channel import Channel
from app.db.models.folder import Folder


@pytest_asyncio.fixture
async def sample_folder(db_session):
    """Creates a test folder for testing folder_id foreign key relationships."""
    folder = Folder(name="Test Folder")
    db_session.add(folder)
    await db_session.commit()
    await db_session.refresh(folder)
    return folder


@pytest.mark.asyncio
class TestCreateChannel:
    """Tests for create_channel() function."""

    async def test_create_channel_with_all_required_fields(self, db_session):
        """Create a channel with only required fields."""
        channel = Channel(
            id="UC_test_channel_001",
            title="Test Channel",
            handle="@testchannel",
            uploads_playlist_id="UU_test_playlist_001",
        )

        result = await create_channel(db_session, channel)

        assert result.id == "UC_test_channel_001"
        assert result.title == "Test Channel"
        assert result.handle == "@testchannel"
        assert result.uploads_playlist_id == "UU_test_playlist_001"
        assert result.is_favorited is False  # Default value
        assert result.folder_id is None  # Default value
        assert isinstance(result.created_at, datetime)

    async def test_create_channel_with_all_fields(self, db_session, sample_folder):
        """Create a channel with all optional fields populated."""
        channel = Channel(
            id="UC_test_channel_002",
            title="Full Test Channel",
            handle="@fulltestchannel",
            description="This is a test channel with all fields",
            thumbnail_url="https://example.com/thumbnail.jpg",
            uploads_playlist_id="UU_test_playlist_002",
            is_favorited=True,
            folder_id=sample_folder.id,
        )

        result = await create_channel(db_session, channel)

        assert result.id == "UC_test_channel_002"
        assert result.title == "Full Test Channel"
        assert result.handle == "@fulltestchannel"
        assert result.description == "This is a test channel with all fields"
        assert result.thumbnail_url == "https://example.com/thumbnail.jpg"
        assert result.uploads_playlist_id == "UU_test_playlist_002"
        assert result.is_favorited is True
        assert result.folder_id == sample_folder.id

    async def test_create_channel_persists_to_database(self, db_session):
        """Verify channel is actually persisted and can be retrieved."""
        channel = Channel(
            id="UC_test_channel_003",
            title="Persistence Test",
            handle="@persisttest",
            uploads_playlist_id="UU_test_playlist_003",
        )

        await create_channel(db_session, channel)

        # Retrieve the channel using get_channels
        retrieved = await get_channels(db_session, id="UC_test_channel_003", first=True)
        assert retrieved is not None
        assert retrieved.title == "Persistence Test"

    async def test_create_channel_with_duplicate_id_raises_integrity_error(
        self, db_session
    ):
        """Creating a channel with duplicate ID should raise IntegrityError."""
        channel1 = Channel(
            id="UC_duplicate",
            title="First Channel",
            handle="@first",
            uploads_playlist_id="UU_duplicate_1",
        )
        await create_channel(db_session, channel1)

        # Expunge to clear identity map and prevent SAWarning about identity conflict
        db_session.expunge(channel1)

        # Try to create another channel with same ID
        channel2 = Channel(
            id="UC_duplicate",
            title="Second Channel",
            handle="@second",
            uploads_playlist_id="UU_duplicate_2",
        )

        with pytest.raises(IntegrityError):
            await create_channel(db_session, channel2)

    async def test_create_channel_with_invalid_folder_id(self, db_session):
        """
        Creating a channel with non-existent folder_id.

        Note: SQLite doesn't enforce foreign key constraints by default,
        so this won't raise an error in tests. In PostgreSQL, this would
        raise an IntegrityError.
        """
        channel = Channel(
            id="UC_test_channel_004",
            title="Invalid Folder Test",
            handle="@invalidfolder",
            uploads_playlist_id="UU_test_playlist_004",
            folder_id=99999,  # Non-existent folder ID
        )

        # In SQLite this succeeds, in PostgreSQL it would raise IntegrityError
        result = await create_channel(db_session, channel)
        assert result.folder_id == 99999

    async def test_create_channel_returns_refreshed_instance(self, db_session):
        """Verify returned channel has database-generated values."""
        channel = Channel(
            id="UC_test_channel_005",
            title="Refresh Test",
            handle="@refreshtest",
            uploads_playlist_id="UU_test_playlist_005",
        )

        result = await create_channel(db_session, channel)

        # created_at should be populated by database defaults
        assert result.created_at is not None
        assert isinstance(result.created_at, datetime)

    async def test_create_multiple_channels(self, db_session):
        """Create multiple channels in sequence."""
        channels_data = [
            ("UC_multi_001", "Multi 1", "@multi1", "UU_multi_001"),
            ("UC_multi_002", "Multi 2", "@multi2", "UU_multi_002"),
            ("UC_multi_003", "Multi 3", "@multi3", "UU_multi_003"),
        ]

        for channel_id, title, handle, playlist_id in channels_data:
            channel = Channel(
                id=channel_id,
                title=title,
                handle=handle,
                uploads_playlist_id=playlist_id,
            )
            await create_channel(db_session, channel)

        # Verify all were created
        all_channels = await get_channels(db_session)
        assert len(all_channels) == 3

    async def test_create_channel_with_folder(self, db_session, sample_folder):
        """Create a channel and associate it with a folder."""
        channel = Channel(
            id="UC_test_channel_006",
            title="Folder Test",
            handle="@foldertest",
            uploads_playlist_id="UU_test_playlist_006",
            folder_id=sample_folder.id,
        )

        result = await create_channel(db_session, channel)

        assert result.folder_id == sample_folder.id


@pytest.mark.asyncio
class TestDeleteChannel:
    """Tests for delete_channel() function."""

    async def test_delete_existing_channel(self, db_session):
        """Delete a channel that exists in the database."""
        # Create a channel first
        channel = Channel(
            id="UC_delete_test_001",
            title="To Be Deleted",
            handle="@tobedeleted",
            uploads_playlist_id="UU_delete_test_001",
        )
        await create_channel(db_session, channel)

        # Verify it exists
        existing = await get_channels(db_session, id="UC_delete_test_001", first=True)
        assert existing is not None

        # Delete it
        await delete_channel(db_session, existing)

        # Verify it's gone
        deleted = await get_channels(db_session, id="UC_delete_test_001", first=True)
        assert deleted is None

    async def test_delete_channel_removes_from_database(self, db_session):
        """Verify deletion actually removes the channel."""
        # Create multiple channels
        for i in range(3):
            channel = Channel(
                id=f"UC_delete_test_{i}",
                title=f"Channel {i}",
                handle=f"@channel{i}",
                uploads_playlist_id=f"UU_delete_test_{i}",
            )
            await create_channel(db_session, channel)

        # Verify we have 3 channels
        all_channels = await get_channels(db_session)
        assert len(all_channels) == 3

        # Delete one
        channel_to_delete = await get_channels(
            db_session, id="UC_delete_test_1", first=True
        )
        await delete_channel(db_session, channel_to_delete)

        # Verify we now have 2 channels
        remaining_channels = await get_channels(db_session)
        assert len(remaining_channels) == 2

    async def test_delete_channel_with_folder(self, db_session, sample_folder):
        """Delete a channel that belongs to a folder."""
        channel = Channel(
            id="UC_delete_test_002",
            title="Channel in Folder",
            handle="@channelinfolder",
            uploads_playlist_id="UU_delete_test_002",
            folder_id=sample_folder.id,
        )
        await create_channel(db_session, channel)

        # Delete the channel
        await delete_channel(db_session, channel)

        # Verify it's deleted
        deleted = await get_channels(db_session, id="UC_delete_test_002", first=True)
        assert deleted is None

        # Verify folder still exists (no cascade delete on folder)
        await db_session.refresh(sample_folder)
        assert sample_folder.id is not None

    async def test_delete_favorited_channel(self, db_session):
        """Delete a channel that is marked as favorited."""
        channel = Channel(
            id="UC_delete_test_003",
            title="Favorited Channel",
            handle="@favoritedchannel",
            uploads_playlist_id="UU_delete_test_003",
            is_favorited=True,
        )
        await create_channel(db_session, channel)

        await delete_channel(db_session, channel)

        # Verify it's deleted
        deleted = await get_channels(db_session, id="UC_delete_test_003", first=True)
        assert deleted is None


@pytest.mark.asyncio
class TestDeleteAllChannels:
    """Tests for delete_all_channels() bulk deletion function."""

    async def test_delete_all_channels_empty_database(self, db_session):
        """Delete all channels when database is empty returns 0."""
        count = await delete_all_channels(db_session)
        assert count == 0

    async def test_delete_all_channels_with_data(self, db_session):
        """Delete all channels returns correct count."""
        # Create 5 channels
        for i in range(5):
            channel = Channel(
                id=f"UC_bulk_delete_{i}",
                title=f"Channel {i}",
                handle=f"@channel{i}",
                uploads_playlist_id=f"UU_bulk_delete_{i}",
            )
            await create_channel(db_session, channel)

        # Verify we have 5 channels
        all_channels = await get_channels(db_session)
        assert len(all_channels) == 5

        # Delete all
        count = await delete_all_channels(db_session)
        assert count == 5

        # Verify database is empty
        remaining = await get_channels(db_session)
        assert len(remaining) == 0

    async def test_delete_all_channels_twice(self, db_session):
        """Calling delete_all twice should work (second call returns 0)."""
        # Create some channels
        for i in range(3):
            channel = Channel(
                id=f"UC_double_delete_{i}",
                title=f"Channel {i}",
                handle=f"@channel{i}",
                uploads_playlist_id=f"UU_double_delete_{i}",
            )
            await create_channel(db_session, channel)

        # First delete
        count1 = await delete_all_channels(db_session)
        assert count1 == 3

        # Second delete
        count2 = await delete_all_channels(db_session)
        assert count2 == 0

    async def test_delete_all_channels_removes_all_types(
        self, db_session, sample_folder
    ):
        """Delete all channels removes favorited and folder-assigned channels."""
        # Create diverse channels
        channels_data = [
            ("UC_diverse_001", "Regular Channel", "@regular", "UU_001", False, None),
            ("UC_diverse_002", "Favorited", "@favorited", "UU_002", True, None),
            (
                "UC_diverse_003",
                "In Folder",
                "@infolder",
                "UU_003",
                False,
                sample_folder.id,
            ),
            (
                "UC_diverse_004",
                "Fav + Folder",
                "@favfolder",
                "UU_004",
                True,
                sample_folder.id,
            ),
        ]

        for channel_id, title, handle, playlist_id, is_fav, folder_id in channels_data:
            channel = Channel(
                id=channel_id,
                title=title,
                handle=handle,
                uploads_playlist_id=playlist_id,
                is_favorited=is_fav,
                folder_id=folder_id,
            )
            await create_channel(db_session, channel)

        count = await delete_all_channels(db_session)
        assert count == 4

        # Verify all gone
        remaining = await get_channels(db_session)
        assert len(remaining) == 0

    async def test_delete_all_channels_large_dataset(self, db_session):
        """Delete all channels works with larger datasets."""
        # Create 50 channels
        for i in range(50):
            channel = Channel(
                id=f"UC_large_{str(i).zfill(3)}",
                title=f"Channel {i}",
                handle=f"@channel{i}",
                uploads_playlist_id=f"UU_large_{str(i).zfill(3)}",
            )
            await create_channel(db_session, channel)

        count = await delete_all_channels(db_session)
        assert count == 50

        remaining = await get_channels(db_session)
        assert len(remaining) == 0
