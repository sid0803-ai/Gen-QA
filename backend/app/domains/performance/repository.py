"""Data-access layer for the performance domain (project-scoped).

Same isolation rule as every other domain for every router-reachable
function: `project_id` + the requesting user's id, membership enforced via
`project_repository.require_membership`, rows always filtered by
`project_id` (runs additionally filtered via a join back to their parent
`PerformanceTest`'s `project_id`, so a run id from another project can never
be reached even if guessed). The handful of functions at the bottom (used
only by the Celery task in `app.domains.performance.tasks`, never directly
router-reachable) are deliberately NOT membership-checked - the task runs as
a system process with no acting user, same carve-out as
`app.domains.executions.repository`'s own internal helpers.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.api_performer.models import SavedApiRequest
from app.domains.performance.models import PerformanceTest, PerformanceTestRun, PerformanceTestRunStatus
from app.domains.projects import repository as project_repository
from app.domains.projects.models import ProjectRole


class SavedApiRequestNotFoundError(Exception):
    """The given saved_request_id doesn't exist in this project -> 404."""


class PerformanceTestNotFoundError(Exception):
    """Performance test doesn't exist in this project (or the project
    doesn't) -> 404."""


class PerformanceTestRunNotFoundError(Exception):
    """Run doesn't exist for this performance test -> 404."""


async def _get_saved_request_row(
    db: AsyncSession, project_id: uuid.UUID, saved_request_id: uuid.UUID
) -> SavedApiRequest | None:
    stmt = select(SavedApiRequest).where(
        SavedApiRequest.id == saved_request_id, SavedApiRequest.project_id == project_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _get_test_row(
    db: AsyncSession, project_id: uuid.UUID, performance_test_id: uuid.UUID
) -> PerformanceTest | None:
    stmt = select(PerformanceTest).where(
        PerformanceTest.id == performance_test_id, PerformanceTest.project_id == project_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# --- PerformanceTest ---------------------------------------------------


async def create_test(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    saved_request_id: uuid.UUID,
    name: str,
    vus: int,
    duration_seconds: int,
) -> PerformanceTest:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    saved_request = await _get_saved_request_row(db, project_id, saved_request_id)
    if saved_request is None:
        raise SavedApiRequestNotFoundError()

    test = PerformanceTest(
        project_id=project_id,
        saved_request_id=saved_request_id,
        name=name,
        vus=vus,
        duration_seconds=duration_seconds,
        created_by=user_id,
    )
    db.add(test)
    await db.commit()
    await db.refresh(test)
    return test


async def list_tests(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID
) -> list[PerformanceTest]:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    stmt = (
        select(PerformanceTest)
        .where(PerformanceTest.project_id == project_id)
        .order_by(PerformanceTest.sequence.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_test(
    db: AsyncSession, project_id: uuid.UUID, performance_test_id: uuid.UUID, user_id: uuid.UUID
) -> PerformanceTest:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    test = await _get_test_row(db, project_id, performance_test_id)
    if test is None:
        raise PerformanceTestNotFoundError()
    return test


async def update_test(
    db: AsyncSession,
    project_id: uuid.UUID,
    performance_test_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    name: str | None,
    vus: int | None,
    duration_seconds: int | None,
) -> PerformanceTest:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    test = await _get_test_row(db, project_id, performance_test_id)
    if test is None:
        raise PerformanceTestNotFoundError()

    if name is not None:
        test.name = name
    if vus is not None:
        test.vus = vus
    if duration_seconds is not None:
        test.duration_seconds = duration_seconds

    await db.commit()
    await db.refresh(test)
    return test


async def delete_test(
    db: AsyncSession, project_id: uuid.UUID, performance_test_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Deletes the performance test - cascades (DB-level ON DELETE CASCADE)
    to its runs."""
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.admin)
    test = await _get_test_row(db, project_id, performance_test_id)
    if test is None:
        raise PerformanceTestNotFoundError()

    await db.delete(test)
    await db.commit()


# --- PerformanceTestRun -------------------------------------------------


async def create_run(
    db: AsyncSession,
    project_id: uuid.UUID,
    performance_test_id: uuid.UUID,
    user_id: uuid.UUID,
) -> PerformanceTestRun:
    """Inserts a `status="queued"` row snapshotting the test's current
    `vus`/`duration_seconds`, and returns it. The actual k6 execution happens
    asynchronously via Celery - the caller (service.py) enqueues the task
    right after this commits, exactly like `executions`/`schedules` do."""
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    test = await _get_test_row(db, project_id, performance_test_id)
    if test is None:
        raise PerformanceTestNotFoundError()

    run = PerformanceTestRun(
        performance_test_id=performance_test_id,
        status=PerformanceTestRunStatus.queued,
        vus=test.vus,
        duration_seconds=test.duration_seconds,
        created_by=user_id,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def _get_run_row(
    db: AsyncSession, project_id: uuid.UUID, performance_test_id: uuid.UUID, run_id: uuid.UUID
) -> PerformanceTestRun | None:
    stmt = (
        select(PerformanceTestRun)
        .join(PerformanceTest, PerformanceTestRun.performance_test_id == PerformanceTest.id)
        .where(
            PerformanceTestRun.id == run_id,
            PerformanceTestRun.performance_test_id == performance_test_id,
            PerformanceTest.project_id == project_id,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_runs(
    db: AsyncSession, project_id: uuid.UUID, performance_test_id: uuid.UUID, user_id: uuid.UUID
) -> list[PerformanceTestRun]:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    test = await _get_test_row(db, project_id, performance_test_id)
    if test is None:
        raise PerformanceTestNotFoundError()

    stmt = (
        select(PerformanceTestRun)
        .where(PerformanceTestRun.performance_test_id == performance_test_id)
        .order_by(PerformanceTestRun.sequence.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_run(
    db: AsyncSession,
    project_id: uuid.UUID,
    performance_test_id: uuid.UUID,
    run_id: uuid.UUID,
    user_id: uuid.UUID,
) -> PerformanceTestRun:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    run = await _get_run_row(db, project_id, performance_test_id, run_id)
    if run is None:
        raise PerformanceTestRunNotFoundError()
    return run


# --- Internal, non-membership-checked helpers - used only by the Celery
# task (app.domains.performance.tasks), which runs as a system process with
# no acting user. Never directly router-reachable. -------------------------


async def get_run_for_task(db: AsyncSession, run_id: uuid.UUID) -> PerformanceTestRun | None:
    result = await db.execute(select(PerformanceTestRun).where(PerformanceTestRun.id == run_id))
    return result.scalar_one_or_none()


async def get_test_for_task(db: AsyncSession, performance_test_id: uuid.UUID) -> PerformanceTest | None:
    result = await db.execute(select(PerformanceTest).where(PerformanceTest.id == performance_test_id))
    return result.scalar_one_or_none()


async def get_saved_request_for_task(
    db: AsyncSession, saved_request_id: uuid.UUID
) -> SavedApiRequest | None:
    result = await db.execute(select(SavedApiRequest).where(SavedApiRequest.id == saved_request_id))
    return result.scalar_one_or_none()


async def mark_running(db: AsyncSession, run_id: uuid.UUID) -> None:
    run = await get_run_for_task(db, run_id)
    if run is None:
        return
    run.status = PerformanceTestRunStatus.running
    run.started_at = datetime.now(timezone.utc)
    await db.commit()


async def record_success(
    db: AsyncSession,
    run_id: uuid.UUID,
    *,
    request_count: int | None,
    failed_count: int | None,
    error_rate: float | None,
    avg_duration_ms: float | None,
    p95_duration_ms: float | None,
    min_duration_ms: float | None,
    max_duration_ms: float | None,
    requests_per_second: float | None,
    raw_summary: dict | None,
) -> None:
    run = await get_run_for_task(db, run_id)
    if run is None:
        return
    run.status = PerformanceTestRunStatus.completed
    run.request_count = request_count
    run.failed_count = failed_count
    run.error_rate = error_rate
    run.avg_duration_ms = avg_duration_ms
    run.p95_duration_ms = p95_duration_ms
    run.min_duration_ms = min_duration_ms
    run.max_duration_ms = max_duration_ms
    run.requests_per_second = requests_per_second
    run.raw_summary = raw_summary
    run.completed_at = datetime.now(timezone.utc)
    await db.commit()


async def record_failure(db: AsyncSession, run_id: uuid.UUID, *, error_message: str) -> None:
    run = await get_run_for_task(db, run_id)
    if run is None:
        return
    run.status = PerformanceTestRunStatus.failed
    run.error_message = error_message
    run.completed_at = datetime.now(timezone.utc)
    await db.commit()
