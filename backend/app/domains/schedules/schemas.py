"""Pydantic schemas for the schedules domain."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ScheduledJobCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    test_case_id: uuid.UUID
    environment_id: uuid.UUID
    cron_expression: str = Field(min_length=1, max_length=255)
    enabled: bool = True


class ScheduledJobUpdate(BaseModel):
    """Any subset of the editable fields. Same "omitted means leave
    unchanged" PATCH convention as every other domain in this codebase (see
    e.g. `app.domains.environments.schemas.EnvironmentUpdate`). Note
    `test_case_id` is intentionally NOT editable here - changing which test
    case a schedule runs is a different-enough operation (it would need a
    fresh approved-automation-script check) that this sprint treats it as
    "delete this schedule, create a new one" instead."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    cron_expression: str | None = Field(default=None, min_length=1, max_length=255)
    enabled: bool | None = None
    environment_id: uuid.UUID | None = None


class ScheduledJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    test_case_id: uuid.UUID
    environment_id: uuid.UUID
    name: str
    cron_expression: str
    enabled: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
