"""Data-access layer for the schedules domain (project-scoped recurring
automated-execution jobs).

Same isolation rule as every other domain for every *router-reachable*
function: `project_id` + the requesting user's id, membership enforced via
`project_repository.require_membership`, rows always filtered by
`project_id`. The two functions at the bottom (`get_due_schedules`,
`mark_ticked`) are used only by the Celery Beat periodic task
(`app.domains.schedules.tasks`), which runs as a system process with no
acting user - deliberately NOT membership-checked, the same "internal
helper" carve-out as `app.domains.executions.repository`'s own bottom
section.

`next_run_at` is computed with `croniter` any time a job is created,
enabled, or its `cron_expression` changes (see `compute_next_run_at()`),
always relative to "now" at the moment of that change - never re-derived
lazily on read.
"""
import uuid
from datetime import datetime, timezone

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.automation import repository as automation_repository
from app.domains.environments.models import Environment
from app.domains.projects import repository as project_repository
from app.domains.projects.models import ProjectRole
from app.domains.schedules.models import ScheduledJob
from app.domains.testcases.models import TestCase


class TestCaseNotFoundError(Exception):
    """Test case doesn't exist in this project (or the project doesn't) -> 404."""


class EnvironmentNotFoundError(Exception):
    """Environment doesn't exist in this project (or the project doesn't) -> 404."""


class ScheduledJobNotFoundError(Exception):
    """Scheduled job doesn't exist in this project -> 404."""


class InvalidCronExpressionError(Exception):
    """cron_expression isn't a valid standard 5-field cron expression -> 400."""


class NoApprovedAutomationScriptError(Exception):
    """The test case has no approved automation script -> 400."""


def compute_next_run_at(cron_expression: str, base_time: datetime) -> datetime:
    """The next fire time strictly after `base_time` - a schedule that is
    created/enabled/re-cronned "now" always fires at its next *future*
    occurrence, never immediately (croniter's own default behavior)."""
    return croniter(cron_expression, base_time).get_next(datetime)


def validate_cron_expression(cron_expression: str) -> None:
    if not croniter.is_valid(cron_expression):
        raise InvalidCronExpressionError()


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


async def _get_schedule_row(
    db: AsyncSession, project_id: uuid.UUID, schedule_id: uuid.UUID
) -> ScheduledJob | None:
    stmt = select(ScheduledJob).where(
        ScheduledJob.id == schedule_id, ScheduledJob.project_id == project_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _require_test_case_and_environment(
    db: AsyncSession, project_id: uuid.UUID, test_case_id: uuid.UUID, environment_id: uuid.UUID
) -> None:
    if await _get_test_case_row(db, project_id, test_case_id) is None:
        raise TestCaseNotFoundError()
    if await _get_environment_row(db, project_id, environment_id) is None:
        raise EnvironmentNotFoundError()


async def _require_approved_automation_script(db: AsyncSession, test_case_id: uuid.UUID) -> None:
    approved = await automation_repository.get_approved_script_version(db, test_case_id)
    if approved is None:
        raise NoApprovedAutomationScriptError()


async def create_schedule(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    name: str,
    test_case_id: uuid.UUID,
    environment_id: uuid.UUID,
    cron_expression: str,
    enabled: bool,
) -> ScheduledJob:
    """A test case can only be scheduled while it currently has an
    *approved* automation script - checked once, here, at creation time.
    Deliberately NOT re-checked on every future edit/read: a schedule stays
    on the books even if the script is later un-approved, and the periodic
    task re-validates this itself on every tick (see
    `app.domains.schedules.tasks`), silently skipping a tick rather than
    erroring when it no longer qualifies."""
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    await _require_test_case_and_environment(db, project_id, test_case_id, environment_id)
    validate_cron_expression(cron_expression)
    await _require_approved_automation_script(db, test_case_id)

    now = datetime.now(timezone.utc)
    schedule = ScheduledJob(
        project_id=project_id,
        test_case_id=test_case_id,
        environment_id=environment_id,
        name=name,
        cron_expression=cron_expression,
        enabled=enabled,
        next_run_at=compute_next_run_at(cron_expression, now) if enabled else None,
        created_by=user_id,
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return schedule


async def list_schedules(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID
) -> list[ScheduledJob]:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    stmt = (
        select(ScheduledJob)
        .where(ScheduledJob.project_id == project_id)
        .order_by(ScheduledJob.sequence.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_schedule(
    db: AsyncSession, project_id: uuid.UUID, schedule_id: uuid.UUID, user_id: uuid.UUID
) -> ScheduledJob:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    schedule = await _get_schedule_row(db, project_id, schedule_id)
    if schedule is None:
        raise ScheduledJobNotFoundError()
    return schedule


async def update_schedule(
    db: AsyncSession,
    project_id: uuid.UUID,
    schedule_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    name: str | None,
    cron_expression: str | None,
    enabled: bool | None,
    environment_id: uuid.UUID | None,
) -> ScheduledJob:
    """Recomputes `next_run_at` whenever `cron_expression` changes, or
    whenever `enabled` flips False->True (relative to "now" at the moment of
    this update); sets `next_run_at` to null whenever `enabled` flips to
    False. A no-op `enabled=True` on an already-enabled job, with no
    `cron_expression` change, leaves `next_run_at` untouched (nothing about
    the schedule actually changed)."""
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    schedule = await _get_schedule_row(db, project_id, schedule_id)
    if schedule is None:
        raise ScheduledJobNotFoundError()

    if environment_id is not None:
        if await _get_environment_row(db, project_id, environment_id) is None:
            raise EnvironmentNotFoundError()
        schedule.environment_id = environment_id

    recompute = False
    if cron_expression is not None:
        validate_cron_expression(cron_expression)
        schedule.cron_expression = cron_expression
        recompute = True

    if name is not None:
        schedule.name = name

    if enabled is not None:
        if enabled and not schedule.enabled:
            recompute = True
        elif not enabled:
            schedule.next_run_at = None
        schedule.enabled = enabled

    if recompute and schedule.enabled:
        schedule.next_run_at = compute_next_run_at(schedule.cron_expression, datetime.now(timezone.utc))

    await db.commit()
    await db.refresh(schedule)
    return schedule


async def delete_schedule(
    db: AsyncSession, project_id: uuid.UUID, schedule_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.admin)
    schedule = await _get_schedule_row(db, project_id, schedule_id)
    if schedule is None:
        raise ScheduledJobNotFoundError()
    await db.delete(schedule)
    await db.commit()


# --- Internal, non-membership-checked helpers - used only by the Celery
# Beat periodic task (app.domains.schedules.tasks), which runs as a system
# process with no acting user. Never directly router-reachable. -------------


async def get_due_schedules(db: AsyncSession, *, now: datetime) -> list[ScheduledJob]:
    """Every enabled job whose `next_run_at` has arrived - the periodic
    task's hot query path (see the `(project_id, enabled, next_run_at)`
    index on `ScheduledJob`)."""
    stmt = select(ScheduledJob).where(
        ScheduledJob.enabled.is_(True), ScheduledJob.next_run_at <= now
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def mark_ticked(db: AsyncSession, schedule_id: uuid.UUID, *, now: datetime) -> None:
    """Called after a due job has actually fired (enqueued a Celery
    execution) this tick: stamps `last_run_at` and recomputes `next_run_at`
    from the job's own `cron_expression` relative to `now`. Deliberately
    re-reads the row by id (rather than mutating a row handed in from an
    earlier, possibly different, session) - same "always re-query, never
    trust a stale in-memory object across sessions" discipline as
    `app.domains.executions.repository`'s own internal helpers."""
    result = await db.execute(select(ScheduledJob).where(ScheduledJob.id == schedule_id))
    schedule = result.scalar_one_or_none()
    if schedule is None:
        return
    schedule.last_run_at = now
    schedule.next_run_at = compute_next_run_at(schedule.cron_expression, now)
    await db.commit()
