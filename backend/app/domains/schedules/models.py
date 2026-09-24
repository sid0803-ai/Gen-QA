"""ScheduledJob model (schedules domain, Sprint 7 - new, project-scoped).

A ScheduledJob is a recurring instruction to run one test case's current
*approved* automation script against one environment, on a cron schedule.
The actual firing is done by a Celery Beat periodic task (see
`app.worker`/`app.domains.schedules.tasks`), which enqueues the SAME
`run_automated_execution` Celery task (`app.domains.executions.tasks`) that
a normal "run this now" automated execution uses - a scheduled run is not a
different kind of execution, just a different trigger source.

`next_run_at` is always kept in sync with `cron_expression`/`enabled` by the
repository layer (see `app.domains.schedules.repository.compute_next_run_at`)
rather than computed lazily on read, so the periodic task's hot "what's due"
query (`enabled = true AND next_run_at <= now()`) can be a plain indexed
range scan - see the `(project_id, enabled, next_run_at)` index below.
"""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Identity, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.domains.environments.models import Environment  # noqa: F401 (registers on the shared registry)
from app.domains.identity.models import User  # noqa: F401
from app.domains.projects.models import Project  # noqa: F401
from app.domains.testcases.models import TestCase  # noqa: F401


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"
    __table_args__ = (
        Index("ix_scheduled_jobs_due", "project_id", "enabled", "next_run_at"),
    )

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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cron_expression: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
