"""Data-access layer for the reporting domain (Sprint 6 - new, read-only).

Every function here is a pure aggregation read over rows that already exist
in the requirements/testcases/automation/executions tables - this domain
intentionally adds no tables of its own (see backend/README.md's Sprint 6
notes for why: a materialized rollup wasn't justified by anything measured
in this sprint).

Same isolation rule as every other domain: every function takes
`project_id` + the requesting user's id and enforces membership via
`project_repository.require_membership` before touching any row.

Central concept used by three of the four endpoints (dashboard,
reports/breakdown, requirements/{id}/coverage): a test case's *latest
execution* is the one with the highest `Execution.sequence` (a monotonic
Postgres IDENTITY column - never `created_at`, which can collide between
two executions recorded in quick succession; see `Execution.sequence`'s own
docstring and every other domain's `sequence` column for the established
reason this codebase always orders "latest X" this way). `sequence` is
globally unique (a `BigInteger Identity(always=True)` with a `UNIQUE`
constraint - see `executions.models.Execution.sequence`), so once we know
the max `sequence` value *within* a test case's own executions, joining
back to `Execution` on `sequence == max_seq` alone (no `test_case_id` in
that join condition) still returns exactly the one right row.
"""
import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.domains.automation.models import AutomationScript, AutomationScriptStatus
from app.domains.executions.models import Execution, ExecutionStatus
from app.domains.projects import repository as project_repository
from app.domains.projects.models import ProjectRole
from app.domains.requirements import repository as requirements_repository
from app.domains.requirements.models import Requirement
from app.domains.requirements.repository import RequirementNotFoundError  # noqa: F401 (re-exported)
from app.domains.schedules.models import ScheduledJob
from app.domains.testcases.models import ExecutionType, TestCase

# Every non-transient Execution.status value - "pending"/"running" are the
# only two that are *not* terminal (an execution still in flight has no
# meaningful pass/fail signal yet).
TERMINAL_STATUSES = (
    ExecutionStatus.passed,
    ExecutionStatus.failed,
    ExecutionStatus.blocked,
    ExecutionStatus.skipped,
    ExecutionStatus.error,
)
IN_PROGRESS_STATUSES = (ExecutionStatus.pending, ExecutionStatus.running)


def _latest_execution_status_stmt(project_id: uuid.UUID, requirement_id: uuid.UUID | None = None) -> Select:
    """SELECT TestCase, <latest execution's status or NULL> for every test
    case in this project (optionally narrowed to one requirement) - one row
    per test case, always, even for a test case with zero executions
    (LEFT JOIN, so its status comes back NULL)."""
    latest_seq_subq = (
        select(
            Execution.test_case_id.label("test_case_id"),
            func.max(Execution.sequence).label("max_seq"),
        )
        .where(Execution.project_id == project_id)
        .group_by(Execution.test_case_id)
        .subquery()
    )
    stmt = (
        select(TestCase, Execution.status)
        .select_from(TestCase)
        .outerjoin(latest_seq_subq, latest_seq_subq.c.test_case_id == TestCase.id)
        .outerjoin(Execution, Execution.sequence == latest_seq_subq.c.max_seq)
        .where(TestCase.project_id == project_id)
    )
    if requirement_id is not None:
        stmt = stmt.where(TestCase.requirement_id == requirement_id)
    return stmt


def _empty_status_breakdown() -> dict[str, int]:
    return {"passed": 0, "failed": 0, "blocked": 0, "skipped": 0, "error": 0, "none": 0}


def _bucket_latest_statuses(rows: list[tuple[TestCase, ExecutionStatus | None]]) -> dict[str, int]:
    """The response shape only has room for the five terminal statuses plus
    "none" - there is deliberately no "pending"/"running" slot (an automated
    execution normally only sits in one of those two states very briefly
    before this codebase's Celery task resolves it to a terminal status).
    A test case whose *latest* execution happens to still be in flight has
    no completed result to report any more than a test case with zero
    executions does, so it is folded into "none" too - the only way to keep
    the "bucket counts must sum to test_cases_count" invariant true given
    this exact 6-key shape. See this module's own README/report note for
    the full rationale."""
    breakdown = _empty_status_breakdown()
    for _test_case, status in rows:
        if status is None or status in IN_PROGRESS_STATUSES:
            breakdown["none"] += 1
        else:
            breakdown[status.value] += 1
    return breakdown


def _pass_rate_pct(breakdown: dict[str, int]) -> float | None:
    """Among test cases whose latest execution is TERMINAL (i.e. excluding
    "none" and excluding pending/running, which never appear in a
    `latest_status_breakdown` built from `_bucket_latest_statuses` in the
    first place - only "none" plus the five terminal keys ever appear
    there)."""
    denominator = breakdown["passed"] + breakdown["failed"] + breakdown["blocked"] + breakdown["skipped"] + breakdown["error"]
    if denominator == 0:
        return None
    return round(breakdown["passed"] / denominator * 100, 2)


async def get_dashboard(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> dict:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)

    requirements_count = (
        await db.execute(
            select(func.count()).select_from(Requirement).where(Requirement.project_id == project_id)
        )
    ).scalar_one()

    latest_rows = (await db.execute(_latest_execution_status_stmt(project_id))).all()
    test_cases_count = len(latest_rows)
    breakdown = _bucket_latest_statuses(latest_rows)

    automation_candidate_count = (
        await db.execute(
            select(func.count(func.distinct(TestCase.id)))
            .select_from(TestCase)
            .join(AutomationScript, AutomationScript.test_case_id == TestCase.id)
            .where(TestCase.project_id == project_id)
            .where(AutomationScript.status == AutomationScriptStatus.approved)
        )
    ).scalar_one()

    automation_coverage_pct = (
        round(automation_candidate_count / test_cases_count * 100, 2) if test_cases_count else 0.0
    )

    executions_total = (
        await db.execute(
            select(func.count()).select_from(Execution).where(Execution.project_id == project_id)
        )
    ).scalar_one()

    in_progress_count = (
        await db.execute(
            select(func.count())
            .select_from(Execution)
            .where(Execution.project_id == project_id)
            .where(Execution.status.in_(IN_PROGRESS_STATUSES))
        )
    ).scalar_one()

    open_failures_count = breakdown["failed"] + breakdown["error"]

    scheduled_jobs_count = (
        await db.execute(
            select(func.count())
            .select_from(ScheduledJob)
            .where(ScheduledJob.project_id == project_id)
            .where(ScheduledJob.enabled.is_(True))
        )
    ).scalar_one()

    return {
        "requirements_count": requirements_count,
        "test_cases_count": test_cases_count,
        "automation_candidate_count": automation_candidate_count,
        "automation_coverage_pct": automation_coverage_pct,
        "executions_total": executions_total,
        "in_progress_count": in_progress_count,
        "latest_status_breakdown": breakdown,
        "pass_rate_pct": _pass_rate_pct(breakdown),
        "open_failures_count": open_failures_count,
        "scheduled_jobs_count": scheduled_jobs_count,
    }


async def get_trend(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID, *, days: int) -> list[dict]:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)

    today = date.today()
    start_day = today - timedelta(days=days - 1)

    day_col = func.date(Execution.completed_at)
    stmt = (
        select(day_col.label("day"), Execution.status, func.count().label("cnt"))
        .where(Execution.project_id == project_id)
        .where(Execution.status.in_(TERMINAL_STATUSES))
        .where(Execution.completed_at.isnot(None))
        .where(day_col >= start_day)
        .where(day_col <= today)
        .group_by(day_col, Execution.status)
    )
    rows = (await db.execute(stmt)).all()

    per_day: dict[date, dict[str, int]] = {}
    cursor = start_day
    while cursor <= today:
        per_day[cursor] = {"passed": 0, "failed": 0, "blocked": 0, "skipped": 0, "error": 0}
        cursor += timedelta(days=1)

    for day, status, cnt in rows:
        # `func.date(...)` on an asyncpg/Postgres DATE column round-trips as
        # a `datetime.date` already, but normalize defensively in case a
        # driver ever hands back a string here instead.
        day_key = day if isinstance(day, date) else date.fromisoformat(str(day))
        per_day[day_key][status.value] += cnt

    result = []
    for day in sorted(per_day):
        counts = per_day[day]
        total = sum(counts.values())
        result.append({"date": day.isoformat(), **counts, "total": total})
    return result


_BREAKDOWN_DIMENSIONS = {
    "by_testing_level": ("testing_level", TestCase.testing_level),
    "by_category": ("category", TestCase.category),
    "by_priority": ("priority", TestCase.priority),
}


async def get_breakdown(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> dict:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)

    latest_rows = (await db.execute(_latest_execution_status_stmt(project_id))).all()

    result: dict[str, list[dict]] = {}
    for key, (field_name, _column) in _BREAKDOWN_DIMENSIONS.items():
        buckets: dict[str, dict[str, int]] = {}
        for test_case, status in latest_rows:
            dimension_value = getattr(test_case, field_name).value
            bucket = buckets.setdefault(
                dimension_value,
                {"total": 0, "passed": 0, "failed": 0, "blocked": 0, "skipped": 0, "error": 0, "no_runs": 0},
            )
            bucket["total"] += 1
            # Same "no completed result yet" folding as
            # `_bucket_latest_statuses` above - "no_runs" absorbs both zero
            # executions and an in-flight (pending/running) latest one,
            # since this bucket shape has no pending/running slot either.
            if status is None or status in IN_PROGRESS_STATUSES:
                bucket["no_runs"] += 1
            else:
                bucket[status.value] += 1

        result[key] = [
            {field_name: dimension_value, **counts}
            for dimension_value, counts in sorted(buckets.items())
        ]
    return result


async def get_requirement_coverage(
    db: AsyncSession, project_id: uuid.UUID, requirement_id: uuid.UUID, user_id: uuid.UUID
) -> dict:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)

    # Raises RequirementNotFoundError (-> 404) if the requirement doesn't
    # belong to this project - same existence-check pattern every other
    # domain uses for a nested resource lookup.
    await requirements_repository.get_requirement(db, project_id, requirement_id, user_id)

    latest_rows = (
        await db.execute(_latest_execution_status_stmt(project_id, requirement_id=requirement_id))
    ).all()
    test_case_count = len(latest_rows)

    automated_count = sum(1 for tc, _ in latest_rows if tc.execution_type == ExecutionType.automation)
    manual_count = sum(1 for tc, _ in latest_rows if tc.execution_type == ExecutionType.manual)
    hybrid_count = sum(1 for tc, _ in latest_rows if tc.execution_type == ExecutionType.hybrid)

    automation_script_approved_count = (
        await db.execute(
            select(func.count(func.distinct(TestCase.id)))
            .select_from(TestCase)
            .join(AutomationScript, AutomationScript.test_case_id == TestCase.id)
            .where(TestCase.project_id == project_id)
            .where(TestCase.requirement_id == requirement_id)
            .where(AutomationScript.status == AutomationScriptStatus.approved)
        )
    ).scalar_one()

    breakdown = _bucket_latest_statuses(latest_rows)

    return {
        "requirement_id": str(requirement_id),
        "test_case_count": test_case_count,
        "automated_count": automated_count,
        "manual_count": manual_count,
        "hybrid_count": hybrid_count,
        "automation_script_approved_count": automation_script_approved_count,
        "latest_status_breakdown": breakdown,
        "pass_rate_pct": _pass_rate_pct(breakdown),
    }
