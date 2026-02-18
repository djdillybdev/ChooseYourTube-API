from fastapi import APIRouter, status
from ..dependencies import DBSessionDep, CurrentUserDep
from ..schemas.folder import FolderCreate, FolderUpdate, FolderOut
from ..services import folder_service

router = APIRouter(prefix="/folders", tags=["Folders"])


@router.get("/tree", response_model=list[FolderOut])
async def read_folder_tree(db_session: DBSessionDep, user: CurrentUserDep):
    return await folder_service.get_tree(db_session, owner_id=str(user.id))


@router.post("/", response_model=FolderOut, status_code=status.HTTP_201_CREATED)
async def create_folder(
    payload: FolderCreate, db_session: DBSessionDep, user: CurrentUserDep
):
    f = await folder_service.create_folder(payload, db_session, owner_id=str(user.id))
    return FolderOut.model_validate(
        {
            "id": f.id,
            "name": f.name,
            "icon_key": f.icon_key,
            "parent_id": f.parent_id,
            "position": f.position,
            "children": [],
        }
    )


@router.patch("/{folder_id}", response_model=FolderOut)
async def rename_or_move_folder(
    folder_id: str,
    payload: FolderUpdate,
    db_session: DBSessionDep,
    user: CurrentUserDep,
):
    f = await folder_service.update_folder(
        folder_id, payload, db_session, owner_id=str(user.id)
    )
    return FolderOut.model_validate(
        {
            "id": f.id,
            "name": f.name,
            "icon_key": f.icon_key,
            "parent_id": f.parent_id,
            "position": f.position,
            "children": [],
        }
    )


@router.get("/{folder_id}", response_model=FolderOut)
async def read_folder_by_id(
    folder_id: str, db_session: DBSessionDep, user: CurrentUserDep
):
    f = await folder_service.get_folder_by_id(
        folder_id, db_session, owner_id=str(user.id)
    )
    return FolderOut.model_validate(
        {
            "id": f.id,
            "name": f.name,
            "icon_key": f.icon_key,
            "parent_id": f.parent_id,
            "position": f.position,
            "children": [],
        }
    )


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(folder_id: str, db_session: DBSessionDep, user: CurrentUserDep):
    """
    Delete a folder by its ID.
    Channels in this folder will be moved to root.
    Child folders will be moved up one level.
    """
    await folder_service.delete_folder_by_id(
        folder_id, db_session, owner_id=str(user.id)
    )
