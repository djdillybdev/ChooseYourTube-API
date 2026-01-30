from __future__ import annotations
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import DateTime, ForeignKey, Text, String, Boolean
from datetime import datetime, timezone
from ..base import Base
from .association_tables import channel_tags

if TYPE_CHECKING:
    from .video import Video
    from .folder import Folder
    from .tag import Tag


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        comment="YouTube's Channel ID (e.g., UC_x5XG1OV2P6uZZ5FSM9Ttw)",
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    handle: Mapped[str] = mapped_column(
        String(128), nullable=True, unique=True, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    uploads_playlist_id: Mapped[str] = mapped_column(
        String(48),
        nullable=False,
        comment="The ID of the channel's 'uploads' playlist.",
    )

    is_favorited: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        nullable=False,
    )

    # Foreign Key to Folder
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id"))

    # Relationship to Folder (One-to-Many)
    # A Channel belongs to one Folder.
    folder: Mapped["Folder"] = relationship(back_populates="channels")

    videos: Mapped[list["Video"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan", lazy="select"
    )

    # Many-to-many relationship with Tags
    tags: Mapped[list["Tag"]] = relationship(
        secondary=channel_tags, back_populates="channels", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Channel(id={self.id}, title='{self.title}')>"
