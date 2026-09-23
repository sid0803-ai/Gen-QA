"""Routes: /api/v1/projects/{project_id}/environments/* (environments domain).

Project-scoped: `viewer` reads, `member` creates/edits, `admin` deletes -
same role convention as every other domain.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, require_project_role
from app.domains.environments import repository, schemas
from app.domains.identity.models import User
from app.domains.projects import repository as project_repository
from app.domains.projects.models import ProjectMember, ProjectRole

router = APIRouter(prefix="/projects", tags=["environments"])


@router.post(
    "/{project_id}/environments",
    response_model=schemas.EnvironmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_environment(
    project_id: uuid.UUID,
    payload: schemas.EnvironmentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.EnvironmentRead:
    try:
        environment = await repository.create_environment(
            db,
            project_id,
            current_user.id,
            name=payload.name,
            base_url=payload.base_url,
            variables=payload.variables,
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Member role required on this project.") from exc
    return schemas.EnvironmentRead.model_validate(environment)


@router.get("/{project_id}/environments", response_model=list[schemas.EnvironmentRead])
async def list_environments(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[schemas.EnvironmentRead]:
    try:
        environments = await repository.list_environments(db, project_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    return [schemas.EnvironmentRead.model_validate(e) for e in environments]


@router.get("/{project_id}/environments/{environment_id}", response_model=schemas.EnvironmentRead)
async def get_environment(
    project_id: uuid.UUID,
    environment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> schemas.EnvironmentRead:
    try:
        environment = await repository.get_environment(db, project_id, environment_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.EnvironmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Environment not found.") from exc
    return schemas.EnvironmentRead.model_validate(environment)


@router.patch("/{project_id}/environments/{environment_id}", response_model=schemas.EnvironmentRead)
async def update_environment(
    project_id: uuid.UUID,
    environment_id: uuid.UUID,
    payload: schemas.EnvironmentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.EnvironmentRead:
    try:
        environment = await repository.update_environment(
            db,
            project_id,
            environment_id,
            current_user.id,
            name=payload.name,
            base_url=payload.base_url,
            variables=payload.variables,
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Member role required on this project.") from exc
    except repository.EnvironmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Environment not found.") from exc
    return schemas.EnvironmentRead.model_validate(environment)


@router.delete("/{project_id}/environments/{environment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_environment(
    project_id: uuid.UUID,
    environment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await repository.delete_environment(db, project_id, environment_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Admin role required on this project.") from exc
    except repository.EnvironmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Environment not found.") from exc
