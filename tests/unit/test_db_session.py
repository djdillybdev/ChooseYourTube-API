"""
Tests for database session management.

Tests the DatabaseSessionManager class and its context managers
for handling database connections and sessions.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.db.session import DatabaseSessionManager, get_db_session


class TestDatabaseSessionManagerInit:
    """Test DatabaseSessionManager initialization."""

    def test_init_creates_engine_and_sessionmaker(self):
        """Test that initialization creates engine and sessionmaker."""
        with patch("app.db.session.create_async_engine") as mock_create_engine:
            with patch("app.db.session.async_sessionmaker") as mock_sessionmaker:
                mock_engine = MagicMock()
                mock_create_engine.return_value = mock_engine

                manager = DatabaseSessionManager(
                    "sqlite+aiosqlite:///:memory:", engine_kwargs={"echo": True}
                )

                # Verify engine was created with correct parameters
                mock_create_engine.assert_called_once_with(
                    "sqlite+aiosqlite:///:memory:", echo=True
                )

                # Verify sessionmaker was created
                mock_sessionmaker.assert_called_once_with(
                    autocommit=False, bind=mock_engine, expire_on_commit=False
                )

    def test_init_with_empty_engine_kwargs(self):
        """Test initialization with default empty engine_kwargs."""
        with patch("app.db.session.create_async_engine") as mock_create_engine:
            with patch("app.db.session.async_sessionmaker"):
                manager = DatabaseSessionManager("sqlite+aiosqlite:///:memory:")

                # Verify engine was created with no extra kwargs
                mock_create_engine.assert_called_once_with(
                    "sqlite+aiosqlite:///:memory:",
                )


@pytest.mark.asyncio
class TestDatabaseSessionManagerClose:
    """Test DatabaseSessionManager.close() method."""

    async def test_close_when_engine_is_none_raises(self):
        """Test that close() raises when engine is not initialized."""
        with patch("app.db.session.create_async_engine"):
            with patch("app.db.session.async_sessionmaker"):
                manager = DatabaseSessionManager("sqlite+aiosqlite:///:memory:")
                manager._engine = None  # Simulate uninitialized state

                with pytest.raises(Exception) as exc_info:
                    await manager.close()

                assert "not initialized" in str(exc_info.value)

    async def test_close_disposes_engine(self):
        """Test that close() disposes the engine properly."""
        with patch("app.db.session.create_async_engine") as mock_create_engine:
            with patch("app.db.session.async_sessionmaker"):
                mock_engine = AsyncMock()
                mock_create_engine.return_value = mock_engine

                manager = DatabaseSessionManager("sqlite+aiosqlite:///:memory:")

                await manager.close()

                # Verify engine.dispose() was called
                mock_engine.dispose.assert_called_once()

                # Verify engine and sessionmaker are set to None
                assert manager._engine is None
                assert manager._sessionmaker is None


@pytest.mark.asyncio
class TestDatabaseSessionManagerConnect:
    """Test DatabaseSessionManager.connect() context manager."""

    async def test_connect_when_engine_is_none_raises(self):
        """Test that connect() raises when engine is not initialized."""
        with patch("app.db.session.create_async_engine"):
            with patch("app.db.session.async_sessionmaker"):
                manager = DatabaseSessionManager("sqlite+aiosqlite:///:memory:")
                manager._engine = None  # Simulate uninitialized state

                with pytest.raises(Exception) as exc_info:
                    async with manager.connect():
                        pass

                assert "not initialized" in str(exc_info.value)

    async def test_connect_yields_connection(self):
        """Test that connect() yields a valid connection."""
        with patch("app.db.session.create_async_engine") as mock_create_engine:
            with patch("app.db.session.async_sessionmaker"):
                # Create mock engine with begin context manager
                mock_engine = MagicMock()
                mock_connection = AsyncMock()
                mock_engine.begin.return_value.__aenter__.return_value = mock_connection
                mock_create_engine.return_value = mock_engine

                manager = DatabaseSessionManager("sqlite+aiosqlite:///:memory:")

                # Use the context manager
                async with manager.connect() as conn:
                    assert conn == mock_connection

    async def test_connect_rolls_back_on_exception(self):
        """Test that connect() rolls back on exception."""
        with patch("app.db.session.create_async_engine") as mock_create_engine:
            with patch("app.db.session.async_sessionmaker"):
                # Create mock engine with begin context manager
                mock_engine = MagicMock()
                mock_connection = AsyncMock()
                mock_engine.begin.return_value.__aenter__.return_value = mock_connection
                mock_create_engine.return_value = mock_engine

                manager = DatabaseSessionManager("sqlite+aiosqlite:///:memory:")

                # Raise exception inside context
                with pytest.raises(ValueError):
                    async with manager.connect() as conn:
                        raise ValueError("Test error")

                # Verify rollback was called
                mock_connection.rollback.assert_called_once()


@pytest.mark.asyncio
class TestDatabaseSessionManagerSession:
    """Test DatabaseSessionManager.session() context manager."""

    async def test_session_when_sessionmaker_is_none_raises(self):
        """Test that session() raises when sessionmaker is not initialized."""
        with patch("app.db.session.create_async_engine"):
            with patch("app.db.session.async_sessionmaker"):
                manager = DatabaseSessionManager("sqlite+aiosqlite:///:memory:")
                manager._sessionmaker = None  # Simulate uninitialized state

                with pytest.raises(Exception) as exc_info:
                    async with manager.session():
                        pass

                assert "not initialized" in str(exc_info.value)

    async def test_session_yields_session(self):
        """Test that session() yields a valid session."""
        with patch("app.db.session.create_async_engine"):
            with patch("app.db.session.async_sessionmaker") as mock_sessionmaker_cls:
                # Create mock session
                mock_session = AsyncMock(spec=AsyncSession)
                mock_sessionmaker = MagicMock()
                mock_sessionmaker.return_value = mock_session
                mock_sessionmaker_cls.return_value = mock_sessionmaker

                manager = DatabaseSessionManager("sqlite+aiosqlite:///:memory:")

                # Use the context manager
                async with manager.session() as session:
                    assert session == mock_session

                # Verify session.close() was called in finally block
                mock_session.close.assert_called_once()

    async def test_session_rolls_back_on_exception(self):
        """Test that session() rolls back on exception."""
        with patch("app.db.session.create_async_engine"):
            with patch("app.db.session.async_sessionmaker") as mock_sessionmaker_cls:
                # Create mock session
                mock_session = AsyncMock(spec=AsyncSession)
                mock_sessionmaker = MagicMock()
                mock_sessionmaker.return_value = mock_session
                mock_sessionmaker_cls.return_value = mock_sessionmaker

                manager = DatabaseSessionManager("sqlite+aiosqlite:///:memory:")

                # Raise exception inside context
                with pytest.raises(ValueError):
                    async with manager.session() as session:
                        raise ValueError("Test error")

                # Verify rollback was called
                mock_session.rollback.assert_called_once()

                # Verify session.close() was still called in finally block
                mock_session.close.assert_called_once()

    async def test_session_cleanup_on_normal_exit(self):
        """Test that session() cleans up on normal exit."""
        with patch("app.db.session.create_async_engine"):
            with patch("app.db.session.async_sessionmaker") as mock_sessionmaker_cls:
                # Create mock session
                mock_session = AsyncMock(spec=AsyncSession)
                mock_sessionmaker = MagicMock()
                mock_sessionmaker.return_value = mock_session
                mock_sessionmaker_cls.return_value = mock_sessionmaker

                manager = DatabaseSessionManager("sqlite+aiosqlite:///:memory:")

                # Use context manager normally
                async with manager.session() as session:
                    pass  # Normal exit

                # Verify session.close() was called
                mock_session.close.assert_called_once()

                # Verify rollback was NOT called (no exception)
                mock_session.rollback.assert_not_called()


@pytest.mark.asyncio
class TestGetDbSession:
    """Test get_db_session dependency injection helper."""

    async def test_get_db_session_yields_session(self):
        """Test that get_db_session yields a session from sessionmanager."""
        with patch("app.db.session.sessionmanager") as mock_manager:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_manager.session.return_value.__aenter__.return_value = mock_session

            # Call the generator
            gen = get_db_session()
            session = await gen.__anext__()

            assert session == mock_session

            # Clean up generator
            try:
                await gen.__anext__()
            except StopAsyncIteration:
                pass
