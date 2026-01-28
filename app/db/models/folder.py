from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..base import Base

if TYPE_CHECKING:
    from .channel import Channel


class Folder(Base):
    __tablename__ = "folders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # --- Relationships ---

    # Self-referencing relationship for sub-folders
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id"))

    # Relationship to Parent (Many-to-One to itself)
    # The `remote_side=[id]` is crucial for SQLAlchemy to understand how to join a table to itself.
    parent: Mapped["Folder"] = relationship(back_populates="children", remote_side=[id])

    # Relationship to Children (One-to-Many to itself)
    children: Mapped[list["Folder"]] = relationship(back_populates="parent")

    # Relationship to Channels (One-to-Many)
    # A Folder can contain many Channels.
    channels: Mapped[list["Channel"]] = relationship(back_populates="folder")

    def __repr__(self) -> str:
        return f"<Folder(id={self.id}, name='{self.name}')>"
