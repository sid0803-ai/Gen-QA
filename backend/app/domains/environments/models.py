"""Environment model (environments domain, Sprint 5 - new, project-scoped).

A lightweight target test executions run against: a name, a base URL, and a
flat dict of string->string variables (extra env vars handed to an automated
execution's subprocess, e.g. test credentials/feature flags).

SECURITY NOTE - explicitly accepted scope cut this sprint: `variables` is
stored as plain JSONB, **not encrypted**. The architecture's own security
section calls for encrypted secrets eventually (this is exactly the kind of
field - API keys, test-account passwords - that would want it), but building
a secrets-encryption story (KMS/envelope encryption, key rotation, etc.) is
out of scope for this sprint. This is a known, documented gap - see
`backend/README.md`'s security-follow-ups section - not an oversight.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.domains.identity.models import User  # noqa: F401 (registers User on the shared registry)
from app.domains.projects.models import Project  # noqa: F401 (registers Project on the shared registry)


class Environment(Base):
    __tablename__ = "environments"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    # Plain dict[str, str] - NOT encrypted, see module docstring.
    variables: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
