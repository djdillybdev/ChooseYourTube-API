from __future__ import annotations
from pydantic import BaseModel, Field
from .base import BaseSchema

# --- Input Schemas ---


class FolderCreate(BaseModel):
    """Schema for creating a new folder."""

    name: str
    parent_id: int | None = None


class FolderUpdate(BaseModel):
    """Schema for updating a folder's name or moving it."""

    name: str | None = None
    parent_id: int | None = None


# --- Output Schema ---


class FolderOut(BaseSchema):
    """
    Schema for returning a folder, including its children.
    This is a recursive schema.
    """

    id: int
    name: str
    parent_id: int | None
    children: list["FolderOut"] = Field(default_factory=list)
