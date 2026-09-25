"""SavedApiRequest model (api_performer domain, Sprint 8 - new, project-scoped).

"API Performer" is a built-in, Postman-lite tool: a project member can save
an ad-hoc HTTP request (method/URL/headers/query params/body), optionally
tied to a default `Environment` for `{{base_url}}`/`{{VAR}}` placeholder
substitution, and re-run it (or run one-off requests that are never
persisted at all) directly against a real target from inside the platform.

SCOPE CUTS - explicitly accepted this sprint (see `backend/README.md`'s
security-follow-ups section, same convention as `environments`' own
unencrypted-`variables` note):

1. **No execution history.** `POST .../execute` and
   `POST .../{request_id}/execute` are "run and see the result, right now" -
   neither endpoint persists anything about the call it made (no request/
   response log row, unlike the `executions` domain's `Execution` records).
   A user who wants a durable record of what an API returned has to copy it
   out of the response themselves. Building a saved execution-history table
   is a reasonable future sprint, not an oversight.

2. **SSRF: deliberately, knowingly out of scope.** This endpoint lets any
   project member (>= `member` role) direct *this backend server* to make an
   outbound HTTP request to any http/https host/port it names - including
   hosts on the backend's own internal network (other internal services,
   cloud metadata endpoints, etc.). That is unsafe in a general-purpose
   multi-tenant deployment. It is accepted here because the entire point of
   this tool is "let a QA engineer hit their own staging/internal APIs from
   inside the platform" - restricting egress would defeat the feature. A
   production deployment of this platform would eventually want a host
   allowlist/denylist and/or network-level egress restriction (e.g. routing
   these calls through a locked-down egress proxy) before exposing it to
   untrusted users. Not building that here is a visible, deliberate decision
   - not an oversight.

3. **`variables` substitution reuses `Environment.variables`**, which is
   itself unencrypted plain JSONB (see `environments/models.py`'s own
   docstring) - any secret stored there is handled with the same posture
   this sprint inherits, not a new gap introduced here.

SPRINT 9 - Collection/Folder hierarchy
=======================================
Sprint 9 restructures the flat list of `SavedApiRequest` rows into a
Postman-style **Collection -> Folder (optional) -> Request** hierarchy:

- `ApiCollection` is the top-level, project-scoped container. Every
  `SavedApiRequest` now belongs to exactly one `ApiCollection`
  (`collection_id`, CASCADE - deleting a collection is a real, user-facing
  destructive action that removes its folders and requests, same posture as
  deleting a project cascading everything in it).
- `ApiFolder` is a **single level of nesting only** - a folder belongs to
  exactly one collection, and there is no folder-within-folder nesting.
  This is a deliberate scope cut: Postman-style unlimited nesting would
  need a recursive tree query/schema for comparatively little value for a
  QA tool's request library; one level (collection -> folder -> request) is
  enough to group related requests without that complexity. Deleting a
  folder does **not** delete its requests - `SavedApiRequest.folder_id` is
  ON DELETE SET NULL, so its requests simply move back to the collection's
  top level (a request with `folder_id = null` sits directly under its
  collection, not inside any folder).
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, String, Text, and_, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.domains.environments.models import Environment  # noqa: F401 (registers on the shared registry)
from app.domains.identity.models import User  # noqa: F401
from app.domains.projects.models import Project  # noqa: F401


class HttpMethod(str, enum.Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class ApiCollection(Base):
    """Top-level, project-scoped container in the Collection -> Folder ->
    Request hierarchy (Sprint 9). See module docstring."""

    __tablename__ = "api_collections"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
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

    # Read-only relationships used only by the tree endpoint
    # (repository.get_tree) to eager-load in one round trip - all writes go
    # through the repository functions above, never through these.
    folders: Mapped[list["ApiFolder"]] = relationship(
        "ApiFolder",
        order_by="ApiFolder.sequence.desc()",
        viewonly=True,
    )
    # Top-level requests only (folder_id IS NULL) - a folder's own requests
    # are reached via ApiFolder.requests instead, so a request never appears
    # in both places.
    requests: Mapped[list["SavedApiRequest"]] = relationship(
        "SavedApiRequest",
        primaryjoin="and_(ApiCollection.id == SavedApiRequest.collection_id, "
        "SavedApiRequest.folder_id.is_(None))",
        order_by="SavedApiRequest.sequence.desc()",
        viewonly=True,
    )


class ApiFolder(Base):
    """A single level of nesting inside one `ApiCollection` - no
    folder-within-folder nesting (deliberate scope cut, see module
    docstring)."""

    __tablename__ = "api_folders"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("api_collections.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    sequence: Mapped[int] = mapped_column(BigInteger, Identity(always=True), nullable=False, unique=True)

    # Read-only, tree-endpoint-only relationship - see ApiCollection.folders'
    # comment above.
    requests: Mapped[list["SavedApiRequest"]] = relationship(
        "SavedApiRequest",
        order_by="SavedApiRequest.sequence.desc()",
        viewonly=True,
    )


class SavedApiRequest(Base):
    __tablename__ = "saved_api_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    # The collection this request lives in (Sprint 9). CASCADE: deleting a
    # collection is a real, user-facing destructive action that removes its
    # requests too (same posture as deleting a project cascading
    # everything in it). This is the final, post-backfill shape (NOT NULL);
    # the Sprint 9 migration adds the column nullable first, backfills every
    # pre-existing row into a per-project "My Requests" collection, then
    # tightens it to NOT NULL - see that migration's own docstring.
    collection_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("api_collections.id", ondelete="CASCADE"), nullable=False
    )
    # The (optional) folder this request is filed under, within
    # `collection_id`. SET NULL: deleting a folder un-files its requests
    # back to the collection's top level rather than deleting them - see
    # module docstring. `null` means "top level of the collection", not
    # "no collection" (`collection_id` always identifies the collection).
    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("api_folders.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[HttpMethod] = mapped_column(
        SAEnum(HttpMethod, name="api_performer_http_method", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    # May contain `{{base_url}}`/`{{VARIABLE_NAME}}` placeholders - see
    # app.domains.api_performer.service for the substitution rule.
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    headers: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    query_params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The default environment this saved request targets for placeholder
    # substitution when executed without an explicit override. ON DELETE
    # SET NULL: deleting an environment must not cascade-delete saved
    # requests that merely reference it as a default - it just clears the
    # reference (any `{{...}}` placeholders are then sent through literally
    # on the next execute, per the substitution rule).
    environment_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("environments.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Same monotonic-ordering trick as Execution.sequence/TestCase.sequence -
    # used to order "newest first" deterministically.
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(always=True), nullable=False, unique=True)
