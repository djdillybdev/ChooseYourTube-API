from pydantic import BaseModel, HttpUrl
from datetime import datetime
from .base import BaseSchema

# --- Input Schemas ---


class ChannelCreate(BaseModel):
    """
    Schema for adding a new channel. The user provides the handle
    and optionally which folder to place it in.
    """

    handle: str
    folder_id: int | None = None


class ChannelUpdate(BaseModel):
    """Schema for updating app-specific channel metadata."""

    is_favorited: bool | None = None
    folder_id: int | None = None  # Allows moving a channel
    tag_ids: list[int] | None = None  # List of tag IDs to associate with the channel


# --- Output Schema ---


class ChannelOut(BaseSchema):
    """Schema for returning a channel from the API."""

    id: str
    title: str
    handle: str | None
    description: str | None
    thumbnail_url: HttpUrl | None
    is_favorited: bool
    folder_id: int | None
    created_at: datetime
    last_updated: datetime

    # Calculated fields
    total_videos: int = 0
