"""Pydantic schemas for the api_performer domain."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domains.api_performer.models import HttpMethod


# --- ApiCollection -------------------------------------------------------


class ApiCollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class ApiCollectionUpdate(BaseModel):
    """Any subset of the editable fields. Same "omitted and null both mean
    leave unchanged" convention as every other PATCH in this codebase."""

    name: str | None = Field(default=None, min_length=1, max_length=255)


class ApiCollectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


# --- ApiFolder -------------------------------------------------------


class ApiFolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class ApiFolderUpdate(BaseModel):
    """Any subset of the editable fields. Same "omitted and null both mean
    leave unchanged" convention as every other PATCH in this codebase."""

    name: str | None = Field(default=None, min_length=1, max_length=255)


class ApiFolderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    collection_id: uuid.UUID
    name: str
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


# --- Tree ----------------------------------------------------------------


class TreeRequestNode(BaseModel):
    """Lightweight per-request shape for the tree endpoint - id/name/method
    only. The full request (headers/body/query params/environment_id/etc.)
    is fetched via the existing `GET /api-requests/{request_id}` endpoint,
    unchanged - the tree exists to save the frontend an N+1 round trip for
    its sidebar, not to duplicate the full resource."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    method: HttpMethod


class TreeFolderNode(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    requests: list[TreeRequestNode]


class TreeCollectionNode(BaseModel):
    """One collection, with its folders and top-level (folder_id IS NULL)
    requests. A given request appears in exactly one place in this tree:
    either inside its folder's `requests` list, or - if it has no folder -
    directly in its collection's own `requests` list. Never both, never
    neither."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    requests: list[TreeRequestNode]
    folders: list[TreeFolderNode]


# --- SavedApiRequest -------------------------------------------------------


class SavedApiRequestCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    method: HttpMethod
    url: str = Field(min_length=1, max_length=2048)
    headers: dict[str, str] = Field(default_factory=dict)
    query_params: dict[str, str] = Field(default_factory=dict)
    body: str | None = None
    environment_id: uuid.UUID | None = None
    # Sprint 9: every saved request now lives in exactly one collection.
    # Required (404 if it doesn't resolve in this project).
    collection_id: uuid.UUID
    # Optional folder within `collection_id` (404 if it doesn't resolve in
    # this project, 400 if it belongs to a different collection than
    # `collection_id`). Omitted/null -> the request sits at the
    # collection's top level.
    folder_id: uuid.UUID | None = None


class SavedApiRequestUpdate(BaseModel):
    """Any subset of the editable fields. Same "omitted and null both mean
    leave unchanged" convention as every other PATCH in this codebase -
    `headers`/`query_params` can be replaced wholesale but not explicitly
    cleared back to `{}` via `null` (send `{}` instead), and `environment_id`
    likewise cannot be cleared back to "no environment" via this endpoint
    (there is currently no way to un-set it back to null once set - a known,
    minor limitation shared with every other nullable-FK PATCH field in this
    codebase's established convention).

    `folder_id` is a DELIBERATE, DOCUMENTED EXCEPTION to that blanket
    convention: moving a request out of a folder back to its collection's
    top level is a real, common action in a Postman-style UI (drag a
    request out of a folder), so this field distinguishes "key omitted from
    the request body" (leave `folder_id` unchanged) from "key present, set
    to `null`" (explicitly clear it back to the collection's top level) via
    Pydantic's `model_fields_set` (see the router, which reads
    `"folder_id" in payload.model_fields_set`) - not via the field's own
    default. Setting `folder_id` to a real folder id via this endpoint is
    validated the same way as on create: 404 if it doesn't resolve in this
    project, 400 if it belongs to a different collection than the request's
    own (unchanged) `collection_id`.

    `collection_id` itself is NOT patchable this sprint - moving a request
    between collections is a deliberate scope cut, same pattern as Sprint
    7's `ScheduledJob.test_case_id`: "delete and recreate in the target
    collection" is the workaround. Every other nullable-FK PATCH field in
    this codebase keeps the ordinary blanket convention; only `folder_id`
    gets this treatment, because "un-file back to top level" is common
    enough here to be worth the special case, whereas e.g. `environment_id`
    was not judged common enough for that treatment in Sprint 8.
    """

    name: str | None = Field(default=None, min_length=1, max_length=255)
    method: HttpMethod | None = None
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    headers: dict[str, str] | None = None
    query_params: dict[str, str] | None = None
    body: str | None = None
    environment_id: uuid.UUID | None = None
    folder_id: uuid.UUID | None = None


class SavedApiRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    collection_id: uuid.UUID
    folder_id: uuid.UUID | None
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
    SavedApiRequestCreate minus `name`/`collection_id`/`folder_id` (nothing
    is persisted, so there's no collection/folder to file it under)."""

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
