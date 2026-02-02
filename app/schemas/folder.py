from __future__ import annotations
from pydantic import BaseModel, Field
from .base import BaseSchema

# --- Input Schemas ---

_UNSET = object()


class FolderCreate(BaseModel):
    """Schema for creating a new folder."""

    name: str
    parent_id: str | None = None


class FolderUpdate(BaseModel):
    """Schema for updating a folder's name or moving it."""

    name: str | None = None
    parent_id: str | None | object = _UNSET


# --- Output Schema ---


class FolderOut(BaseSchema):
    """
    Schema for returning a folder, including its children.
    This is a recursive schema.
    """

    id: str
    name: str
    parent_id: str | None
    children: list["FolderOut"] = Field(default_factory=list)
