from fastapi import APIRouter, status
from ..dependencies import DBSessionDep
from ..schemas.folder import FolderCreate, FolderUpdate, FolderOut
from ..services import folder_service

router = APIRouter(prefix="/folders", tags=["Folders"])


@router.get("/tree", response_model=list[FolderOut])
async def read_folder_tree(db_session: DBSessionDep):
    return await folder_service.get_tree(db_session)


@router.post("/", response_model=FolderOut, status_code=status.HTTP_201_CREATED)
async def create_folder(payload: FolderCreate, db_session: DBSessionDep):
    f = await folder_service.create_folder(payload, db_session)
    return FolderOut.model_validate(f)


@router.patch("/{folder_id}", response_model=FolderOut)
async def rename_or_move_folder(
    folder_id: int, payload: FolderUpdate, db_session: DBSessionDep
):
    f = await folder_service.update_folder(folder_id, payload, db_session)
    return FolderOut.model_validate(f)
