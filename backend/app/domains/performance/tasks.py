"""The actual performance-test execution engine: loads a queued
`PerformanceTestRun` + its `PerformanceTest` + target `SavedApiRequest`,
resolves `{{base_url}}`/`{{VARIABLE}}` substitution via api_performer's own
`resolve_environment`/`apply_substitution`, generates a k6 script, runs it as
a real subprocess, and records the result.

Deliberately has NO dependency on Celery/`app.worker` - `app.worker.py`
imports *this* module's `run_performance_test_sync()` (deferred, inside its
task function body) rather than the other way around, same import-cycle-
avoidance reasoning as `app.domains.executions.tasks`.
"""
import asyncio
import concurrent.futures
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.domains.api_performer import service as api_performer_service
from app.domains.environments import repository as environments_repository
from app.domains.performance import repository as performance_repository
from app.domains.performance import service as performance_service


def run_performance_test_sync(run_id: str) -> None:
    """Sync entry point - Celery tasks are sync by default, and that's fine
    here.

    Always runs `_run()` to completion inside a brand-new thread (with its
    own fresh `asyncio.run()` event loop), rather than calling `asyncio.run()`
    directly on the calling thread - required for both a real Celery worker
    process AND `task_always_eager=True` test mode to work correctly. See
    `app.domains.executions.tasks.run_automated_execution_sync`'s docstring
    for the full rationale (pytest-asyncio already has an event loop running
    on the calling thread when `.delay()` runs eagerly in-process; a
    dedicated thread + fresh loop sidesteps that uniformly in both
    contexts)."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(asyncio.run, _run(run_id)).result()


async def _run(run_id_str: str) -> None:
    """Owns a dedicated, short-lived engine/connection pool for the whole
    lifetime of this one task invocation - see
    `app.domains.executions.tasks._run`'s docstring for why a shared,
    long-lived engine can't safely be reused across many different
    `asyncio.run()` event loops (asyncpg binds a connection to whichever
    loop was running when it was first checked out)."""
    run_id = uuid.UUID(run_id_str)
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            run = await performance_repository.get_run_for_task(db, run_id)
            if run is None:
                return  # Row vanished (e.g. project deleted concurrently) - nothing to do.
            test = await performance_repository.get_test_for_task(db, run.performance_test_id)
            if test is None:
                await performance_repository.record_failure(
                    db, run_id, error_message="Performance test no longer exists."
                )
                return
            saved_request = await performance_repository.get_saved_request_for_task(
                db, test.saved_request_id
            )
            if saved_request is None:
                await performance_repository.record_failure(
                    db, run_id, error_message="The saved API request this test targets no longer exists."
                )
                return

            # Flip queued -> running *before* the (slow) subprocess runs, so
            # a polling client sees the transition, not just queued -> terminal.
            await performance_repository.mark_running(db, run_id)

            try:
                environment = await api_performer_service.resolve_environment(
                    db, test.project_id, saved_request.environment_id, run.created_by
                )
            except environments_repository.EnvironmentNotFoundError:
                # Race: the environment was deleted between when the saved
                # request was last read and now (normally impossible since
                # `SavedApiRequest.environment_id` is ON DELETE SET NULL, but
                # guarded against rather than assumed unreachable).
                await performance_repository.record_failure(
                    db, run_id, error_message="The environment this request targets no longer exists."
                )
                return
            method = saved_request.method
            url, headers, _query_params, body = api_performer_service.apply_substitution(
                url=saved_request.url,
                headers=saved_request.headers,
                query_params=saved_request.query_params,
                body=saved_request.body,
                environment=environment,
            )
            vus = run.vus
            duration_seconds = run.duration_seconds

        script = performance_service.build_k6_script(
            method=method,
            url=url,
            headers=headers,
            body=body,
            vus=vus,
            duration_seconds=duration_seconds,
        )

        try:
            metrics = await asyncio.to_thread(
                performance_service.run_k6_script, script, duration_seconds=duration_seconds
            )
        except performance_service.K6RunError as exc:
            async with session_factory() as db:
                await performance_repository.record_failure(db, run_id, error_message=str(exc))
            return

        async with session_factory() as db:
            await performance_repository.record_success(db, run_id, **metrics)
    finally:
        await engine.dispose()
