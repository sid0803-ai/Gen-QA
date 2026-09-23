"""Data-access layer for the executions domain (project-scoped, references a
test case + an environment).

Same isolation rule as every other domain for every *router-reachable*
function: `project_id` + the requesting user's id, membership enforced via
`project_repository.require_membership`, rows always filtered by
`project_id`. The handful of functions at the bottom (used only by the
Celery task in `app.domains.executions.tasks`, never directly router-
reachable) are deliberately NOT membership-checked - the task runs as a
system process with no acting user, exactly like
`app.domains.testcases.repository.create_ai_test_case_draft()`'s own
"internal helper" carve-out.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.automation import repository as automation_repository
from app.domains.environments.models import Environment
from app.domains.executions.models import Execution, ExecutionKind, ExecutionStatus
from app.domains.projects import repository as project_repository
from app.domains.projects.models import ProjectRole
from app.domains.testcases.models import TestCase


class TestCaseNotFoundError(Exception):
    """Test case doesn't exist in this project (or the project doesn't) -> 404."""


class EnvironmentNotFoundError(Exception):
    """Environment doesn't exist in this project (or the project doesn't) -> 404."""


class ExecutionNotFoundError(Exception):
    """Execution doesn't exist in this project -> 404."""


class NoApprovedAutomationScriptError(Exception):
    """The test case has no approved automation script -> 409."""


async def _get_test_case_row(
    db: AsyncSession, project_id: uuid.UUID, test_case_id: uuid.UUID
) -> TestCase | None:
    stmt = select(TestCase).where(TestCase.id == test_case_id, TestCase.project_id == project_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _get_environment_row(
    db: AsyncSession, project_id: uuid.UUID, environment_id: uuid.UUID
) -> Environment | None:
    stmt = select(Environment).where(
        Environment.id == environment_id, Environment.project_id == project_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _get_execution_row(
    db: AsyncSession, project_id: uuid.UUID, execution_id: uuid.UUID
) -> Execution | None:
    stmt = select(Execution).where(Execution.id == execution_id, Execution.project_id == project_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _require_test_case_and_environment(
    db: AsyncSession, project_id: uuid.UUID, test_case_id: uuid.UUID, environment_id: uuid.UUID
) -> None:
    if await _get_test_case_row(db, project_id, test_case_id) is None:
        raise TestCaseNotFoundError()
    if await _get_environment_row(db, project_id, environment_id) is None:
        raise EnvironmentNotFoundError()


async def create_manual_execution(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    test_case_id: uuid.UUID,
    environment_id: uuid.UUID,
    result_status: ExecutionStatus,
    actual_result: str | None,
    comments: str | None,
) -> Execution:
    """A human recording a result that already happened: already
    `completed_at`-stamped immediately, `started_at` set to the same instant
    (there's no real "duration" to measure for a manually-observed result,
    so `duration_ms` stays None)."""
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    await _require_test_case_and_environment(db, project_id, test_case_id, environment_id)

    now = datetime.now(timezone.utc)
    execution = Execution(
        project_id=project_id,
        test_case_id=test_case_id,
        environment_id=environment_id,
        type=ExecutionKind.manual,
        status=result_status,
        triggered_by=user_id,
        started_at=now,
        completed_at=now,
        actual_result=actual_result,
        comments=comments,
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)
    return execution


async def create_pending_automated_execution(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    test_case_id: uuid.UUID,
    environment_id: uuid.UUID,
) -> Execution:
    """Creates the `status="pending"` row the caller (service.py) then
    enqueues a Celery task for. Requires the test case to already have an
    *approved* automation script - raises NoApprovedAutomationScriptError
    (-> 409) otherwise, so the API never enqueues a task doomed to fail for
    a reason it could have checked synchronously."""
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    await _require_test_case_and_environment(db, project_id, test_case_id, environment_id)

    approved_version = await automation_repository.get_approved_script_version(db, test_case_id)
    if approved_version is None:
        raise NoApprovedAutomationScriptError()

    execution = Execution(
        project_id=project_id,
        test_case_id=test_case_id,
        environment_id=environment_id,
        type=ExecutionKind.automated,
        status=ExecutionStatus.pending,
        triggered_by=user_id,
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)
    return execution


async def list_executions(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    test_case_id: uuid.UUID | None = None,
    status: ExecutionStatus | None = None,
    type: ExecutionKind | None = None,
    environment_id: uuid.UUID | None = None,
) -> list[Execution]:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)

    stmt = select(Execution).where(Execution.project_id == project_id)
    if test_case_id is not None:
        stmt = stmt.where(Execution.test_case_id == test_case_id)
    if status is not None:
        stmt = stmt.where(Execution.status == status)
    if type is not None:
        stmt = stmt.where(Execution.type == type)
    if environment_id is not None:
        stmt = stmt.where(Execution.environment_id == environment_id)
    stmt = stmt.order_by(Execution.sequence.desc())

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_execution(
    db: AsyncSession, project_id: uuid.UUID, execution_id: uuid.UUID, user_id: uuid.UUID
) -> Execution:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    execution = await _get_execution_row(db, project_id, execution_id)
    if execution is None:
        raise ExecutionNotFoundError()
    return execution


# --- Internal, non-membership-checked helpers - used only by the Celery
# task (app.domains.executions.tasks), which runs as a system process with
# no acting user. Never directly router-reachable. -------------------------


async def get_execution_for_run(db: AsyncSession, execution_id: uuid.UUID) -> Execution | None:
    result = await db.execute(select(Execution).where(Execution.id == execution_id))
    return result.scalar_one_or_none()


async def get_environment_row(db: AsyncSession, environment_id: uuid.UUID) -> Environment | None:
    result = await db.execute(select(Environment).where(Environment.id == environment_id))
    return result.scalar_one_or_none()


async def mark_running(db: AsyncSession, execution_id: uuid.UUID) -> None:
    execution = await get_execution_for_run(db, execution_id)
    if execution is None:
        return
    execution.status = ExecutionStatus.running
    execution.started_at = datetime.now(timezone.utc)
    await db.commit()


async def record_result(
    db: AsyncSession,
    execution_id: uuid.UUID,
    *,
    result_status: ExecutionStatus,
    logs: str | None,
    error_message: str | None,
    duration_ms: int | None,
) -> None:
    execution = await get_execution_for_run(db, execution_id)
    if execution is None:
        return
    execution.status = result_status
    execution.logs = logs
    execution.error_message = error_message
    execution.duration_ms = duration_ms
    execution.completed_at = datetime.now(timezone.utc)
    await db.commit()
