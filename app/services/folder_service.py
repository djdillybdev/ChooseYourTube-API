import uuid
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.crud import crud_folder
from ..db.models.folder import Folder
from ..schemas.folder import FolderCreate, FolderUpdate, FolderOut, _UNSET


def _build_tree(folders: list[Folder]) -> list[FolderOut]:
    nodes: dict[str, FolderOut] = {}
    children_map: dict[str | None, list[str]] = {}
    for f in folders:
        nodes[f.id] = FolderOut(
            id=f.id,
            name=f.name,
            icon_key=f.icon_key,
            parent_id=f.parent_id,
            position=f.position,
            children=[],
        )
        children_map.setdefault(f.parent_id, []).append(f.id)

    def sorted_children(parent_id: str | None) -> list[str]:
        return sorted(
            children_map.get(parent_id, []),
            key=lambda cid: (nodes[cid].position, nodes[cid].name, nodes[cid].id),
        )

    def attach(node_id: str) -> FolderOut:
        node = nodes[node_id]
        for cid in sorted_children(node_id):
            node.children.append(attach(cid))
        return node

    roots = [attach(fid) for fid in sorted_children(None)]
    return roots


def _assert_not_cycle(
    folders_by_id: dict[str, Folder], moving_id: str, new_parent_id: str | None
):
    cur = new_parent_id
    while cur is not None:
        if cur == moving_id:
            raise HTTPException(
                status_code=400, detail="Cannot move a folder into its descendant."
            )
        cur = folders_by_id[cur].parent_id


async def get_tree(db: AsyncSession, owner_id: str = "test-user") -> list[FolderOut]:
    folders = await crud_folder.get_folders(db, owner_id=owner_id, limit=None)
    return _build_tree(folders)


async def get_folder_by_id(
    folder_id: str, db: AsyncSession, owner_id: str = "test-user"
) -> Folder:
    folder = await crud_folder.get_folders(
        db, owner_id=owner_id, id=folder_id, first=True
    )
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder


async def create_folder(
    payload: FolderCreate, db: AsyncSession, owner_id: str = "test-user"
) -> Folder:
    if payload.parent_id:
        parent = await crud_folder.get_folders(
            db, owner_id=owner_id, id=payload.parent_id, first=True
        )
        if not parent:
            raise HTTPException(status_code=404, detail="Parent folder not found")

    # Generate UUID for new folder
    folder_id = str(uuid.uuid4())
    max_position = await crud_folder.get_max_position(
        db, payload.parent_id, owner_id=owner_id
    )
    if payload.position is None:
        new_position = max_position + 1
    else:
        new_position = min(payload.position, max_position + 1)
        await crud_folder.shift_positions_for_insert(
            db, payload.parent_id, new_position, owner_id=owner_id
        )

    return await crud_folder.create_folder(
        db,
        Folder(
            id=folder_id,
            owner_id=owner_id,
            name=payload.name,
            parent_id=payload.parent_id,
            icon_key=payload.icon_key,
            position=new_position,
        ),
    )


async def update_folder(
    folder_id: str,
    payload: FolderUpdate,
    db: AsyncSession,
    owner_id: str = "test-user",
) -> Folder:
    folder = await crud_folder.get_folders(
        db, owner_id=owner_id, id=folder_id, first=True
    )
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    if payload.parent_id == folder_id:
        raise HTTPException(status_code=400, detail="Folder cannot be its own parent")

    if payload.parent_id is not None and payload.parent_id is not _UNSET:
        parent = await crud_folder.get_folders(
            db, owner_id=owner_id, id=payload.parent_id, first=True
        )
        if not parent:
            raise HTTPException(status_code=404, detail="New parent not found")
        all_folders = await crud_folder.get_folders(db, owner_id=owner_id, limit=None)
        by_id = {f.id: f for f in all_folders}
        _assert_not_cycle(by_id, folder_id, payload.parent_id)

    target_parent_id = (
        folder.parent_id if payload.parent_id is _UNSET else payload.parent_id
    )

    if payload.parent_id is not _UNSET and target_parent_id != folder.parent_id:
        await crud_folder.shift_positions_after_removal(
            db, folder.parent_id, folder.position, owner_id=owner_id
        )

        max_position = await crud_folder.get_max_position(
            db, target_parent_id, owner_id=owner_id
        )
        if payload.position is None:
            new_position = max_position + 1
        else:
            new_position = min(payload.position, max_position + 1)
            await crud_folder.shift_positions_for_insert(
                db, target_parent_id, new_position, owner_id=owner_id
            )

        folder.parent_id = target_parent_id
        folder.position = new_position
    elif payload.position is not None and payload.position != folder.position:
        max_position = await crud_folder.get_max_position(
            db, folder.parent_id, owner_id=owner_id
        )
        new_position = min(payload.position, max_position)
        await crud_folder.shift_positions_for_move(
            db, folder.parent_id, folder.position, new_position, owner_id=owner_id
        )
        folder.position = new_position

    if payload.name is not None:
        folder.name = payload.name
    if payload.icon_key is not None:
        folder.icon_key = payload.icon_key
    return await crud_folder.update_folder(db, folder)


async def delete_folder_by_id(
    folder_id: str, db_session: AsyncSession, owner_id: str = "test-user"
) -> None:
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
    folder = await crud_folder.get_folders(
        db_session, owner_id=owner_id, id=folder_id, first=True
    )
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    # Move channels to root
    for channel in folder.channels:
        channel.folder_id = None

    # Move child folders up one level
    children = await crud_folder.get_folders(
        db_session, owner_id=owner_id, parent_id=folder_id, limit=None
    )
    for child in children:
        child.parent_id = folder.parent_id

    # Now safe to delete the folder
    await crud_folder.delete_folder(db_session, folder)
