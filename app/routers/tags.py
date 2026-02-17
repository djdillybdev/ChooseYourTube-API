from fastapi import APIRouter, Query, status

from app.schemas.base import PaginatedResponse
from ..dependencies import DBSessionDep, CurrentUserDep
from ..schemas.tag import TagCreate, TagUpdate, TagOut
from ..schemas.video import VideoOut
from ..schemas.channel import ChannelOut
from ..services import tag_service

router = APIRouter(prefix="/tags", tags=["Tags"])


@router.get("/", response_model=PaginatedResponse[TagOut])
async def list_tags(
    db_session: DBSessionDep,
    user: CurrentUserDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    List all tags with pagination.
    """
    return await tag_service.get_all_tags(
        db_session=db_session, limit=limit, offset=offset, owner_id=str(user.id)
    )


@router.get("/{tag_id}", response_model=TagOut)
async def get_tag_by_id(tag_id: str, db_session: DBSessionDep, user: CurrentUserDep):
    """
    Get a single tag by ID.
    """
    return await tag_service.get_tag_by_id(
        tag_id=tag_id, db_session=db_session, owner_id=str(user.id)
    )


@router.post("/", response_model=TagOut, status_code=status.HTTP_201_CREATED)
async def create_tag(payload: TagCreate, db_session: DBSessionDep, user: CurrentUserDep):
    """
    Create a new tag.
    Tag names are automatically normalized to lowercase.
    """
    return await tag_service.create_new_tag(
        payload=payload, db_session=db_session, owner_id=str(user.id)
    )


@router.patch("/{tag_id}", response_model=TagOut)
async def update_tag(
    tag_id: str, payload: TagUpdate, db_session: DBSessionDep, user: CurrentUserDep
):
    """
    Update a tag's name.
    """
    return await tag_service.update_tag(
        tag_id=tag_id, payload=payload, db_session=db_session, owner_id=str(user.id)
    )


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(tag_id: str, db_session: DBSessionDep, user: CurrentUserDep):
    """
    Delete a tag by its ID.
    This will also remove the tag from all associated channels and videos.
    """
    await tag_service.delete_tag_by_id(
        tag_id=tag_id, db_session=db_session, owner_id=str(user.id)
    )


@router.get("/{tag_id}/videos", response_model=list[VideoOut])
async def get_videos_for_tag(
    tag_id: str,
    db_session: DBSessionDep,
    user: CurrentUserDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Get all videos associated with a tag.
    """
    return await tag_service.get_videos_for_tag(
        tag_id=tag_id, db_session=db_session, limit=limit, offset=offset, owner_id=str(user.id)
    )


@router.get("/{tag_id}/channels", response_model=list[ChannelOut])
async def get_channels_for_tag(
    tag_id: str,
    db_session: DBSessionDep,
    user: CurrentUserDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Get all channels associated with a tag.
    """
    return await tag_service.get_channels_for_tag(
        tag_id=tag_id, db_session=db_session, limit=limit, offset=offset, owner_id=str(user.id)
    )
