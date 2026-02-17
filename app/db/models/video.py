from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Text,
    Boolean,
    DateTime,
    Integer,
    ForeignKey,
    JSON,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.mutable import MutableList
from ..base import Base
from .association_tables import video_tags, playlist_videos

if TYPE_CHECKING:
    from .channel import Channel
    from .tag import Tag
    from .playlist import Playlist


class Video(Base):
    __tablename__ = "videos"
    __table_args__ = (
        # Index for filtering favorited videos
        Index("ix_video_is_favorited", "is_favorited"),
        # Index for filtering watched videos
        Index("ix_video_is_watched", "is_watched"),
        # Index for filtering shorts
        Index("ix_video_is_short", "is_short"),
        # Compound index for common query pattern: filter by channel and sort by published date
        Index("ix_video_channel_published", "channel_id", "published_at"),
    )

    id: Mapped[str] = mapped_column(
        String(16), primary_key=True, comment="YouTube's Video ID (e.g., dQw4w9WgXcQ)"
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer)

    is_favorited: Mapped[bool] = mapped_column(Boolean, default=False)
    is_short: Mapped[bool] = mapped_column(Boolean, default=False)
    is_watched: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        nullable=False,
    )
    # Use JSON for cross-database compatibility (works with both PostgreSQL and SQLite)
    # MutableList allows in-place modifications to be tracked by SQLAlchemy
    yt_tags: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSON), default=list, nullable=False, server_default="[]"
    )

    channel_id: Mapped[str] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True
    )

    channel: Mapped["Channel"] = relationship(back_populates="videos")

    # Many-to-many relationship with Tags (separate from yt_tags which are YouTube metadata)
    tags: Mapped[list["Tag"]] = relationship(
        secondary=video_tags, back_populates="videos", lazy="selectin"
    )

    # Many-to-many relationship with Playlists
    playlists: Mapped[list["Playlist"]] = relationship(
        secondary=playlist_videos, back_populates="videos", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Video(id={self.id}, title='{self.title}')>"
