"""Routes: /api/v1/projects/{project_id}/api-requests/*,
/api/v1/projects/{project_id}/api-collections/* (api_performer domain,
"API Performer" - a built-in, Postman-lite ad-hoc HTTP request tool).

Project-scoped: `viewer` reads, `member` creates/edits/executes, `admin`
deletes - same role convention as every other domain (`environments` in
particular). See `app.domains.api_performer.models`'s module docstring for
this domain's deliberate scope cuts (no execution history, SSRF, single-
level folder nesting).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, require_project_role
from app.domains.api_performer import repository, schemas, service
from app.domains.api_performer.models import HttpMethod
from app.domains.environments import repository as environments_repository
from app.domains.identity.models import User
from app.domains.projects import repository as project_repository
from app.domains.projects.models import ProjectMember, ProjectRole

router = APIRouter(prefix="/projects", tags=["api-performer"])


# --- ApiCollection ---------------------------------------------------------


@router.post(
    "/{project_id}/api-collections",
    response_model=schemas.ApiCollectionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_collection(
    project_id: uuid.UUID,
    payload: schemas.ApiCollectionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.ApiCollectionRead:
    try:
        collection = await repository.create_collection(
            db, project_id, current_user.id, name=payload.name
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Member role required on this project.") from exc
    return schemas.ApiCollectionRead.model_validate(collection)


@router.get("/{project_id}/api-collections", response_model=list[schemas.ApiCollectionRead])
async def list_collections(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[schemas.ApiCollectionRead]:
    try:
        collections = await repository.list_collections(db, project_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    return [schemas.ApiCollectionRead.model_validate(c) for c in collections]


@router.get("/{project_id}/api-collections/tree", response_model=list[schemas.TreeCollectionNode])
async def get_collection_tree(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[schemas.TreeCollectionNode]:
    """One call for the frontend's sidebar instead of N+1 - see
    `schemas.TreeCollectionNode`'s docstring for the exact nesting/uniqueness
    guarantee (a request appears in exactly one place)."""
    try:
        collections = await repository.get_tree(db, project_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    return [schemas.TreeCollectionNode.model_validate(c) for c in collections]


@router.patch("/{project_id}/api-collections/{collection_id}", response_model=schemas.ApiCollectionRead)
async def update_collection(
    project_id: uuid.UUID,
    collection_id: uuid.UUID,
    payload: schemas.ApiCollectionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.ApiCollectionRead:
    try:
        collection = await repository.update_collection(
            db, project_id, collection_id, current_user.id, name=payload.name
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Member role required on this project.") from exc
    except repository.ApiCollectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Collection not found.") from exc
    return schemas.ApiCollectionRead.model_validate(collection)


@router.delete("/{project_id}/api-collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    project_id: uuid.UUID,
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await repository.delete_collection(db, project_id, collection_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Admin role required on this project.") from exc
    except repository.ApiCollectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Collection not found.") from exc


# --- ApiFolder ---------------------------------------------------------


@router.post(
    "/{project_id}/api-collections/{collection_id}/folders",
    response_model=schemas.ApiFolderRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_folder(
    project_id: uuid.UUID,
    collection_id: uuid.UUID,
    payload: schemas.ApiFolderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.ApiFolderRead:
    try:
        folder = await repository.create_folder(
            db, project_id, collection_id, current_user.id, name=payload.name
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Member role required on this project.") from exc
    except repository.ApiCollectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Collection not found.") from exc
    return schemas.ApiFolderRead.model_validate(folder)


@router.get(
    "/{project_id}/api-collections/{collection_id}/folders", response_model=list[schemas.ApiFolderRead]
)
async def list_folders(
    project_id: uuid.UUID,
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[schemas.ApiFolderRead]:
    try:
        folders = await repository.list_folders(db, project_id, collection_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.ApiCollectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Collection not found.") from exc
    return [schemas.ApiFolderRead.model_validate(f) for f in folders]


@router.patch(
    "/{project_id}/api-collections/{collection_id}/folders/{folder_id}",
    response_model=schemas.ApiFolderRead,
)
async def update_folder(
    project_id: uuid.UUID,
    collection_id: uuid.UUID,
    folder_id: uuid.UUID,
    payload: schemas.ApiFolderUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.ApiFolderRead:
    try:
        folder = await repository.update_folder(
            db, project_id, collection_id, folder_id, current_user.id, name=payload.name
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Member role required on this project.") from exc
    except repository.ApiCollectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Collection not found.") from exc
    except repository.ApiFolderNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Folder not found.") from exc
    return schemas.ApiFolderRead.model_validate(folder)


@router.delete(
    "/{project_id}/api-collections/{collection_id}/folders/{folder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_folder(
    project_id: uuid.UUID,
    collection_id: uuid.UUID,
    folder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await repository.delete_folder(db, project_id, collection_id, folder_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Admin role required on this project.") from exc
    except repository.ApiCollectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Collection not found.") from exc
    except repository.ApiFolderNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Folder not found.") from exc


async def _run_execute(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    method: HttpMethod,
    url: str,
    headers: dict[str, str],
    query_params: dict[str, str],
    body: str | None,
    environment_id: uuid.UUID | None,
) -> schemas.ExecuteResponse:
    try:
        environment = await service.resolve_environment(db, project_id, environment_id, user_id)
    except environments_repository.EnvironmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Environment not found.") from exc

    sub_url, sub_headers, sub_query_params, sub_body = service.apply_substitution(
        url=url, headers=headers, query_params=query_params, body=body, environment=environment
    )

    try:
        result = await service.execute_http_request(
            method=method, url=sub_url, headers=sub_headers, query_params=sub_query_params, body=sub_body
        )
    except service.InvalidSchemeError as exc:
        raise HTTPException(status_code=400, detail="Only http/https URLs are supported.") from exc

    return schemas.ExecuteResponse(**result)


@router.post(
    "/{project_id}/api-requests",
    response_model=schemas.SavedApiRequestRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_saved_request(
    project_id: uuid.UUID,
    payload: schemas.SavedApiRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.SavedApiRequestRead:
    try:
        saved_request = await repository.create_saved_request(
            db,
            project_id,
            current_user.id,
            name=payload.name,
            method=payload.method,
            url=payload.url,
            headers=payload.headers,
            query_params=payload.query_params,
            body=payload.body,
            environment_id=payload.environment_id,
            collection_id=payload.collection_id,
            folder_id=payload.folder_id,
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Member role required on this project.") from exc
    except repository.ApiCollectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Collection not found.") from exc
    except repository.ApiFolderNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Folder not found.") from exc
    except repository.FolderNotInCollectionError as exc:
        raise HTTPException(
            status_code=400, detail="Folder does not belong to the given collection."
        ) from exc
    return schemas.SavedApiRequestRead.model_validate(saved_request)


@router.get("/{project_id}/api-requests", response_model=list[schemas.SavedApiRequestRead])
async def list_saved_requests(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[schemas.SavedApiRequestRead]:
    try:
        saved_requests = await repository.list_saved_requests(db, project_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    return [schemas.SavedApiRequestRead.model_validate(r) for r in saved_requests]


@router.get("/{project_id}/api-requests/{request_id}", response_model=schemas.SavedApiRequestRead)
async def get_saved_request(
    project_id: uuid.UUID,
    request_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> schemas.SavedApiRequestRead:
    try:
        saved_request = await repository.get_saved_request(db, project_id, request_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.SavedApiRequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Saved API request not found.") from exc
    return schemas.SavedApiRequestRead.model_validate(saved_request)


@router.patch("/{project_id}/api-requests/{request_id}", response_model=schemas.SavedApiRequestRead)
async def update_saved_request(
    project_id: uuid.UUID,
    request_id: uuid.UUID,
    payload: schemas.SavedApiRequestUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.SavedApiRequestRead:
    # `folder_id` is the one field on this PATCH that distinguishes "key
    # omitted" from "key present as null" - see schemas.SavedApiRequestUpdate's
    # docstring. Every other field keeps the ordinary blanket convention.
    folder_id_set = "folder_id" in payload.model_fields_set
    try:
        saved_request = await repository.update_saved_request(
            db,
            project_id,
            request_id,
            current_user.id,
            name=payload.name,
            method=payload.method,
            url=payload.url,
            headers=payload.headers,
            query_params=payload.query_params,
            body=payload.body,
            environment_id=payload.environment_id,
            folder_id=payload.folder_id,
            folder_id_set=folder_id_set,
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Member role required on this project.") from exc
    except repository.SavedApiRequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Saved API request not found.") from exc
    except repository.ApiFolderNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Folder not found.") from exc
    except repository.FolderNotInCollectionError as exc:
        raise HTTPException(
            status_code=400, detail="Folder does not belong to the given collection."
        ) from exc
    return schemas.SavedApiRequestRead.model_validate(saved_request)


@router.delete("/{project_id}/api-requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_request(
    project_id: uuid.UUID,
    request_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await repository.delete_saved_request(db, project_id, request_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Admin role required on this project.") from exc
    except repository.SavedApiRequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Saved API request not found.") from exc


@router.post("/{project_id}/api-requests/execute", response_model=schemas.ExecuteResponse)
async def execute_ad_hoc_request(
    project_id: uuid.UUID,
    payload: schemas.AdHocExecuteRequest,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.member)),
    db: AsyncSession = Depends(get_db),
) -> schemas.ExecuteResponse:
    """Ad-hoc execution - nothing persisted. See module docstring."""
    return await _run_execute(
        db,
        project_id,
        current_user.id,
        method=payload.method,
        url=payload.url,
        headers=payload.headers,
        query_params=payload.query_params,
        body=payload.body,
        environment_id=payload.environment_id,
    )


@router.post("/{project_id}/api-requests/{request_id}/execute", response_model=schemas.ExecuteResponse)
async def execute_saved_request(
    project_id: uuid.UUID,
    request_id: uuid.UUID,
    payload: schemas.SavedRequestExecuteOverride | None = None,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.member)),
    db: AsyncSession = Depends(get_db),
) -> schemas.ExecuteResponse:
    """Executes a saved request. Optional body `{environment_id?}` overrides
    the saved request's own `environment_id` for this one run only - nothing
    is persisted (no execution history; see module docstring)."""
    try:
        saved_request = await repository.get_saved_request(db, project_id, request_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.SavedApiRequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Saved API request not found.") from exc

    environment_id = saved_request.environment_id
    if payload is not None and payload.environment_id is not None:
        environment_id = payload.environment_id

    return await _run_execute(
        db,
        project_id,
        current_user.id,
        method=saved_request.method,
        url=saved_request.url,
        headers=saved_request.headers,
        query_params=saved_request.query_params,
        body=saved_request.body,
        environment_id=environment_id,
    )
