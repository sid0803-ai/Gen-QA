"""Pydantic schemas for the api_performer domain."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domains.api_performer.models import HttpMethod


class SavedApiRequestCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    method: HttpMethod
    url: str = Field(min_length=1, max_length=2048)
    headers: dict[str, str] = Field(default_factory=dict)
    query_params: dict[str, str] = Field(default_factory=dict)
    body: str | None = None
    environment_id: uuid.UUID | None = None


class SavedApiRequestUpdate(BaseModel):
    """Any subset of the editable fields. Same "omitted and null both mean
    leave unchanged" convention as every other PATCH in this codebase -
    `headers`/`query_params` can be replaced wholesale but not explicitly
    cleared back to `{}` via `null` (send `{}` instead), and `environment_id`
    likewise cannot be cleared back to "no environment" via this endpoint
    (there is currently no way to un-set it back to null once set - a known,
    minor limitation shared with every other nullable-FK PATCH field in this
    codebase's established convention)."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    method: HttpMethod | None = None
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    headers: dict[str, str] | None = None
    query_params: dict[str, str] | None = None
    body: str | None = None
    environment_id: uuid.UUID | None = None


class SavedApiRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    method: HttpMethod
    url: str
    headers: dict[str, str]
    query_params: dict[str, str]
    body: str | None
    environment_id: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class AdHocExecuteRequest(BaseModel):
    """Body for `POST /api-requests/execute` - identical shape to
    SavedApiRequestCreate minus `name` (nothing is persisted)."""

    method: HttpMethod
    url: str = Field(min_length=1, max_length=2048)
    headers: dict[str, str] = Field(default_factory=dict)
    query_params: dict[str, str] = Field(default_factory=dict)
    body: str | None = None
    environment_id: uuid.UUID | None = None


class SavedRequestExecuteOverride(BaseModel):
    """Optional body for `POST /api-requests/{request_id}/execute`. If
    `environment_id` is provided (non-null), it overrides the saved
    request's own `environment_id` for this one run only - nothing is
    persisted. If omitted (or sent as `null`), the saved request's own
    `environment_id` is used, same "omitted/null both mean unchanged"
    convention as every PATCH body in this codebase."""

    environment_id: uuid.UUID | None = None


class ExecuteResponse(BaseModel):
    """Response shape for both execute endpoints (ad-hoc and saved).

    On a successful outbound call (any HTTP status code, including 4xx/5xx
    from the target - that is a normal result, not an error of this tool):
    `error` is `null` and the other four fields are populated from the real
    response (`headers` is the response's headers as a flat `dict[str,str]`;
    `body` is UTF-8 text, replacing undecodable bytes, truncated at ~1MB
    with a trailing note if the target's response exceeded that).

    On a failure to complete the outbound call at all (timeout, connection
    refused, DNS failure, etc. - deliberately NOT surfaced as a 5xx from
    this endpoint itself, since a failed *outbound* call is an expected,
    normal result for an ad-hoc HTTP tool): `error` holds a clear message,
    and the null-safe placeholders are `status_code=None`, `headers={}`,
    `body=""`, `duration_ms=0`.
    """

    status_code: int | None
    headers: dict[str, str]
    body: str
    duration_ms: int
    error: str | None
