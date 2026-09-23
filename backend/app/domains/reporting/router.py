"""Routes: /api/v1/projects/{project_id}/dashboard,
/api/v1/projects/{project_id}/reports/*, and
/api/v1/projects/{project_id}/requirements/{requirement_id}/coverage
(reporting domain, Sprint 6 - new, read-only).

Every endpoint here is a `viewer`-role read, same as every other GET route
in this codebase: `project_repository.require_membership` (called inside
repository.py) raises `NotAMemberError` for a non-member -> 404 (never 403,
so project existence is never leaked), and each route additionally declares
`Depends(require_project_role(ProjectRole.viewer))` as a belt-and-braces
gate, matching the existing routers' own convention.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, require_project_role
from app.domains.identity.models import User
from app.domains.projects import repository as project_repository
from app.domains.projects.models import ProjectMember, ProjectRole
from app.domains.reporting import repository, schemas

router = APIRouter(prefix="/projects", tags=["reporting"])


@router.get("/{project_id}/dashboard", response_model=schemas.DashboardRead)
async def get_dashboard(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> schemas.DashboardRead:
    try:
        data = await repository.get_dashboard(db, project_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    return schemas.DashboardRead.model_validate(data)


@router.get("/{project_id}/reports/trend", response_model=list[schemas.TrendPoint])
async def get_trend(
    project_id: uuid.UUID,
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[schemas.TrendPoint]:
    try:
        data = await repository.get_trend(db, project_id, current_user.id, days=days)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    return [schemas.TrendPoint.model_validate(point) for point in data]


@router.get("/{project_id}/reports/breakdown", response_model=schemas.BreakdownRead)
async def get_breakdown(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> schemas.BreakdownRead:
    try:
        data = await repository.get_breakdown(db, project_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    return schemas.BreakdownRead.model_validate(data)


@router.get(
    "/{project_id}/requirements/{requirement_id}/coverage",
    response_model=schemas.RequirementCoverageRead,
)
async def get_requirement_coverage(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> schemas.RequirementCoverageRead:
    try:
        data = await repository.get_requirement_coverage(
            db, project_id, requirement_id, current_user.id
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requirement not found.") from exc
    return schemas.RequirementCoverageRead.model_validate(data)
