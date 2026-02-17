from pydantic import BaseModel, HttpUrl, TypeAdapter, field_validator
from datetime import datetime
from .base import BaseSchema

# --- Input Schemas ---


class VideoCreate(BaseModel):
    """
    Internal schema for creating a video from YouTube API data.
    This is not intended for direct use by an end-user API endpoint.
    """

    owner_id: str = "test-user"
    id: str
    channel_id: str
    title: str
    description: str | None
    thumbnail_url: str | None = None
    published_at: datetime
    duration_seconds: int | None
    yt_tags: list[str] = []
    is_short: bool = False

    @field_validator("thumbnail_url", mode="before")
    @classmethod
    def _validate_url(cls, v):
        if v is None:
            return None
        TypeAdapter(HttpUrl).validate_python(v)  # validates
        return str(v)


class VideoUpdate(BaseModel):
    """Schema for updating app-specific video metadata."""

    is_favorited: bool | None = None
    is_watched: bool | None = None
    is_short: bool | None = None
    tag_ids: list[str] | None = None  # List of tag IDs to associate with the video


# --- Output Schema ---


class VideoOut(BaseSchema):
    """Schema for returning a video from the API."""

    id: str
    channel_id: str
    title: str
    description: str | None
    thumbnail_url: HttpUrl | None
    published_at: datetime
    duration_seconds: int | None
    yt_tags: list[str]
    is_short: bool
    is_favorited: bool
    is_watched: bool
    created_at: datetime
