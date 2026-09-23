"""Routes: /api/v1/projects/{project_id}/executions/* (executions domain).

Project-scoped, references a test case + an environment. `viewer` reads,
`member` creates (both manual and automated). There is no update/delete
endpoint - an execution is an immutable record of something that happened
(or is happening); a bad manual entry is superseded by recording a new one,
not edited in place.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, require_project_role
from app.domains.executions import repository, schemas, service
from app.domains.executions.models import ExecutionKind, ExecutionStatus
from app.domains.identity.models import User
from app.domains.projects import repository as project_repository
from app.domains.projects.models import ProjectMember, ProjectRole

router = APIRouter(prefix="/projects", tags=["executions"])


@router.post(
    "/{project_id}/executions",
    response_model=schemas.ExecutionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_execution(
    project_id: uuid.UUID,
    payload: schemas.ExecutionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.ExecutionRead:
    try:
        if payload.type == ExecutionKind.manual:
            execution = await service.create_manual_execution(
                db,
                project_id,
                current_user.id,
                test_case_id=payload.test_case_id,
                environment_id=payload.environment_id,
                result_status=payload.status,
                actual_result=payload.actual_result,
                comments=payload.comments,
            )
        else:
            execution = await service.create_automated_execution(
                db,
                project_id,
                current_user.id,
                test_case_id=payload.test_case_id,
                environment_id=payload.environment_id,
            )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Member role required on this project.") from exc
    except repository.TestCaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Test case not found.") from exc
    except repository.EnvironmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Environment not found.") from exc
    except repository.NoApprovedAutomationScriptError as exc:
        raise HTTPException(
            status_code=409, detail="This test case has no approved automation script."
        ) from exc
    return schemas.ExecutionRead.model_validate(execution)


@router.get("/{project_id}/executions", response_model=list[schemas.ExecutionRead])
async def list_executions(
    project_id: uuid.UUID,
    test_case_id: uuid.UUID | None = None,
    status: ExecutionStatus | None = None,
    type: ExecutionKind | None = None,
    environment_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[schemas.ExecutionRead]:
    try:
        executions = await repository.list_executions(
            db,
            project_id,
            current_user.id,
            test_case_id=test_case_id,
            status=status,
            type=type,
            environment_id=environment_id,
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    return [schemas.ExecutionRead.model_validate(e) for e in executions]


@router.get("/{project_id}/executions/{execution_id}", response_model=schemas.ExecutionRead)
async def get_execution(
    project_id: uuid.UUID,
    execution_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> schemas.ExecutionRead:
    try:
        execution = await repository.get_execution(db, project_id, execution_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.ExecutionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Execution not found.") from exc
    return schemas.ExecutionRead.model_validate(execution)
