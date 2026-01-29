from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy import String, Text, Boolean, DateTime, Integer, ForeignKey, ARRAY, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.mutable import MutableList
from ..base import Base
from .association_tables import video_tags

if TYPE_CHECKING:
    from .channel import Channel
    from .tag import Tag


class Video(Base):
    __tablename__ = "videos"

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
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
        server_default="[]"
    )

    channel_id: Mapped[str] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True
    )

    channel: Mapped["Channel"] = relationship(back_populates="videos")

    # Many-to-many relationship with Tags (separate from yt_tags which are YouTube metadata)
    tags: Mapped[list["Tag"]] = relationship(
        secondary=video_tags,
        back_populates="videos",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Video(id={self.id}, title='{self.title}')>"
