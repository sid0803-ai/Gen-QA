"""Data-access layer for the automation domain (per-test-case automation
script + version history, nested under a project + test case).

Same isolation rule as every other domain: every function takes `project_id`
+ the requesting user's id and enforces membership (and a minimum role,
where relevant) via `project_repository.require_membership`, plus verifies
the test case belongs to that project, before touching any AutomationScript/
ScriptVersion row.

Version lookups always run a fresh, explicit `SELECT ... ORDER BY
version_number` against `ScriptVersion` (see `_get_versions()`) rather than
reading `AutomationScript.versions` (the ORM relationship). This mirrors
`app.domains.testcases.repository.update_test_case()`'s own COUNT-query
approach for the exact same reason: under an `AsyncSession` with
`expire_on_commit=False` (as this codebase's test fixtures use, reusing one
session across many simulated "requests"), an already-loaded relationship
collection on an identity-mapped parent object is not automatically
refreshed after a later commit that adds more child rows through a plain
`db.add(child)` (rather than via the relationship attribute itself) - a
subsequent read of that stale collection can silently miss the just-added
row. A direct `SELECT` against the child table has no such staleness risk.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.automation.models import AutomationScript, AutomationScriptStatus, ScriptSource, ScriptVersion
from app.domains.projects import repository as project_repository
from app.domains.projects.models import ProjectRole
from app.domains.testcases.models import TestCase


class TestCaseNotFoundError(Exception):
    """Test case doesn't exist in this project (or the project doesn't) -> 404."""


class AutomationScriptNotFoundError(Exception):
    """No automation script exists yet for this test case -> 404."""


class AutomationScriptAlreadyApprovedError(Exception):
    """Script is already approved -> 409."""


async def _get_test_case_row(
    db: AsyncSession, project_id: uuid.UUID, test_case_id: uuid.UUID
) -> TestCase | None:
    stmt = select(TestCase).where(TestCase.id == test_case_id, TestCase.project_id == project_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _require_test_case(
    db: AsyncSession, project_id: uuid.UUID, test_case_id: uuid.UUID
) -> TestCase:
    test_case = await _get_test_case_row(db, project_id, test_case_id)
    if test_case is None:
        raise TestCaseNotFoundError()
    return test_case


async def _get_script_row(db: AsyncSession, test_case_id: uuid.UUID) -> AutomationScript | None:
    stmt = select(AutomationScript).where(AutomationScript.test_case_id == test_case_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _get_versions(db: AsyncSession, automation_script_id: uuid.UUID) -> list[ScriptVersion]:
    """Always a fresh query - see this module's docstring."""
    stmt = (
        select(ScriptVersion)
        .where(ScriptVersion.automation_script_id == automation_script_id)
        .order_by(ScriptVersion.version_number)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _get_script_with_versions(
    db: AsyncSession, test_case_id: uuid.UUID
) -> tuple[AutomationScript, list[ScriptVersion]] | None:
    script = await _get_script_row(db, test_case_id)
    if script is None:
        return None
    versions = await _get_versions(db, script.id)
    return script, versions


async def get_test_case_for_generation(
    db: AsyncSession, project_id: uuid.UUID, test_case_id: uuid.UUID, user_id: uuid.UUID
) -> TestCase:
    """Membership('member') + existence check only - used by the service
    layer before calling out to AIService, so an AI call is never made for a
    test case the caller can't reach/isn't privileged enough to touch."""
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    return await _require_test_case(db, project_id, test_case_id)


async def save_generated_script(
    db: AsyncSession,
    *,
    test_case_id: uuid.UUID,
    user_id: uuid.UUID,
    code: str,
) -> tuple[AutomationScript, list[ScriptVersion], bool]:
    """Create the AutomationScript row if it doesn't exist yet, then append a
    new `source="ai"` ScriptVersion and reset status to "draft". Returns
    (script, versions, created) - `created` is True the first time (caller
    uses it to pick 201 vs 200), False on every subsequent regeneration.
    Membership/test-case existence is already verified by
    `get_test_case_for_generation()` just before this is called."""
    script = await _get_script_row(db, test_case_id)
    created = script is None
    if script is None:
        script = AutomationScript(
            test_case_id=test_case_id, status=AutomationScriptStatus.draft, created_by=user_id
        )
        db.add(script)
        await db.flush()
        next_version_number = 1
    else:
        existing_versions = await _get_versions(db, script.id)
        next_version_number = (existing_versions[-1].version_number + 1) if existing_versions else 1

    version = ScriptVersion(
        automation_script_id=script.id,
        version_number=next_version_number,
        code=code,
        source=ScriptSource.ai,
        created_by=user_id,
    )
    db.add(version)
    script.status = AutomationScriptStatus.draft

    await db.commit()
    await db.refresh(script)
    versions = await _get_versions(db, script.id)
    return script, versions, created


async def get_automation_script(
    db: AsyncSession, project_id: uuid.UUID, test_case_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[AutomationScript, list[ScriptVersion]]:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    await _require_test_case(db, project_id, test_case_id)
    result = await _get_script_with_versions(db, test_case_id)
    if result is None:
        raise AutomationScriptNotFoundError()
    return result


async def update_script(
    db: AsyncSession,
    project_id: uuid.UUID,
    test_case_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    code: str,
) -> tuple[AutomationScript, list[ScriptVersion]]:
    """Human edit: creates a new `source="human"` ScriptVersion and resets
    `status="draft"` - same invariant as an AI regeneration (any edit always
    requires fresh approval)."""
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    await _require_test_case(db, project_id, test_case_id)
    script = await _get_script_row(db, test_case_id)
    if script is None:
        raise AutomationScriptNotFoundError()

    existing_versions = await _get_versions(db, script.id)
    next_version_number = (existing_versions[-1].version_number + 1) if existing_versions else 1
    version = ScriptVersion(
        automation_script_id=script.id,
        version_number=next_version_number,
        code=code,
        source=ScriptSource.human,
        created_by=user_id,
    )
    db.add(version)
    script.status = AutomationScriptStatus.draft

    await db.commit()
    await db.refresh(script)
    versions = await _get_versions(db, script.id)
    return script, versions


async def approve_script(
    db: AsyncSession, project_id: uuid.UUID, test_case_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[AutomationScript, list[ScriptVersion]]:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    await _require_test_case(db, project_id, test_case_id)
    script = await _get_script_row(db, test_case_id)
    if script is None:
        raise AutomationScriptNotFoundError()
    if script.status == AutomationScriptStatus.approved:
        raise AutomationScriptAlreadyApprovedError()

    script.status = AutomationScriptStatus.approved
    await db.commit()
    await db.refresh(script)
    versions = await _get_versions(db, script.id)
    return script, versions


async def list_versions(
    db: AsyncSession, project_id: uuid.UUID, test_case_id: uuid.UUID, user_id: uuid.UUID
) -> list[ScriptVersion]:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    await _require_test_case(db, project_id, test_case_id)
    result = await _get_script_with_versions(db, test_case_id)
    if result is None:
        raise AutomationScriptNotFoundError()
    _, versions = result
    return versions


async def get_approved_script_version(
    db: AsyncSession, test_case_id: uuid.UUID
) -> ScriptVersion | None:
    """Internal, non-membership-checked helper used by the executions
    domain (already membership-checked by its own caller) to load the
    current approved script's code for a test case, or None if the test
    case has no automation script or it isn't approved."""
    script = await _get_script_row(db, test_case_id)
    if script is None or script.status != AutomationScriptStatus.approved:
        return None
    versions = await _get_versions(db, script.id)
    if not versions:
        return None
    return versions[-1]
