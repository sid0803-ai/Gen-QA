"""Pydantic schemas for the automation domain (per-test-case automation
script + version history)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domains.automation.models import AutomationScriptStatus, ScriptSource


class AutomationScriptGenerate(BaseModel):
    """Body for POST .../automation-script. `environment_id` is used only as
    generation context (so the script's base_url placeholder is meaningful)
    - it is not persisted onto the script itself."""

    environment_id: uuid.UUID | None = None


class AutomationScriptUpdate(BaseModel):
    """Body for PATCH .../automation-script: a human edit of the current
    script code."""

    code: str


class ScriptVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version_number: int
    code: str
    source: ScriptSource
    created_by: uuid.UUID
    created_at: datetime


class ScriptVersionSummary(BaseModel):
    """Version-list item - omits `code` (see AutomationScript.versions)."""

    model_config = ConfigDict(from_attributes=True)

    version_number: int
    source: ScriptSource
    created_by: uuid.UUID
    created_at: datetime


class AutomationScriptRead(BaseModel):
    id: uuid.UUID
    test_case_id: uuid.UUID
    status: AutomationScriptStatus
    current_version: ScriptVersionRead
    created_at: datetime
    updated_at: datetime
