"""
Pydantic schemas for Tag entity validation and serialization.
"""

from datetime import datetime
from pydantic import BaseModel, Field, field_validator


# --- Create Schema ---


class TagCreate(BaseModel):
    """Schema for creating a new tag."""

    name: str = Field(..., min_length=1, max_length=255, description="Tag name")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        """Normalize tag name to lowercase and strip whitespace."""
        return v.strip().lower()


# --- Update Schema ---


class TagUpdate(BaseModel):
    """Schema for updating a tag."""

    name: str | None = Field(None, min_length=1, max_length=255, description="New tag name")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str | None) -> str | None:
        """Normalize tag name to lowercase and strip whitespace."""
        if v is not None:
            return v.strip().lower()
        return v


# --- Output Schema ---


class TagOut(BaseModel):
    """Schema for tag output."""

    id: int
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}
