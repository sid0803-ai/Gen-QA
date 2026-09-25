"""PerformanceTest / PerformanceTestRun models (performance domain, Sprint 10
- new, project-scoped).

"Performance Testing" is a load-testing tool built on top of the existing
`api_performer` domain: rather than letting a user author a whole separate
load-testing request shape, a `PerformanceTest` simply points at one already-
saved `SavedApiRequest` (api_performer's own persisted HTTP request) and
layers a virtual-users/duration config on top of it. Running a test (via
`POST .../runs`) resolves that saved request's `{{base_url}}`/`{{VARIABLE}}`
placeholders the exact same way api_performer's own execute endpoint does
(reusing `api_performer.service.apply_substitution`/`resolve_environment`
directly - see `app.domains.performance.service`), generates a k6 script for
it, and runs that script as a real subprocess via the external `k6` binary.

SCOPE CUTS - explicitly accepted this sprint (same documentation convention
as `api_performer/models.py`'s own scope-cut section):

1. **One saved request per performance test, never a whole collection.** A
   `PerformanceTest.saved_request_id` FK targets exactly one
   `SavedApiRequest` - there is no way to load-test an entire
   `ApiCollection`/`ApiFolder` in one run (e.g. a multi-step user journey).
   That is a reasonable future sprint (would need a real load-testing DSL for
   sequencing/thinking-time between steps), not an oversight; single-request
   load testing already covers the common "is this one endpoint fast enough
   under load" case k6 is built for.

2. **k6 is an external binary, not a pip package.** `run_k6_script()`
   (service.py) shells out to `settings.k6_binary_path` (default `"k6"`,
   assumed on PATH; overridable via `K6_BINARY_PATH` env var for a portable
   binary - same posture as this codebase's existing portable-binary
   handling for Redis/Playwright's Chrome channel). A dev machine without k6
   installed gets every run ending `status="failed"` with a clear
   `error_message` ("k6 binary not found on PATH...") rather than a crash -
   this is a deliberately graceful degradation, not a missing feature.

3. **No live progress streaming.** A run's status only ever transitions
   `queued -> running -> completed`/`failed`, polled the same way
   `executions`' automated runs are polled - there is no websocket/SSE
   streaming of k6's live per-second output. Metrics are only available once
   the whole run finishes and k6's `--summary-export` JSON is parsed.

4. **`raw_summary` stores k6's full parsed summary JSON unencrypted/
   un-redacted**, same posture as this codebase's other "store the whole
   diagnostic blob" fields (e.g. `Execution.logs`) - it may contain response
   header values/URLs from the target if the saved request's own config
   does, no new gap beyond what api_performer's execute endpoint already
   accepts as this project's SSRF/secrets posture (see api_performer's own
   module docstring, point 2).
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Identity, Integer, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.domains.api_performer.models import SavedApiRequest  # noqa: F401 (registers on the shared registry)
from app.domains.identity.models import User  # noqa: F401
from app.domains.projects.models import Project  # noqa: F401


class PerformanceTestRunStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class PerformanceTest(Base):
    __tablename__ = "performance_tests"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    # The saved API request this performance test targets - see module
    # docstring, scope cut #1 (exactly one request, never a whole
    # collection). CASCADE: deleting the saved request deletes any
    # performance test built on top of it, same posture as deleting a
    # project cascading everything in it.
    saved_request_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("saved_api_requests.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Virtual users - how many concurrent iterations k6 runs for the
    # duration of the test.
    vus: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    created_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Same monotonic-ordering trick as every other domain's `sequence` -
    # used to order "newest first" deterministically.
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(always=True), nullable=False, unique=True)


class PerformanceTestRun(Base):
    """One actual k6 run of a `PerformanceTest`'s config, at the moment it
    was triggered. `vus`/`duration_seconds` are snapshotted onto the run
    (rather than always read live off `PerformanceTest`) so that editing a
    test's config later never rewrites the history of what a past run
    actually used - same "snapshot the config that was actually used"
    reasoning as `Execution` snapshotting a test case's approved script
    version at run time rather than re-reading "whatever the test case looks
    like now"."""

    __tablename__ = "performance_test_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    performance_test_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("performance_tests.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[PerformanceTestRunStatus] = mapped_column(
        SAEnum(
            PerformanceTestRunStatus,
            name="performance_test_run_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=PerformanceTestRunStatus.queued,
    )
    # Snapshots of the config actually used for this run - see class docstring.
    vus: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Metrics parsed out of k6's `--summary-export` JSON - all nullable,
    # populated only once the run reaches `completed`. Never populated (stay
    # null) on `failed`.
    request_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failed_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    p95_duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    requests_per_second: Mapped[float | None] = mapped_column(Float, nullable=True)
    # k6's full parsed summary JSON, for future drill-down - see module
    # docstring point 4.
    raw_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Populated on `failed` only (k6 binary not found, timed out, non-zero
    # exit with no parsable summary, ...) - never left to an unhandled
    # exception; see `app.domains.performance.service.run_k6_script`.
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    sequence: Mapped[int] = mapped_column(BigInteger, Identity(always=True), nullable=False, unique=True)
