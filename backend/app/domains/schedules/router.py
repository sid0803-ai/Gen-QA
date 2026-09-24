"""Routes: /api/v1/projects/{project_id}/schedules/* (schedules domain).

Project-scoped: `viewer` reads, `member` creates/edits, `admin` deletes -
same role convention as every other domain (see e.g.
`app.domains.environments.router`).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, require_project_role
from app.domains.identity.models import User
from app.domains.projects import repository as project_repository
from app.domains.projects.models import ProjectMember, ProjectRole
from app.domains.schedules import repository, schemas

router = APIRouter(prefix="/projects", tags=["schedules"])


@router.post(
    "/{project_id}/schedules",
    response_model=schemas.ScheduledJobRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_schedule(
    project_id: uuid.UUID,
    payload: schemas.ScheduledJobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.ScheduledJobRead:
    try:
        schedule = await repository.create_schedule(
            db,
            project_id,
            current_user.id,
            name=payload.name,
            test_case_id=payload.test_case_id,
            environment_id=payload.environment_id,
            cron_expression=payload.cron_expression,
            enabled=payload.enabled,
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Member role required on this project.") from exc
    except repository.TestCaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Test case not found.") from exc
    except repository.EnvironmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Environment not found.") from exc
    except repository.InvalidCronExpressionError as exc:
        raise HTTPException(status_code=400, detail="cron_expression is not a valid cron expression.") from exc
    except repository.NoApprovedAutomationScriptError as exc:
        raise HTTPException(
            status_code=400, detail="Test case has no approved automation script."
        ) from exc
    return schemas.ScheduledJobRead.model_validate(schedule)


@router.get("/{project_id}/schedules", response_model=list[schemas.ScheduledJobRead])
async def list_schedules(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[schemas.ScheduledJobRead]:
    try:
        schedules = await repository.list_schedules(db, project_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    return [schemas.ScheduledJobRead.model_validate(s) for s in schedules]


@router.get("/{project_id}/schedules/{schedule_id}", response_model=schemas.ScheduledJobRead)
async def get_schedule(
    project_id: uuid.UUID,
    schedule_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> schemas.ScheduledJobRead:
    try:
        schedule = await repository.get_schedule(db, project_id, schedule_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.ScheduledJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Scheduled job not found.") from exc
    return schemas.ScheduledJobRead.model_validate(schedule)


@router.patch("/{project_id}/schedules/{schedule_id}", response_model=schemas.ScheduledJobRead)
async def update_schedule(
    project_id: uuid.UUID,
    schedule_id: uuid.UUID,
    payload: schemas.ScheduledJobUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.ScheduledJobRead:
    try:
        schedule = await repository.update_schedule(
            db,
            project_id,
            schedule_id,
            current_user.id,
            name=payload.name,
            cron_expression=payload.cron_expression,
            enabled=payload.enabled,
            environment_id=payload.environment_id,
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Member role required on this project.") from exc
    except repository.ScheduledJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Scheduled job not found.") from exc
    except repository.EnvironmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Environment not found.") from exc
    except repository.InvalidCronExpressionError as exc:
        raise HTTPException(status_code=400, detail="cron_expression is not a valid cron expression.") from exc
    return schemas.ScheduledJobRead.model_validate(schedule)


@router.delete("/{project_id}/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    project_id: uuid.UUID,
    schedule_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await repository.delete_schedule(db, project_id, schedule_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Admin role required on this project.") from exc
    except repository.ScheduledJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Scheduled job not found.") from exc
