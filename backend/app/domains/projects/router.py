"""Routes: /api/v1/projects/* (projects domain)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, require_project_role
from app.domains.identity.models import User
from app.domains.projects import repository, schemas, service
from app.domains.projects.models import ProjectMember, ProjectRole

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=schemas.ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: schemas.ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.ProjectRead:
    project = await repository.create_project(
        db, payload.name, payload.description, current_user.id
    )
    return schemas.ProjectRead.model_validate(project)


@router.get("", response_model=list[schemas.ProjectListItem])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[schemas.ProjectListItem]:
    rows = await repository.list_projects_for_user(db, current_user.id)
    return [
        schemas.ProjectListItem(
            id=project.id,
            name=project.name,
            description=project.description,
            created_at=project.created_at,
            role=role,
        )
        for project, role in rows
    ]


@router.get("/{project_id}", response_model=schemas.ProjectRead)
async def get_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> schemas.ProjectRead:
    try:
        project = await repository.get_project_detail(db, project_id, current_user.id)
    except repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    return schemas.ProjectRead.model_validate(project)


@router.patch("/{project_id}", response_model=schemas.ProjectRead)
async def update_project(
    project_id: uuid.UUID,
    payload: schemas.ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.ProjectRead:
    try:
        project = await repository.update_project(
            db, project_id, current_user.id, name=payload.name, description=payload.description
        )
    except repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.InsufficientRoleError as exc:
        raise HTTPException(
            status_code=403, detail="Admin role required on this project."
        ) from exc
    return schemas.ProjectRead.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await repository.delete_project(db, project_id, current_user.id)
    except repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.InsufficientRoleError as exc:
        raise HTTPException(
            status_code=403, detail="Admin role required on this project."
        ) from exc


@router.get("/{project_id}/members", response_model=list[schemas.MemberRead])
async def list_members(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[schemas.MemberRead]:
    try:
        members = await repository.list_members(db, project_id, current_user.id)
    except repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    return [
        schemas.MemberRead(
            user_id=m.user_id, email=m.user.email, full_name=m.user.full_name, role=m.role
        )
        for m in members
    ]


@router.post(
    "/{project_id}/members", response_model=schemas.MemberRead, status_code=status.HTTP_201_CREATED
)
async def add_member(
    project_id: uuid.UUID,
    payload: schemas.MemberAdd,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.MemberRead:
    try:
        membership = await service.add_member_by_email(
            db, project_id, current_user.id, payload.email, payload.role
        )
    except repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.InsufficientRoleError as exc:
        raise HTTPException(
            status_code=403, detail="Admin role required on this project."
        ) from exc
    except service.UserNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="No registered user found with that email."
        ) from exc
    except repository.AlreadyMemberError as exc:
        raise HTTPException(
            status_code=409, detail="User is already a member of this project."
        ) from exc

    return schemas.MemberRead(
        user_id=membership.user_id,
        email=membership.user.email,
        full_name=membership.user.full_name,
        role=membership.role,
    )


@router.patch("/{project_id}/members/{user_id}", response_model=schemas.MemberRead)
async def update_member_role(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: schemas.MemberRoleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.MemberRead:
    try:
        membership = await repository.update_member_role(
            db, project_id, current_user.id, user_id, payload.role
        )
    except repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.InsufficientRoleError as exc:
        raise HTTPException(
            status_code=403, detail="Admin role required on this project."
        ) from exc
    except repository.TargetNotAMemberError as exc:
        raise HTTPException(
            status_code=404, detail="User is not a member of this project."
        ) from exc
    except repository.LastAdminError as exc:
        raise HTTPException(
            status_code=409, detail="A project must always have at least one admin."
        ) from exc

    return schemas.MemberRead(
        user_id=membership.user_id,
        email=membership.user.email,
        full_name=membership.user.full_name,
        role=membership.role,
    )


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await repository.remove_member(db, project_id, current_user.id, user_id)
    except repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.InsufficientRoleError as exc:
        raise HTTPException(
            status_code=403, detail="Admin role required on this project."
        ) from exc
    except repository.TargetNotAMemberError as exc:
        raise HTTPException(
            status_code=404, detail="User is not a member of this project."
        ) from exc
    except repository.LastAdminError as exc:
        raise HTTPException(
            status_code=409, detail="A project must always have at least one admin."
        ) from exc
