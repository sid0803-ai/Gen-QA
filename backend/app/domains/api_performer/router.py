"""Routes: /api/v1/projects/{project_id}/api-requests/* (api_performer
domain, "API Performer" - a built-in, Postman-lite ad-hoc HTTP request tool).

Project-scoped: `viewer` reads, `member` creates/edits/executes, `admin`
deletes - same role convention as every other domain (`environments` in
particular). See `app.domains.api_performer.models`'s module docstring for
this domain's deliberate scope cuts (no execution history, SSRF).
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
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Member role required on this project.") from exc
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
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Member role required on this project.") from exc
    except repository.SavedApiRequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Saved API request not found.") from exc
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
