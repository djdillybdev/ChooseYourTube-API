from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.crud import crud_folder
from ..db.models.folder import Folder
from ..schemas.folder import FolderCreate, FolderUpdate, FolderOut, _UNSET


def _build_tree(folders: list[Folder]) -> list[FolderOut]:
    nodes: dict[int, FolderOut] = {}
    children_map: dict[int | None, list[int]] = {}
    for f in folders:
        nodes[f.id] = FolderOut(
            id=f.id, name=f.name, parent_id=f.parent_id, children=[]
        )
        children_map.setdefault(f.parent_id, []).append(f.id)

    def attach(node_id: int) -> FolderOut:
        node = nodes[node_id]
        for cid in children_map.get(node_id, []):
            node.children.append(attach(cid))
        return node

    roots = [attach(fid) for fid in children_map.get(None, [])]
    return roots


def _assert_not_cycle(
    folders_by_id: dict[int, Folder], moving_id: int, new_parent_id: int | None
):
    cur = new_parent_id
    while cur is not None:
        if cur == moving_id:
            raise HTTPException(
                status_code=400, detail="Cannot move a folder into its descendant."
            )
        cur = folders_by_id[cur].parent_id


async def get_tree(db: AsyncSession) -> list[FolderOut]:
    folders = await crud_folder.get_folders(db, limit=None)
    return _build_tree(folders)


async def get_folder_by_id(folder_id: int, db: AsyncSession) -> Folder:
    folder = await crud_folder.get_folders(db, id=folder_id, first=True)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder


async def create_folder(payload: FolderCreate, db: AsyncSession) -> Folder:
    if payload.parent_id:
        parent = await crud_folder.get_folders(db, id=payload.parent_id, first=True)
        if not parent:
            raise HTTPException(status_code=404, detail="Parent folder not found")
    return await crud_folder.create_folder(
        db, Folder(name=payload.name, parent_id=payload.parent_id)
    )


async def update_folder(
    folder_id: int, payload: FolderUpdate, db: AsyncSession
) -> Folder:
    folder = await crud_folder.get_folders(db, id=folder_id, first=True)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    if payload.parent_id == folder_id:
        raise HTTPException(status_code=400, detail="Folder cannot be its own parent")

    if payload.parent_id is not None and payload.parent_id is not _UNSET:
        parent = await crud_folder.get_folders(db, id=payload.parent_id, first=True)
        if not parent:
            raise HTTPException(status_code=404, detail="New parent not found")
        all_folders = await crud_folder.get_folders(db, limit=None)
        by_id = {f.id: f for f in all_folders}
        _assert_not_cycle(by_id, folder_id, payload.parent_id)

    if payload.name is not None:
        folder.name = payload.name
    if payload.parent_id is not _UNSET:
        folder.parent_id = payload.parent_id

    return await crud_folder.update_folder(db, folder)


async def delete_folder_by_id(folder_id: int, db_session: AsyncSession) -> None:
    """
    Deletes a folder by its ID.

    Before deletion:
    - Channels in this folder are moved to root (folder_id set to None)
    - Child folders are moved up one level (parent_id set to this folder's parent)

    Args:
        folder_id: Folder ID to delete
        db_session: Database session

    Raises:
        HTTPException: If folder not found
    """
    # Get the folder to ensure it exists
    folder = await crud_folder.get_folders(db_session, id=folder_id, first=True)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    # Move channels to root
    for channel in folder.channels:
        channel.folder_id = None

    # Move child folders up one level
    children = await crud_folder.get_folders(
        db_session, parent_id=folder_id, limit=None
    )
    for child in children:
        child.parent_id = folder.parent_id

    # Now safe to delete the folder
    await crud_folder.delete_folder(db_session, folder)
