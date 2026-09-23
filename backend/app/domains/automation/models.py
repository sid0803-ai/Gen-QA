"""AutomationScript + ScriptVersion models (automation domain, Sprint 5 -
new, test-case-scoped).

One `AutomationScript` per `TestCase` (one-to-one, enforced by the `unique`
constraint on `test_case_id`), with a `ScriptVersion` history that mirrors
`TestCaseVersion`'s own pattern exactly: a full snapshot (here, the whole
script source) per version, newest last (`version_number` ascending, 1-
indexed). Both an AI regeneration and a human edit always create a new
`ScriptVersion` and reset the parent `AutomationScript.status` back to
"draft" - the same "never silently re-approve stale content" invariant this
codebase uses everywhere else (see `app.domains.requirements`'s draft/
approve/reject lifecycles).
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.domains.identity.models import User  # noqa: F401 (registers User on the shared registry)
from app.domains.testcases.models import TestCase  # noqa: F401 (registers TestCase on the shared registry)


class AutomationScriptStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"


class ScriptSource(str, enum.Enum):
    ai = "ai"
    human = "human"


class AutomationScript(Base):
    __tablename__ = "automation_scripts"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    test_case_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("test_cases.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status: Mapped[AutomationScriptStatus] = mapped_column(
        SAEnum(
            AutomationScriptStatus,
            name="automation_script_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=AutomationScriptStatus.draft,
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

    versions: Mapped[list["ScriptVersion"]] = relationship(
        "ScriptVersion",
        back_populates="automation_script",
        cascade="all, delete-orphan",
        order_by="ScriptVersion.version_number",
    )


class ScriptVersion(Base):
    """One immutable snapshot (full script source) per version,
    version_number 1-indexed and incrementing once per generate/edit."""

    __tablename__ = "script_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    automation_script_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("automation_scripts.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[ScriptSource] = mapped_column(
        SAEnum(ScriptSource, name="script_source", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    automation_script: Mapped["AutomationScript"] = relationship(
        "AutomationScript", back_populates="versions"
    )
