from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy import String, Text, Boolean, DateTime, Integer, ForeignKey, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..base import Base

if TYPE_CHECKING:
    from .channel import Channel


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
    yt_tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, nullable=False, server_default="{}"
    )

    channel_id: Mapped[str] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True
    )

    channel: Mapped["Channel"] = relationship(back_populates="videos")

    def __repr__(self) -> str:
        return f"<Video(id={self.id}, title='{self.title}')>"
