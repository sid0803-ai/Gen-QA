"""The actual execution engine: runs a test case's current *approved*
automation script as a real Playwright Test subprocess and records a
genuine pass/fail/error result - the real engineering core of this sprint.

Deliberately has NO dependency on Celery/`app.worker` - `app.worker.py`
imports *this* module's `run_automated_execution_sync()` (deferred, inside
its task function body) rather than the other way around, so there is no
import cycle between "the Celery app" and "the task logic". This also keeps
the logic here independently testable/callable without needing Celery
installed at all.
"""
import asyncio
import concurrent.futures
import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.domains.automation import repository as automation_repository
from app.domains.executions import repository as executions_repository
from app.domains.executions.models import ExecutionStatus

# backend/app/domains/executions/tasks.py -> parents[3] == backend/
AUTOMATION_RUNNER_DIR = Path(__file__).resolve().parents[3] / "automation_runner"
SPEC_DIR = AUTOMATION_RUNNER_DIR / "tests"
SUBPROCESS_TIMEOUT_SECONDS = 120
_MAX_LOG_CHARS = 20_000
_MAX_ERROR_CHARS = 4_000


def run_automated_execution_sync(execution_id: str) -> None:
    """Sync entry point - Celery tasks are sync by default, and that's fine
    here.

    Always runs `_run()` to completion inside a brand-new thread (with its
    own fresh `asyncio.run()` event loop), rather than calling
    `asyncio.run()` directly on the calling thread. This matters because
    this function is called from two very different contexts:
      - a real Celery worker process (prefork/solo pool) - no event loop is
        running on that thread, so `asyncio.run()` directly would also work
        here, but...
      - `task_always_eager=True` test mode - `.delay()` runs the task
        function inline, in-process, which in this codebase's tests happens
        from *inside* an already-running asyncio event loop (pytest-asyncio
        gives every async test its own loop; calling an async repository
        function from an async test is itself running inside that loop).
        Calling `asyncio.run()` directly there would raise "asyncio.run()
        cannot be called from a running event loop".
    Running in a dedicated thread sidesteps that entirely, uniformly, in
    both contexts - the calling thread just blocks on `.result()` until the
    task's own event loop finishes, exactly matching real Celery's blocking
    "eager" semantics."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(asyncio.run, _run(execution_id)).result()


async def _run(execution_id_str: str) -> None:
    """Owns a dedicated, short-lived engine/connection pool for the whole
    lifetime of this one task invocation, rather than reusing the shared
    `app.core.db.engine`/`AsyncSessionLocal` singletons.

    This matters because `run_automated_execution_sync()` (above) runs this
    coroutine inside a brand-new thread + brand-new `asyncio.run()` event
    loop on *every* invocation. asyncpg binds a connection's internal
    asyncio primitives to whichever event loop was running when that
    connection was first checked out of the pool; a connection pool shared
    across many *different* event loops (one new loop per task) would
    eventually hand a task a connection bound to some earlier, now-closed
    loop and blow up with "Future ... attached to a different loop" - the
    exact class of bug `tests/conftest.py` documents and works around for
    its own per-test engines. Creating (and disposing) a fresh engine here
    sidesteps it entirely, the same way."""
    execution_id = uuid.UUID(execution_id_str)
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            execution = await executions_repository.get_execution_for_run(db, execution_id)
            if execution is None:
                return  # Row vanished (e.g. project deleted concurrently) - nothing to do.
            test_case_id = execution.test_case_id
            environment_id = execution.environment_id

            approved_version = await automation_repository.get_approved_script_version(db, test_case_id)
            environment = await executions_repository.get_environment_row(db, environment_id)

            # Flip pending -> running *before* the (slow) subprocess runs, so
            # a polling client sees the transition, not just pending -> terminal.
            await executions_repository.mark_running(db, execution_id)

        if approved_version is None or environment is None:
            # Shouldn't normally happen - create_pending_automated_execution()
            # already checked an approved script exists synchronously at
            # enqueue time - but guards against a race where the script was
            # un-approved/the environment deleted between enqueue and this
            # task running.
            async with session_factory() as db:
                await executions_repository.record_result(
                    db,
                    execution_id,
                    result_status=ExecutionStatus.error,
                    logs=None,
                    error_message="Automation script or environment no longer exists.",
                    duration_ms=None,
                )
            return

        result = await asyncio.to_thread(_execute_playwright_script, approved_version.code, environment)

        async with session_factory() as db:
            await executions_repository.record_result(
                db,
                execution_id,
                result_status=result["status"],
                logs=result["logs"],
                error_message=result["error_message"],
                duration_ms=result["duration_ms"],
            )
    finally:
        await engine.dispose()


def _combine_logs(stdout: str, stderr: str) -> str:
    combined = f"--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}"
    if len(combined) > _MAX_LOG_CHARS:
        combined = combined[:_MAX_LOG_CHARS] + "\n...[truncated]..."
    return combined


def _first_test_error(report: dict) -> str | None:
    """Walk the Playwright JSON reporter's suite tree looking for the first
    test result carrying an error message."""

    def walk(suites: list[dict]) -> str | None:
        for suite in suites or []:
            for spec in suite.get("specs", []) or []:
                for t in spec.get("tests", []) or []:
                    for r in t.get("results", []) or []:
                        error = r.get("error")
                        if error and error.get("message"):
                            return str(error["message"])
                        for e in r.get("errors", []) or []:
                            if e.get("message"):
                                return str(e["message"])
            nested = walk(suite.get("suites", []) or [])
            if nested:
                return nested
        return None

    return walk(report.get("suites", []) or [])


def _execute_playwright_script(code: str, environment: Any) -> dict:
    """Write `code` to a uniquely-named spec file inside the dedicated
    `automation_runner/` Playwright project, run it via
    `npx playwright test <file> --reporter=json`, and translate the result
    into `{status, logs, error_message, duration_ms}`.

    `environment.base_url` is set as `BASE_URL` (which the generated script
    reads via `process.env.BASE_URL ?? <placeholder>`) and every key/value
    in `environment.variables` is passed through as an additional env var -
    this is the plain-text environment-variable channel documented as this
    sprint's known "no secret encryption yet" gap (see
    `app.domains.environments.models`)."""
    SPEC_DIR.mkdir(parents=True, exist_ok=True)
    spec_name = f"exec_{uuid.uuid4().hex}.spec.ts"
    spec_path = SPEC_DIR / spec_name
    spec_path.write_text(code, encoding="utf-8")

    npx = shutil.which("npx") or ("npx.cmd" if os.name == "nt" else "npx")
    cmd = [npx, "playwright", "test", f"tests/{spec_name}", "--reporter=json"]

    env = os.environ.copy()
    env["BASE_URL"] = environment.base_url
    for key, value in (environment.variables or {}).items():
        env[str(key)] = str(value)

    started = time.monotonic()
    stdout, stderr = "", ""
    try:
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(AUTOMATION_RUNNER_DIR),
                env=env,
                capture_output=True,
                text=True,
                timeout=SUBPROCESS_TIMEOUT_SECONDS,
            )
            stdout, stderr = proc.stdout or "", proc.stderr or ""
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or "" if isinstance(exc.stdout, str) else ""
            stderr = (exc.stderr or "" if isinstance(exc.stderr, str) else "") + (
                f"\n\n[process killed: exceeded {SUBPROCESS_TIMEOUT_SECONDS}s timeout]"
            )
            return {
                "status": ExecutionStatus.error,
                "logs": _combine_logs(stdout, stderr),
                "error_message": f"playwright test run timed out after {SUBPROCESS_TIMEOUT_SECONDS}s.",
                "duration_ms": int((time.monotonic() - started) * 1000),
            }
        except OSError as exc:
            # e.g. npx not found at all on this machine.
            return {
                "status": ExecutionStatus.error,
                "logs": _combine_logs(stdout, stderr),
                "error_message": f"Failed to launch playwright test runner: {exc}",
                "duration_ms": int((time.monotonic() - started) * 1000),
            }
    finally:
        try:
            spec_path.unlink(missing_ok=True)
        except OSError:
            pass

    wall_ms = int((time.monotonic() - started) * 1000)

    try:
        report = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        # Errored before producing a report at all (TypeScript syntax error,
        # browser launch failure, missing dependency, ...) - map to "error"
        # with whatever diagnostic text is available, never a silent crash.
        diagnostic = stderr.strip() or stdout.strip() or "playwright produced no parsable output."
        return {
            "status": ExecutionStatus.error,
            "logs": _combine_logs(stdout, stderr),
            "error_message": diagnostic[:_MAX_ERROR_CHARS],
            "duration_ms": wall_ms,
        }

    stats = report.get("stats", {}) or {}
    expected = int(stats.get("expected", 0) or 0)
    unexpected = int(stats.get("unexpected", 0) or 0)
    skipped = int(stats.get("skipped", 0) or 0)
    report_duration = stats.get("duration")
    duration_ms = int(report_duration) if isinstance(report_duration, (int, float)) else wall_ms

    top_level_errors = report.get("errors") or []
    if expected == 0 and unexpected == 0 and skipped == 0 and top_level_errors:
        # No test ever actually ran (e.g. a config/compile error caught by
        # Playwright itself before test collection) - genuinely errored, not
        # "failed" (a failed test at least attempted to run).
        first = top_level_errors[0]
        message = first.get("message") if isinstance(first, dict) else str(first)
        return {
            "status": ExecutionStatus.error,
            "logs": _combine_logs(stdout, stderr),
            "error_message": (message or "Unknown playwright error.")[:_MAX_ERROR_CHARS],
            "duration_ms": duration_ms,
        }

    if unexpected > 0:
        message = _first_test_error(report) or "One or more assertions/steps failed."
        return {
            "status": ExecutionStatus.failed,
            "logs": _combine_logs(stdout, stderr),
            "error_message": message[:_MAX_ERROR_CHARS],
            "duration_ms": duration_ms,
        }

    if expected > 0:
        return {
            "status": ExecutionStatus.passed,
            "logs": _combine_logs(stdout, stderr),
            "error_message": None,
            "duration_ms": duration_ms,
        }

    # expected == 0, unexpected == 0, nothing skipped, no top-level errors:
    # the spec file matched no tests at all.
    return {
        "status": ExecutionStatus.error,
        "logs": _combine_logs(stdout, stderr),
        "error_message": "No tests were found/executed in the generated script.",
        "duration_ms": duration_ms,
    }
