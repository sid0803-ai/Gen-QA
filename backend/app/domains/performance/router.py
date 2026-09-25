"""Routes: /api/v1/projects/{project_id}/performance-tests/* (performance
domain, "Performance Testing" - k6-backed load testing built on top of a
saved api_performer request; see `app.domains.performance.models`'s module
docstring for the full scope-cut list).

Project-scoped: `viewer` reads, `member` creates/edits/triggers runs,
`admin` deletes - same role convention as every other domain (`executions`/
`api_performer` in particular).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, require_project_role
from app.domains.identity.models import User
from app.domains.performance import repository, schemas
from app.domains.projects import repository as project_repository
from app.domains.projects.models import ProjectMember, ProjectRole

router = APIRouter(prefix="/projects", tags=["performance"])


# --- PerformanceTest -----------------------------------------------------


@router.post(
    "/{project_id}/performance-tests",
    response_model=schemas.PerformanceTestRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_performance_test(
    project_id: uuid.UUID,
    payload: schemas.PerformanceTestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.PerformanceTestRead:
    try:
        test = await repository.create_test(
            db,
            project_id,
            current_user.id,
            saved_request_id=payload.saved_request_id,
            name=payload.name,
            vus=payload.vus,
            duration_seconds=payload.duration_seconds,
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Member role required on this project.") from exc
    except repository.SavedApiRequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Saved API request not found.") from exc
    return schemas.PerformanceTestRead.model_validate(test)


@router.get("/{project_id}/performance-tests", response_model=list[schemas.PerformanceTestRead])
async def list_performance_tests(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[schemas.PerformanceTestRead]:
    try:
        tests = await repository.list_tests(db, project_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    return [schemas.PerformanceTestRead.model_validate(t) for t in tests]


@router.get(
    "/{project_id}/performance-tests/{performance_test_id}", response_model=schemas.PerformanceTestRead
)
async def get_performance_test(
    project_id: uuid.UUID,
    performance_test_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> schemas.PerformanceTestRead:
    try:
        test = await repository.get_test(db, project_id, performance_test_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.PerformanceTestNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Performance test not found.") from exc
    return schemas.PerformanceTestRead.model_validate(test)


@router.patch(
    "/{project_id}/performance-tests/{performance_test_id}", response_model=schemas.PerformanceTestRead
)
async def update_performance_test(
    project_id: uuid.UUID,
    performance_test_id: uuid.UUID,
    payload: schemas.PerformanceTestUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.PerformanceTestRead:
    try:
        test = await repository.update_test(
            db,
            project_id,
            performance_test_id,
            current_user.id,
            name=payload.name,
            vus=payload.vus,
            duration_seconds=payload.duration_seconds,
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Member role required on this project.") from exc
    except repository.PerformanceTestNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Performance test not found.") from exc
    return schemas.PerformanceTestRead.model_validate(test)


@router.delete(
    "/{project_id}/performance-tests/{performance_test_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_performance_test(
    project_id: uuid.UUID,
    performance_test_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await repository.delete_test(db, project_id, performance_test_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Admin role required on this project.") from exc
    except repository.PerformanceTestNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Performance test not found.") from exc


# --- PerformanceTestRun --------------------------------------------------


@router.post(
    "/{project_id}/performance-tests/{performance_test_id}/runs",
    response_model=schemas.PerformanceTestRunRead,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_run(
    project_id: uuid.UUID,
    performance_test_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.PerformanceTestRunRead:
    """Creates a `status="queued"` run row and hands it to Celery
    (`.delay()`) - returns immediately with the queued run; the k6 execution
    itself happens asynchronously (see `app.domains.performance.tasks`),
    same "create + enqueue, return the pending/queued row" pattern as
    `executions`' automated-execution trigger endpoint (also 201, since a
    new resource - the run row - was created by this call)."""
    try:
        run = await repository.create_run(db, project_id, performance_test_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Member role required on this project.") from exc
    except repository.PerformanceTestNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Performance test not found.") from exc

    from app.worker import run_performance_test

    run_performance_test.delay(str(run.id))
    return schemas.PerformanceTestRunRead.model_validate(run)


@router.get(
    "/{project_id}/performance-tests/{performance_test_id}/runs",
    response_model=list[schemas.PerformanceTestRunSummary],
)
async def list_runs(
    project_id: uuid.UUID,
    performance_test_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[schemas.PerformanceTestRunSummary]:
    """Newest first (via `sequence`, matching this codebase's ordering
    convention) - lighter `PerformanceTestRunSummary` shape, without
    `raw_summary`."""
    try:
        runs = await repository.list_runs(db, project_id, performance_test_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.PerformanceTestNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Performance test not found.") from exc
    return [schemas.PerformanceTestRunSummary.model_validate(r) for r in runs]


@router.get(
    "/{project_id}/performance-tests/{performance_test_id}/runs/{run_id}",
    response_model=schemas.PerformanceTestRunRead,
)
async def get_run(
    project_id: uuid.UUID,
    performance_test_id: uuid.UUID,
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> schemas.PerformanceTestRunRead:
    """Full run detail, including `raw_summary`."""
    try:
        run = await repository.get_run(db, project_id, performance_test_id, run_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.PerformanceTestRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Performance test run not found.") from exc
    return schemas.PerformanceTestRunRead.model_validate(run)
