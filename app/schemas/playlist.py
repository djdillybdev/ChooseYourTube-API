"""
Pydantic schemas for Playlist entity validation and serialization.
"""

from datetime import datetime
from pydantic import BaseModel, Field

from app.schemas.base import BaseSchema


# --- Create Schema ---


class PlaylistCreate(BaseModel):
    """Schema for creating a new playlist."""

    name: str = Field(..., min_length=1, max_length=255, description="Playlist name")
    description: str | None = Field(None, description="Playlist description")
    is_system: bool = Field(False, description="Whether this is a system playlist (e.g. queue)")


# --- Update Schema ---


class PlaylistUpdate(BaseModel):
    """Schema for updating a playlist."""

    name: str | None = Field(
        None, min_length=1, max_length=255, description="New playlist name"
    )
    description: str | None = Field(None, description="New playlist description")


# --- Video Management Schemas ---


class PlaylistAddVideo(BaseModel):
    """Schema for adding a video to a playlist."""

    video_id: str = Field(..., description="Video ID to add")
    position: int | None = Field(None, ge=0, description="Position in playlist (appended if omitted)")


class PlaylistAddVideos(BaseModel):
    """Schema for bulk adding videos to a playlist."""

    video_ids: list[str] = Field(..., min_length=1, description="Video IDs to add")
    position: int | None = Field(None, ge=0, description="Insert position (appended if omitted)")


class PlaylistMoveVideo(BaseModel):
    """Schema for moving a video to a new position."""

    video_id: str = Field(..., description="Video ID to move")
    new_position: int = Field(..., ge=0, description="Target position")


class PlaylistSetPosition(BaseModel):
    """Schema for setting the current playback position."""

    current_position: int | None = Field(None, ge=0, description="Current position index, null to clear")


class PlaylistSetVideos(BaseModel):
    """Schema for setting the full ordered video list of a playlist."""

    video_ids: list[str] = Field(..., description="Ordered list of video IDs")


# --- Output Schemas ---


class PlaylistOut(BaseSchema):
    """Schema for playlist output (list endpoints)."""

    id: str
    name: str
    description: str | None
    thumbnail_url: str | None = None
    is_system: bool
    source_type: str
    source_channel_id: str | None = None
    source_youtube_playlist_id: str | None = None
    source_is_active: bool
    source_last_synced_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PlaylistDetailOut(BaseSchema):
    """Schema for detailed playlist output with ordered video IDs."""

    id: str
    name: str
    description: str | None
    thumbnail_url: str | None = None
    is_system: bool
    source_type: str
    source_channel_id: str | None = None
    source_youtube_playlist_id: str | None = None
    source_is_active: bool
    source_last_synced_at: datetime | None = None
    current_position: int | None
    total_videos: int
    created_at: datetime
    video_ids: list[str]

    model_config = {"from_attributes": True}


class ChannelPlaylistOut(BaseSchema):
    id: str
    name: str
    description: str | None
    thumbnail_url: str | None
    is_system: bool
    source_type: str
    source_channel_id: str | None
    source_youtube_playlist_id: str | None
    source_is_active: bool
    source_last_synced_at: datetime | None
    total_videos: int
    created_at: datetime

    model_config = {"from_attributes": True}
