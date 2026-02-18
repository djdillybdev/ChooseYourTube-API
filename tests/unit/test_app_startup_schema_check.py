"""Tests for startup schema-check wiring."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from app.main import check_database_schema_on_startup


@pytest.mark.asyncio
async def test_startup_schema_check_skipped_when_disabled(monkeypatch):
    guard = AsyncMock()
    monkeypatch.setattr("app.main.assert_required_playlist_schema", guard)
    monkeypatch.setattr("app.main.settings.enable_startup_schema_check", False)

    await check_database_schema_on_startup()

    guard.assert_not_awaited()


@pytest.mark.asyncio
async def test_startup_schema_check_runs_when_enabled(monkeypatch):
    guard = AsyncMock()

    @asynccontextmanager
    async def fake_session_context():
        yield object()

    class FakeSessionManager:
        def session(self):
            return fake_session_context()

    monkeypatch.setattr("app.main.assert_required_playlist_schema", guard)
    monkeypatch.setattr("app.main.sessionmanager", FakeSessionManager())
    monkeypatch.setattr("app.main.settings.enable_startup_schema_check", True)

    await check_database_schema_on_startup()

    guard.assert_awaited_once()
