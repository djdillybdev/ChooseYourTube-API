from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Text,
    DateTime,
    Boolean,
    Integer,
    ForeignKeyConstraint,
    UniqueConstraint,
    and_,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..base import Base
from .association_tables import playlist_videos

if TYPE_CHECKING:
    from .channel import Channel
    from .video import Video


class Playlist(Base):
    __tablename__ = "playlists"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "source_type",
            "source_youtube_playlist_id",
            name="uq_playlist_owner_source_playlist",
        ),
        ForeignKeyConstraint(
            ["owner_id", "source_channel_id"],
            ["channels.owner_id", "channels.id"],
            ondelete="CASCADE",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, comment="UUID as string"
    )
    owner_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True, default="test-user"
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    source_channel_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    source_youtube_playlist_id: Mapped[str | None] = mapped_column(
        String(48), nullable=True, index=True
    )
    source_is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_position: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Many-to-many relationship with Videos
    videos: Mapped[list["Video"]] = relationship(
        secondary=playlist_videos,
        primaryjoin="and_(Playlist.owner_id == playlist_videos.c.owner_id, Playlist.id == playlist_videos.c.playlist_id)",
        secondaryjoin="and_(Video.owner_id == playlist_videos.c.owner_id, Video.id == playlist_videos.c.video_id)",
        back_populates="playlists",
        lazy="selectin",
    )
    source_channel: Mapped["Channel | None"] = relationship(lazy="selectin")

    def __repr__(self) -> str:
        return f"<Playlist(id={self.id}, name='{self.name}')>"
