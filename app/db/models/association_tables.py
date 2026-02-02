"""
Association tables for many-to-many relationships.

These tables are defined separately from the models to avoid circular import issues.
"""

from datetime import datetime, timezone
from sqlalchemy import Table, Column, String, DateTime, ForeignKey
from ..base import Base

# Many-to-many association table for Channel ↔ Tag
channel_tags = Table(
    "channel_tags",
    Base.metadata,
    Column(
        "channel_id",
        String(32),
        ForeignKey("channels.id", ondelete="CASCADE"),
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
)

# Many-to-many association table for Video ↔ Tag
video_tags = Table(
    "video_tags",
    Base.metadata,
    Column(
        "video_id",
        String(16),
        ForeignKey("videos.id", ondelete="CASCADE"),
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
)
