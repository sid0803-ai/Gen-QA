"""Celery application instance for Gen-QA's execution engine (Sprint 5).

Dev/deployment usage - start a real worker process, pointed at a real Redis
(`REDIS_URL` in `backend/.env`, already wired in `app.core.config.Settings`
since Sprint 1 but unused until now):

    cd backend
    celery -A app.worker worker --loglevel=info

Tests never need a real Redis: `tests/conftest.py` sets
`celery_app.conf.task_always_eager = True` for the whole test session, which
runs `run_automated_execution` synchronously, in-process, the moment
`.delay()` is called - still the real task function/logic, just without an
actual broker round-trip (this is Celery's own documented test-mode
mechanism, not a shortcut around correctness). See `backend/README.md` for
the from-scratch real-Redis smoke test (via the pip-installable `redislite`)
that separately proved the actual broker wiring works end-to-end, once,
outside of eager mode.

The task function itself is defined in `app.domains.executions.tasks`
(imported lazily inside the task body below) - see that module for the
actual execution engine (writing the script to a temp file inside
`backend/automation_runner/`, running `npx playwright test ... --reporter
=json` as a real subprocess, parsing the result). Importing it lazily here
(rather than at module scope) keeps this module import-cycle-free: nothing
in `app.domains.executions.tasks` needs to import this module back.

Sprint 7 (schedules domain) adds a second, periodic task -
`run_due_scheduled_jobs` - registered on Celery Beat via `beat_schedule`
below, running every 60 seconds. Its actual logic lives in
`app.domains.schedules.tasks` (imported lazily, same reasoning as above);
each tick it enqueues this same `run_automated_execution` task for every
`ScheduledJob` that's currently due. Running a real Beat scheduler process
alongside a worker is a normal deployment concern (`celery -A app.worker
beat --loglevel=info`, in addition to the `worker` process from the
docstring above) - pytest never runs Beat itself; see
`app.domains.schedules.tasks.run_due_scheduled_jobs_sync()`'s own docstring
for how tests invoke the periodic task's logic directly instead.
"""
from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "genqa",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    "run-due-scheduled-jobs": {
        "task": "run_due_scheduled_jobs",
        "schedule": 60.0,  # seconds
    },
}


@celery_app.task(name="run_automated_execution")
def run_automated_execution(execution_id: str) -> None:
    from app.domains.executions.tasks import run_automated_execution_sync

    run_automated_execution_sync(execution_id)


@celery_app.task(name="run_due_scheduled_jobs")
def run_due_scheduled_jobs() -> None:
    from app.domains.schedules.tasks import run_due_scheduled_jobs_sync

    run_due_scheduled_jobs_sync()


@celery_app.task(name="run_performance_test")
def run_performance_test(run_id: str) -> None:
    from app.domains.performance.tasks import run_performance_test_sync

    run_performance_test_sync(run_id)
