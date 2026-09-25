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
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

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


class SavedApiRequest(Base):
    __tablename__ = "saved_api_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
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
