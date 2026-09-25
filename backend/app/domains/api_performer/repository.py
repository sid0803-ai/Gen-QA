"""Data-access layer for the api_performer domain (project-scoped).

Same isolation rule as every other domain: every function takes
`project_id` + the requesting user's id and enforces membership (and a
minimum role, where relevant) via `project_repository.require_membership`
before touching any row. Rows are additionally always filtered by
`project_id` (folders additionally by `collection_id`), so an id from
another project (or another collection) can never be reached even if
guessed.

Sprint 9 adds `ApiCollection`/`ApiFolder` CRUD alongside the pre-existing
`SavedApiRequest` CRUD, and threads `collection_id`/`folder_id` through the
latter - see `app.domains.api_performer.models`'s module docstring for the
hierarchy this implements (Collection -> Folder (optional, one level) ->
Request).
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.api_performer.models import ApiCollection, ApiFolder, HttpMethod, SavedApiRequest
from app.domains.projects import repository as project_repository
from app.domains.projects.models import ProjectRole


class SavedApiRequestNotFoundError(Exception):
    """Saved request doesn't exist in this project (or the project doesn't) -> 404."""


class ApiCollectionNotFoundError(Exception):
    """Collection doesn't exist in this project (or the project doesn't) -> 404."""


class ApiFolderNotFoundError(Exception):
    """Folder doesn't exist in this collection (or the collection/project doesn't) -> 404."""


class FolderNotInCollectionError(Exception):
    """`folder_id` resolves to a real folder, but not one that belongs to the
    given `collection_id` -> 400."""


# --- ApiCollection ---------------------------------------------------------


async def _get_collection_row(
    db: AsyncSession, project_id: uuid.UUID, collection_id: uuid.UUID
) -> ApiCollection | None:
    stmt = select(ApiCollection).where(
        ApiCollection.id == collection_id, ApiCollection.project_id == project_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_collection(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID, *, name: str
) -> ApiCollection:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    collection = ApiCollection(project_id=project_id, name=name, created_by=user_id)
    db.add(collection)
    await db.commit()
    await db.refresh(collection)
    return collection


async def list_collections(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID
) -> list[ApiCollection]:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    stmt = (
        select(ApiCollection)
        .where(ApiCollection.project_id == project_id)
        .order_by(ApiCollection.sequence.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_collection(
    db: AsyncSession, project_id: uuid.UUID, collection_id: uuid.UUID, user_id: uuid.UUID
) -> ApiCollection:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    collection = await _get_collection_row(db, project_id, collection_id)
    if collection is None:
        raise ApiCollectionNotFoundError()
    return collection


async def update_collection(
    db: AsyncSession,
    project_id: uuid.UUID,
    collection_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    name: str | None,
) -> ApiCollection:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    collection = await _get_collection_row(db, project_id, collection_id)
    if collection is None:
        raise ApiCollectionNotFoundError()

    if name is not None:
        collection.name = name

    await db.commit()
    await db.refresh(collection)
    return collection


async def delete_collection(
    db: AsyncSession, project_id: uuid.UUID, collection_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Deletes the collection - cascades (DB-level ON DELETE CASCADE) to its
    folders and requests. A real, user-facing destructive action, same
    posture as deleting a project cascading everything in it."""
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.admin)
    collection = await _get_collection_row(db, project_id, collection_id)
    if collection is None:
        raise ApiCollectionNotFoundError()

    await db.delete(collection)
    await db.commit()


# --- ApiFolder ---------------------------------------------------------


async def _get_folder_row(
    db: AsyncSession, collection_id: uuid.UUID, folder_id: uuid.UUID
) -> ApiFolder | None:
    stmt = select(ApiFolder).where(ApiFolder.id == folder_id, ApiFolder.collection_id == collection_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_folder(
    db: AsyncSession,
    project_id: uuid.UUID,
    collection_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    name: str,
) -> ApiFolder:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    collection = await _get_collection_row(db, project_id, collection_id)
    if collection is None:
        raise ApiCollectionNotFoundError()

    folder = ApiFolder(collection_id=collection_id, name=name, created_by=user_id)
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return folder


async def list_folders(
    db: AsyncSession, project_id: uuid.UUID, collection_id: uuid.UUID, user_id: uuid.UUID
) -> list[ApiFolder]:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    collection = await _get_collection_row(db, project_id, collection_id)
    if collection is None:
        raise ApiCollectionNotFoundError()

    stmt = (
        select(ApiFolder)
        .where(ApiFolder.collection_id == collection_id)
        .order_by(ApiFolder.sequence.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_folder(
    db: AsyncSession,
    project_id: uuid.UUID,
    collection_id: uuid.UUID,
    folder_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    name: str | None,
) -> ApiFolder:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    collection = await _get_collection_row(db, project_id, collection_id)
    if collection is None:
        raise ApiCollectionNotFoundError()
    folder = await _get_folder_row(db, collection_id, folder_id)
    if folder is None:
        raise ApiFolderNotFoundError()

    if name is not None:
        folder.name = name

    await db.commit()
    await db.refresh(folder)
    return folder


async def delete_folder(
    db: AsyncSession,
    project_id: uuid.UUID,
    collection_id: uuid.UUID,
    folder_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Deletes the folder. Its requests are NOT deleted - `SavedApiRequest.
    folder_id` is ON DELETE SET NULL, so they simply move back to the
    collection's top level (DB-enforced, nothing extra to do here)."""
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.admin)
    collection = await _get_collection_row(db, project_id, collection_id)
    if collection is None:
        raise ApiCollectionNotFoundError()
    folder = await _get_folder_row(db, collection_id, folder_id)
    if folder is None:
        raise ApiFolderNotFoundError()

    await db.delete(folder)
    await db.commit()


# --- Tree --------------------------------------------------------------


async def get_tree(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID
) -> list[ApiCollection]:
    """Returns every collection in the project, each with its folders and
    requests eagerly loaded, ordered `sequence` desc at every level, for the
    router to shape into the lightweight tree response. See
    `app.domains.api_performer.schemas.ApiCollectionTreeNode` for the exact
    response shape."""
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    stmt = (
        select(ApiCollection)
        .where(ApiCollection.project_id == project_id)
        .order_by(ApiCollection.sequence.desc())
        .options(
            selectinload(ApiCollection.folders).selectinload(ApiFolder.requests),
            selectinload(ApiCollection.requests),
        )
    )
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


# --- SavedApiRequest ---------------------------------------------------


async def _get_request_row(
    db: AsyncSession, project_id: uuid.UUID, request_id: uuid.UUID
) -> SavedApiRequest | None:
    stmt = select(SavedApiRequest).where(
        SavedApiRequest.id == request_id, SavedApiRequest.project_id == project_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _validate_collection_and_folder(
    db: AsyncSession,
    project_id: uuid.UUID,
    collection_id: uuid.UUID,
    folder_id: uuid.UUID | None,
) -> None:
    """Raises ApiCollectionNotFoundError if `collection_id` doesn't resolve
    in this project, ApiFolderNotFoundError if `folder_id` is given but
    doesn't resolve in this project, or FolderNotInCollectionError if it
    resolves but belongs to a different collection."""
    collection = await _get_collection_row(db, project_id, collection_id)
    if collection is None:
        raise ApiCollectionNotFoundError()

    if folder_id is None:
        return

    stmt = select(ApiFolder).join(ApiCollection, ApiFolder.collection_id == ApiCollection.id).where(
        ApiFolder.id == folder_id, ApiCollection.project_id == project_id
    )
    result = await db.execute(stmt)
    folder = result.scalar_one_or_none()
    if folder is None:
        raise ApiFolderNotFoundError()
    if folder.collection_id != collection_id:
        raise FolderNotInCollectionError()


async def create_saved_request(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    name: str,
    method: HttpMethod,
    url: str,
    headers: dict[str, str] | None,
    query_params: dict[str, str] | None,
    body: str | None,
    environment_id: uuid.UUID | None,
    collection_id: uuid.UUID,
    folder_id: uuid.UUID | None,
) -> SavedApiRequest:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    await _validate_collection_and_folder(db, project_id, collection_id, folder_id)

    saved_request = SavedApiRequest(
        project_id=project_id,
        collection_id=collection_id,
        folder_id=folder_id,
        name=name,
        method=method,
        url=url,
        headers=headers or {},
        query_params=query_params or {},
        body=body,
        environment_id=environment_id,
        created_by=user_id,
    )
    db.add(saved_request)
    await db.commit()
    await db.refresh(saved_request)
    return saved_request


async def list_saved_requests(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID
) -> list[SavedApiRequest]:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    stmt = (
        select(SavedApiRequest)
        .where(SavedApiRequest.project_id == project_id)
        .order_by(SavedApiRequest.sequence.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_saved_request(
    db: AsyncSession, project_id: uuid.UUID, request_id: uuid.UUID, user_id: uuid.UUID
) -> SavedApiRequest:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    saved_request = await _get_request_row(db, project_id, request_id)
    if saved_request is None:
        raise SavedApiRequestNotFoundError()
    return saved_request


async def update_saved_request(
    db: AsyncSession,
    project_id: uuid.UUID,
    request_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    name: str | None,
    method: HttpMethod | None,
    url: str | None,
    headers: dict[str, str] | None,
    query_params: dict[str, str] | None,
    body: str | None,
    environment_id: uuid.UUID | None,
    folder_id: uuid.UUID | None,
    folder_id_set: bool,
) -> SavedApiRequest:
    """`folder_id`/`folder_id_set` implement the one deliberate exception to
    this codebase's blanket "omitted and explicit null both mean unchanged"
    PATCH convention - see `schemas.SavedApiRequestUpdate`'s docstring.
    `folder_id_set=False` means the key was omitted (leave unchanged);
    `folder_id_set=True` means the key was present in the request body,
    including as `null` (clear it back to the collection's top level, or set
    it to a new folder - validated against the request's own, unchanged,
    `collection_id`). `collection_id` itself is not patchable this sprint
    (see the schema docstring)."""
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    saved_request = await _get_request_row(db, project_id, request_id)
    if saved_request is None:
        raise SavedApiRequestNotFoundError()

    if name is not None:
        saved_request.name = name
    if method is not None:
        saved_request.method = method
    if url is not None:
        saved_request.url = url
    if headers is not None:
        saved_request.headers = headers
    if query_params is not None:
        saved_request.query_params = query_params
    if body is not None:
        saved_request.body = body
    if environment_id is not None:
        saved_request.environment_id = environment_id

    if folder_id_set:
        if folder_id is None:
            saved_request.folder_id = None
        else:
            await _validate_collection_and_folder(
                db, project_id, saved_request.collection_id, folder_id
            )
            saved_request.folder_id = folder_id

    await db.commit()
    await db.refresh(saved_request)
    return saved_request


async def delete_saved_request(
    db: AsyncSession, project_id: uuid.UUID, request_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.admin)
    saved_request = await _get_request_row(db, project_id, request_id)
    if saved_request is None:
        raise SavedApiRequestNotFoundError()

    await db.delete(saved_request)
    await db.commit()
