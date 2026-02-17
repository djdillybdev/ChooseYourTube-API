from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..base import Base
from .association_tables import playlist_videos

if TYPE_CHECKING:
    from .video import Video


class Playlist(Base):
    __tablename__ = "playlists"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, comment="UUID as string"
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    current_position: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Many-to-many relationship with Videos
    videos: Mapped[list["Video"]] = relationship(
        secondary=playlist_videos, back_populates="playlists", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Playlist(id={self.id}, name='{self.name}')>"
