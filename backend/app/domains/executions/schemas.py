"""Pydantic schemas for the executions domain."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from app.domains.executions.models import MANUAL_TERMINAL_STATUSES, ExecutionKind, ExecutionStatus


class ExecutionCreate(BaseModel):
    """Two shapes depending on `type`, validated together here (FastAPI
    turns a failed validator into a 422):
      - manual: `status` is required and must be one of passed/failed/
        blocked/skipped; `actual_result`/`comments` are optional free text.
      - automated: `status`/`actual_result`/`comments` must all be omitted -
        the server always starts an automated execution at "pending" and
        fills `logs`/`error_message` in once the Celery task completes.
    """

    test_case_id: uuid.UUID
    environment_id: uuid.UUID
    type: ExecutionKind
    status: ExecutionStatus | None = None
    actual_result: str | None = None
    comments: str | None = None

    @model_validator(mode="after")
    def _validate_shape(self) -> "ExecutionCreate":
        if self.type == ExecutionKind.manual:
            if self.status is None:
                raise ValueError("status is required for a manual execution.")
            if self.status not in MANUAL_TERMINAL_STATUSES:
                allowed = ", ".join(sorted(s.value for s in MANUAL_TERMINAL_STATUSES))
                raise ValueError(f"status must be one of [{allowed}] for a manual execution.")
        else:
            if self.status is not None:
                raise ValueError("status must not be provided for an automated execution (server-assigned).")
            if self.actual_result is not None or self.comments is not None:
                raise ValueError("actual_result/comments are manual-only fields.")
        return self


class ExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    test_case_id: uuid.UUID
    environment_id: uuid.UUID
    type: ExecutionKind
    status: ExecutionStatus
    triggered_by: uuid.UUID
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    actual_result: str | None
    comments: str | None
    logs: str | None
    error_message: str | None
    created_at: datetime
