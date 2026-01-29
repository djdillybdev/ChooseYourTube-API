"""
Global pytest fixtures for all tests.

Includes:
- Mock fixtures for unit tests (YouTube API, Redis)
- Database fixtures for integration/CRUD tests
- FastAPI TestClient for router/API tests
- Sample YouTube API response fixtures
"""

import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# Set test environment variables before any app imports
# This prevents Settings validation errors during test collection
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("API_ORIGIN", "http://localhost:3000")
os.environ.setdefault("YOUTUBE_API_KEY", "test_api_key_for_testing")

from app.db.base import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.db.session import get_db_session  # noqa: E402
from app.clients.youtube import get_youtube_api  # noqa: E402
from app.queue import get_arq_redis  # noqa: E402


@pytest.fixture
def mock_youtube_api():
    """
    Mock YouTubeAPI client for testing without real API calls.

    Returns a MagicMock with async methods configured as AsyncMocks.
    """
    mock = MagicMock()

    # Mock async methods
    mock.channels_list_async = AsyncMock()
    mock.playlist_items_list_async = AsyncMock()
    mock.videos_list_async = AsyncMock()

    # Mock sync methods (wrapped in asyncio.to_thread)
    mock.get_channel_info = MagicMock()

    return mock


@pytest.fixture
def mock_arq_redis():
    """
    Mock arq Redis client for testing without Redis.

    Returns a MagicMock with enqueue_job configured as AsyncMock.
    """
    mock = MagicMock()
    mock.enqueue_job = AsyncMock()

    return mock


# Database Testing Fixtures

@pytest_asyncio.fixture
async def test_engine():
    """
    Create an in-memory SQLite database engine for testing.

    Uses StaticPool to maintain single connection across async operations.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables after tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """
    Provide a clean database session for each test.

    Each test gets a fresh session with a transaction that rolls back.
    """
    async_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()  # Rollback any uncommitted changes


# FastAPI TestClient Fixtures

@pytest.fixture
def test_client(db_session, mock_youtube_api, mock_arq_redis):
    """
    FastAPI TestClient for testing API endpoints.

    Overrides app dependencies with test fixtures:
    - Database session uses in-memory SQLite
    - YouTube API uses mock client
    - Redis client uses mock
    """
    # Override app dependencies
    app.dependency_overrides[get_db_session] = lambda: db_session
    app.dependency_overrides[get_youtube_api] = lambda: mock_youtube_api
    app.dependency_overrides[get_arq_redis] = lambda: mock_arq_redis

    client = TestClient(app)
    yield client

    # Clear dependency overrides after test
    app.dependency_overrides.clear()


# YouTube API Response Fixtures

@pytest.fixture
def sample_channel_response():
    """Sample YouTube channel info response for testing."""
    from tests.fixtures.youtube_responses import mock_channel_info_response
    return mock_channel_info_response()


@pytest.fixture
def sample_playlist_items_response():
    """Sample YouTube playlist items response for testing."""
    from tests.fixtures.youtube_responses import mock_playlist_items_response
    return mock_playlist_items_response()


@pytest.fixture
def sample_videos_list_response():
    """Sample YouTube videos list response for testing."""
    from tests.fixtures.youtube_responses import mock_videos_list_response
    return mock_videos_list_response()
