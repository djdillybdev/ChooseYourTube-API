from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..base import Base
from .association_tables import channel_tags, video_tags

if TYPE_CHECKING:
    from .channel import Channel
    from .video import Video


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Many-to-many relationships
    channels: Mapped[list["Channel"]] = relationship(
        secondary=channel_tags, back_populates="tags", lazy="selectin"
    )
    videos: Mapped[list["Video"]] = relationship(
        secondary=video_tags, back_populates="tags", lazy="selectin"
    )

    def __init__(self, **kwargs):
        """Initialize Tag and normalize name to lowercase for case-insensitive storage."""
        if "name" in kwargs:
            kwargs["name"] = kwargs["name"].lower()
        super().__init__(**kwargs)
