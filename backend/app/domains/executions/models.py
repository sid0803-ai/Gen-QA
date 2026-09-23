"""Execution model (executions domain, Sprint 5 - new, project-scoped).

An Execution records one run of a test case against an environment, either
`type="manual"` (a human recording a result that already happened - already
`completed_at`-stamped at creation) or `type="automated"` (enqueues a Celery
task that actually runs the test case's current *approved* automation
script as a real subprocess and records a genuine pass/fail result - see
`app.worker`/`app.domains.executions.tasks`).

No screenshot/video/trace artifact capture this sprint (needs object storage
- S3/MinIO - which isn't built yet); `logs`/`error_message` (automated) and
`actual_result`/`comments` (manual) are the whole text-only result surface.
See `backend/README.md` for both of these documented as explicit scope cuts.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Integer, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.domains.environments.models import Environment  # noqa: F401 (registers on the shared registry)
from app.domains.identity.models import User  # noqa: F401
from app.domains.projects.models import Project  # noqa: F401
from app.domains.testcases.models import TestCase  # noqa: F401


class ExecutionKind(str, enum.Enum):
    """Named `ExecutionKind` (not `ExecutionType`) to avoid confusion with
    `app.domains.testcases.models.ExecutionType` (a test case's *intended*
    execution mode - manual/automation/hybrid - a different concept from
    "what kind of execution record is this")."""

    manual = "manual"
    automated = "automated"


class ExecutionStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    passed = "passed"
    failed = "failed"
    blocked = "blocked"
    skipped = "skipped"
    error = "error"


# Manual executions may only ever be created directly in one of these
# terminal statuses (a human reports something that already happened);
# "pending"/"running" are automated-only transient states.
MANUAL_TERMINAL_STATUSES = {
    ExecutionStatus.passed,
    ExecutionStatus.failed,
    ExecutionStatus.blocked,
    ExecutionStatus.skipped,
}


class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    test_case_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False
    )
    environment_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("environments.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[ExecutionKind] = mapped_column(
        SAEnum(ExecutionKind, name="execution_kind", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    status: Mapped[ExecutionStatus] = mapped_column(
        SAEnum(ExecutionStatus, name="execution_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=ExecutionStatus.pending,
    )
    triggered_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Manual-only:
    actual_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Automated-only:
    logs: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Same monotonic-ordering trick as TestCase.sequence/AIAnalysis.sequence -
    # used to order "newest first" deterministically (two executions created
    # in quick succession can share a `created_at` value).
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(always=True), nullable=False, unique=True)
