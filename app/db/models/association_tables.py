"""
Association tables for many-to-many relationships.

These tables are defined separately from the models to avoid circular import issues.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Table,
    Column,
    String,
    Integer,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
)
from ..base import Base

# Many-to-many association table for Channel ↔ Tag
channel_tags = Table(
    "channel_tags",
    Base.metadata,
    Column(
        "owner_id",
        String(36),
        primary_key=True,
        nullable=False,
        default="test-user",
        server_default="test-user",
    ),
    Column(
        "channel_id",
        String(32),
        primary_key=True,
    ),
    Column(
        "tag_id",
        String(36),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    ),
    ForeignKeyConstraint(
        ["owner_id", "channel_id"],
        ["channels.owner_id", "channels.id"],
        ondelete="CASCADE",
    ),
)

# Many-to-many association table for Video ↔ Tag
video_tags = Table(
    "video_tags",
    Base.metadata,
    Column(
        "owner_id",
        String(36),
        primary_key=True,
        nullable=False,
        default="test-user",
        server_default="test-user",
    ),
    Column(
        "video_id",
        String(16),
        primary_key=True,
    ),
    Column(
        "tag_id",
        String(36),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    ),
    ForeignKeyConstraint(
        ["owner_id", "video_id"],
        ["videos.owner_id", "videos.id"],
        ondelete="CASCADE",
    ),
)

# Many-to-many association table for Playlist ↔ Video
playlist_videos = Table(
    "playlist_videos",
    Base.metadata,
    Column(
        "owner_id",
        String(36),
        primary_key=True,
        nullable=False,
        default="test-user",
        server_default="test-user",
    ),
    Column(
        "playlist_id",
        String(36),
        ForeignKey("playlists.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "video_id",
        String(16),
        primary_key=True,
    ),
    Column(
        "position",
        Integer,
        nullable=False,
        default=0,
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    ),
    ForeignKeyConstraint(
        ["owner_id", "video_id"],
        ["videos.owner_id", "videos.id"],
        ondelete="CASCADE",
    ),
)
