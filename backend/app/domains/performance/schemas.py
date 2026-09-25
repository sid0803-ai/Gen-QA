"""Pydantic schemas for the performance domain."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domains.performance.models import PerformanceTestRunStatus

# Sane, deliberately generous-but-bounded caps to prevent someone
# accidentally DOSing their own machine (or an internal target) with a
# runaway vus/duration combination - see module docstring's scope cuts for
# the general posture on this being a "point it at your own stuff" tool.
MAX_VUS = 500
MAX_DURATION_SECONDS = 3600


# --- PerformanceTest -------------------------------------------------------


class PerformanceTestCreate(BaseModel):
    saved_request_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    vus: int = Field(default=5, ge=1, le=MAX_VUS)
    duration_seconds: int = Field(default=30, ge=1, le=MAX_DURATION_SECONDS)


class PerformanceTestUpdate(BaseModel):
    """Any subset of the editable fields. Standard "omitted means unchanged"
    PATCH convention used throughout this codebase - no nullable-FK-clearing
    semantics needed here (unlike api_performer's `folder_id`), since none of
    these fields are ever meant to be explicitly cleared back to null."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    vus: int | None = Field(default=None, ge=1, le=MAX_VUS)
    duration_seconds: int | None = Field(default=None, ge=1, le=MAX_DURATION_SECONDS)


class PerformanceTestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    saved_request_id: uuid.UUID
    name: str
    vus: int
    duration_seconds: int
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


# --- PerformanceTestRun ------------------------------------------------


class PerformanceTestRunRead(BaseModel):
    """Full run detail, including `raw_summary` - used for the single-run
    "get" endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    performance_test_id: uuid.UUID
    status: PerformanceTestRunStatus
    vus: int
    duration_seconds: int
    started_at: datetime | None
    completed_at: datetime | None
    request_count: int | None
    failed_count: int | None
    error_rate: float | None
    avg_duration_ms: float | None
    p95_duration_ms: float | None
    min_duration_ms: float | None
    max_duration_ms: float | None
    requests_per_second: float | None
    raw_summary: dict | None
    error_message: str | None
    created_by: uuid.UUID


class PerformanceTestRunSummary(BaseModel):
    """Lighter list-view variant without `raw_summary` - used for the runs
    list endpoint so a project with many/large runs doesn't pay to
    serialize every run's full k6 summary blob just to render a list."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    performance_test_id: uuid.UUID
    status: PerformanceTestRunStatus
    vus: int
    duration_seconds: int
    started_at: datetime | None
    completed_at: datetime | None
    request_count: int | None
    failed_count: int | None
    error_rate: float | None
    avg_duration_ms: float | None
    p95_duration_ms: float | None
    min_duration_ms: float | None
    max_duration_ms: float | None
    requests_per_second: float | None
    error_message: str | None
    created_by: uuid.UUID
