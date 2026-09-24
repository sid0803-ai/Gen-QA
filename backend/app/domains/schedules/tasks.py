"""The scheduling engine's periodic tick: registered on Celery Beat (see
`app.worker`) to run every 60 seconds. For every `ScheduledJob` that's
currently enabled and due (`next_run_at <= now()`), it re-validates the
target test case still has an approved automation script and, if so,
enqueues the SAME `run_automated_execution` Celery task
(`app.domains.executions.tasks`) that a manual "run this now" automated
execution uses - reusing `app.domains.executions.service.create_automated_
execution()` end to end (Execution-row creation *and* the `.delay()` call)
rather than duplicating either.

Deliberately mirrors `app.domains.executions.tasks`'s own sync-entrypoint-
wrapping-a-dedicated-async-engine pattern (see that module's docstring for
the full rationale): Celery Beat/worker tasks are sync by default in this
codebase, and running a brand-new asyncio event loop per invocation inside a
dedicated thread sidesteps asyncpg's "a connection is bound to whichever
event loop was running when it was first checked out" constraint uniformly,
whether this runs under a real Celery worker process or under
`task_always_eager` test mode (where `.delay()`/an eager Beat call runs
in-process, possibly from inside an already-running event loop).

NOTE on `Execution.triggered_by`: that column is a strict FK to `users.id`
(not a free-text/enum "trigger source" field - see
`app.domains.executions.models.Execution`), so a schedule-fired execution
can't literally be attributed to a string like `"schedule"`. It's attributed
to the `ScheduledJob.created_by` user instead - the person who set the
schedule up - which is the closest existing concept to "who is responsible
for this run" that the current schema supports.
"""
import asyncio
import concurrent.futures
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.domains.executions import repository as executions_repository
from app.domains.executions import service as executions_service
from app.domains.projects import repository as project_repository
from app.domains.schedules import repository as schedules_repository

# Exceptions that mean "this job no longer qualifies to fire right now" -
# caught around create_automated_execution() below so a due job that's since
# become un-automatable (script un-approved, test case/environment deleted,
# or the schedule's creator lost project membership) is skipped silently
# this tick rather than erroring or disabling the job. The next tick
# re-checks from scratch.
_SKIP_EXCEPTIONS = (
    executions_repository.NoApprovedAutomationScriptError,
    executions_repository.TestCaseNotFoundError,
    executions_repository.EnvironmentNotFoundError,
    project_repository.NotAMemberError,
    project_repository.InsufficientRoleError,
)


def run_due_scheduled_jobs_sync() -> None:
    """Sync entry point - the Celery Beat task body (`app.worker`) calls
    this directly. See this module's docstring for why the real work
    happens inside a dedicated thread + fresh event loop."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(asyncio.run, _run_due_scheduled_jobs()).result()


async def _run_due_scheduled_jobs() -> None:
    """Owns a dedicated, short-lived engine for the whole lifetime of this
    one tick, exactly like `app.domains.executions.tasks._run()` does for a
    single execution - see that function's docstring for why a shared,
    long-lived engine can't safely be reused across many different
    `asyncio.run()` event loops."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        now = datetime.now(timezone.utc)
        async with session_factory() as db:
            due = await schedules_repository.get_due_schedules(db, now=now)
            # Snapshot the plain fields we need before this session closes -
            # each job below gets processed in its own short-lived session.
            due_snapshot = [
                (job.id, job.project_id, job.test_case_id, job.environment_id, job.created_by)
                for job in due
            ]

        for schedule_id, project_id, test_case_id, environment_id, created_by in due_snapshot:
            fired = False
            async with session_factory() as db:
                try:
                    await executions_service.create_automated_execution(
                        db,
                        project_id,
                        created_by,
                        test_case_id=test_case_id,
                        environment_id=environment_id,
                    )
                    fired = True
                except _SKIP_EXCEPTIONS:
                    fired = False

            if fired:
                async with session_factory() as db:
                    await schedules_repository.mark_ticked(
                        db, schedule_id, now=datetime.now(timezone.utc)
                    )
    finally:
        await engine.dispose()
