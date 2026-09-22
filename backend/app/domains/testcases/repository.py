"""Data-access layer for the testcases domain (project-scoped Test Case
Repository).

CRITICAL ISOLATION RULE (same as every other domain): every function here
that reads or writes a TestCase/TestCaseVersion scoped to a project takes
`project_id` + the requesting user's id and enforces membership (and, where
relevant, a minimum role) via `project_repository.require_membership`
before touching any row. TestCase rows are additionally always filtered by
`project_id`, so a test case id from another project can never be reached
even if guessed.

The one exception is `create_ai_test_case_draft()`, an *internal* (never
directly router-reachable) helper used only by
`app.domains.requirements.service.approve_test_design()` to promote an
already-membership-checked TestDesign's scenarios into TestCase rows inside
that same call's transaction - see its own docstring.
"""
import enum
import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.projects import repository as project_repository
from app.domains.projects.models import ProjectRole
from app.domains.requirements.models import Requirement, RequirementPriority
from app.domains.testcases.models import (
    ExecutionType,
    TestCase,
    TestCaseCategory,
    TestCaseCounter,
    TestCaseSeverity,
    TestCaseSource,
    TestCaseStatus,
    TestCaseVersion,
    TestingLevel,
)

# Fields whose value is one of these Postgres-enum-backed types. Every enum
# value flowing into this module may arrive either as a plain `str` (e.g.
# from app.domains.ai.schemas.TestDesignScenario, whose fields are plain
# Literals, not instances of these model-level Enum classes - see
# create_ai_test_case_draft()) or as an already-correct Enum instance (e.g.
# from testcases.schemas, whose fields ARE these Enum classes). Calling
# `EnumClass(x)` normalizes either case: `type(x) is EnumClass` short-
# circuits and returns `x` unchanged, otherwise it's looked up as a plain
# value string - so it's always safe to route a value through its enum
# class before assigning it to an ORM attribute typed as that SAEnum
# column, matching the rest of this codebase's convention of only ever
# setting enum-typed ORM attributes from real Enum instances.
_ENUM_FIELDS: dict[str, type[enum.Enum]] = {
    "category": TestCaseCategory,
    "testing_level": TestingLevel,
    "priority": RequirementPriority,
    "severity": TestCaseSeverity,
    "execution_type": ExecutionType,
    "status": TestCaseStatus,
}


def _normalize_enum_fields(values: dict) -> dict:
    """Return a copy of `values` with every key in `_ENUM_FIELDS` present
    and non-None routed through its Enum class (see `_ENUM_FIELDS` above)."""
    normalized = dict(values)
    for field, enum_cls in _ENUM_FIELDS.items():
        if normalized.get(field) is not None:
            normalized[field] = enum_cls(normalized[field])
    return normalized


class RequirementNotFoundError(Exception):
    """Requirement doesn't exist in this project (or the project doesn't) -> 404."""


class TestCaseNotFoundError(Exception):
    """Test case doesn't exist in this project -> 404."""


class TestCaseAlreadyApprovedError(Exception):
    """Test case is already approved -> 409 (only draft -> approved is a
    valid transition; AI-promoted test cases are already approved from the
    moment they're created)."""


# Fields a human can PATCH; also exactly the fields snapshotted into a
# TestCaseVersion on every edit (see update_test_case()).
_EDITABLE_FIELDS = [
    "title",
    "category",
    "testing_level",
    "priority",
    "severity",
    "preconditions",
    "test_data",
    "steps",
    "expected_result",
    "business_rule",
    "automation_candidate",
    "execution_type",
    "tags",
]


def _serialize(value):
    """JSON-safe representation of one TestCase field value, for a
    TestCaseVersion snapshot: enum members become their `.value`, every
    other already-JSON-safe type (str/bool/list) passes through unchanged."""
    if isinstance(value, enum.Enum):
        return value.value
    return value


async def _get_requirement_row(
    db: AsyncSession, project_id: uuid.UUID, requirement_id: uuid.UUID
) -> Requirement | None:
    stmt = select(Requirement).where(
        Requirement.id == requirement_id, Requirement.project_id == project_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _get_test_case_row(
    db: AsyncSession, project_id: uuid.UUID, test_case_id: uuid.UUID, *, for_update: bool = False
) -> TestCase | None:
    stmt = select(TestCase).where(TestCase.id == test_case_id, TestCase.project_id == project_id)
    if for_update:
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _next_code(db: AsyncSession, project_id: uuid.UUID) -> str:
    """Concurrency-safe sequential 'TC-001', 'TC-002', ... code generation,
    scoped per project.

    Safety approach: a per-project counter row (`test_case_counters`),
    locked with `SELECT ... FOR UPDATE` inside the *same* transaction as the
    TestCase insert that follows (both this function and the eventual
    db.add()/commit happen on the same AsyncSession before any commit).
    Postgres blocks a second concurrent transaction's `FOR UPDATE` on the
    same counter row until the first transaction commits or rolls back, so
    two concurrent test-case creations in the same project can never
    observe/consume the same `next_value` - this is what rules out the
    naive `count(*) + 1` approach's race condition (which can hand out the
    same code to two concurrent requests, since both would count the same
    pre-insert row total before either commits).

    The counter row is created on first use via an upsert
    (`INSERT ... ON CONFLICT DO NOTHING`); Postgres serializes concurrent
    first-use inserts the same way (the "loser" of the ON CONFLICT race
    blocks until the "winner"'s transaction resolves, then sees the
    now-existing row), so the very first code generated for a project is
    equally safe under concurrency.
    """
    upsert_stmt = (
        pg_insert(TestCaseCounter)
        .values(project_id=project_id, next_value=1)
        .on_conflict_do_nothing(index_elements=["project_id"])
    )
    await db.execute(upsert_stmt)

    locked = await db.execute(
        select(TestCaseCounter).where(TestCaseCounter.project_id == project_id).with_for_update()
    )
    counter = locked.scalar_one()
    code_number = counter.next_value
    counter.next_value = code_number + 1
    return f"TC-{code_number:03d}"


async def create_ai_test_case_draft(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    test_design_id: uuid.UUID,
    created_by: uuid.UUID,
    title: str,
    category: str,
    testing_level: str,
    priority: str,
    severity: str,
    preconditions: str,
    test_data: str,
    steps: list[str],
    expected_result: str,
    business_rule: str,
    automation_candidate: bool,
) -> TestCase:
    """Create one TestCase promoted from an approved TestDesign scenario
    (`source="ai"`, `status="approved"` immediately).

    Deliberately does NOT call db.commit() - the caller
    (`app.domains.requirements.service.approve_test_design()`) creates every
    promoted TestCase plus the parent TestDesign's own status update inside
    one transaction/commit, so approving a TestDesign and promoting its
    included scenarios into TestCase rows are atomic (all-or-nothing).
    Membership/role is already verified by that caller before this is ever
    reached - this function is an internal cross-domain call, never
    directly reachable via a router, so it does not repeat that check.

    `category`/`testing_level`/`priority`/`severity` arrive here as plain
    `str` (the caller is `app.domains.requirements.service`, working off a
    `TestDesignScenario` from `app.domains.ai.schemas`, whose fields are
    plain `Literal`s, not instances of this domain's Enum classes) - see
    `_normalize_enum_fields()`."""
    code = await _next_code(db, project_id)
    normalized = _normalize_enum_fields(
        {"category": category, "testing_level": testing_level, "priority": priority, "severity": severity}
    )
    test_case = TestCase(
        project_id=project_id,
        requirement_id=requirement_id,
        test_design_id=test_design_id,
        code=code,
        title=title,
        category=normalized["category"],
        testing_level=normalized["testing_level"],
        priority=normalized["priority"],
        severity=normalized["severity"],
        preconditions=preconditions,
        test_data=test_data,
        steps=steps,
        expected_result=expected_result,
        business_rule=business_rule or "",
        automation_candidate=automation_candidate,
        execution_type=(ExecutionType.automation if automation_candidate else ExecutionType.manual),
        status=TestCaseStatus.approved,
        source=TestCaseSource.ai,
        tags=[],
        created_by=created_by,
    )
    db.add(test_case)
    await db.flush()
    return test_case


async def create_test_case(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    requirement_id: uuid.UUID,
    title: str,
    category: str,
    testing_level: str,
    priority: str,
    severity: str,
    preconditions: str,
    test_data: str,
    steps: list[str],
    expected_result: str,
    business_rule: str | None,
    automation_candidate: bool,
    execution_type: str | None,
    tags: list[str] | None,
) -> TestCase:
    """Manual (human-authored) test case creation: `source="human"`,
    `status="draft"`."""
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    requirement = await _get_requirement_row(db, project_id, requirement_id)
    if requirement is None:
        raise RequirementNotFoundError()

    code = await _next_code(db, project_id)
    normalized = _normalize_enum_fields(
        {"category": category, "testing_level": testing_level, "priority": priority, "severity": severity}
    )
    resolved_execution_type = (
        ExecutionType(execution_type)
        if execution_type is not None
        else (ExecutionType.automation if automation_candidate else ExecutionType.manual)
    )
    test_case = TestCase(
        project_id=project_id,
        requirement_id=requirement_id,
        test_design_id=None,
        code=code,
        title=title,
        category=normalized["category"],
        testing_level=normalized["testing_level"],
        priority=normalized["priority"],
        severity=normalized["severity"],
        preconditions=preconditions,
        test_data=test_data,
        steps=steps,
        expected_result=expected_result,
        business_rule=business_rule or "",
        automation_candidate=automation_candidate,
        execution_type=resolved_execution_type,
        status=TestCaseStatus.draft,
        source=TestCaseSource.human,
        tags=tags or [],
        created_by=user_id,
    )
    db.add(test_case)
    await db.commit()
    await db.refresh(test_case)
    return test_case


async def list_test_cases(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    requirement_id: uuid.UUID | None = None,
    testing_level: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    automation_candidate: bool | None = None,
    search: str | None = None,
) -> list[tuple[TestCase, str]]:
    """Returns (test_case, requirement_title) tuples, newest first."""
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)

    stmt = (
        select(TestCase, Requirement.title)
        .join(Requirement, Requirement.id == TestCase.requirement_id)
        .where(TestCase.project_id == project_id)
    )
    if requirement_id is not None:
        stmt = stmt.where(TestCase.requirement_id == requirement_id)
    if testing_level is not None:
        stmt = stmt.where(TestCase.testing_level == TestingLevel(testing_level))
    if category is not None:
        stmt = stmt.where(TestCase.category == TestCaseCategory(category))
    if priority is not None:
        stmt = stmt.where(TestCase.priority == RequirementPriority(priority))
    if status is not None:
        stmt = stmt.where(TestCase.status == TestCaseStatus(status))
    if automation_candidate is not None:
        stmt = stmt.where(TestCase.automation_candidate == automation_candidate)
    if search:
        stmt = stmt.where(TestCase.title.ilike(f"%{search}%"))
    stmt = stmt.order_by(TestCase.sequence.desc())

    result = await db.execute(stmt)
    return [(row[0], row[1]) for row in result.all()]


async def get_test_case(
    db: AsyncSession, project_id: uuid.UUID, test_case_id: uuid.UUID, user_id: uuid.UUID
) -> TestCase:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    test_case = await _get_test_case_row(db, project_id, test_case_id)
    if test_case is None:
        raise TestCaseNotFoundError()
    return test_case


async def update_test_case(
    db: AsyncSession,
    project_id: uuid.UUID,
    test_case_id: uuid.UUID,
    user_id: uuid.UUID,
    updates: dict,
) -> TestCase:
    """Apply any subset of `_EDITABLE_FIELDS` and create a TestCaseVersion
    snapshot of the state *after* the edit. The TestCase row is fetched with
    `FOR UPDATE` so two concurrent PATCHes on the SAME test case are
    serialized (the second blocks until the first commits), which keeps
    `version_number` gap-free/unique the same way `_next_code()` keeps
    `code` unique - same class of race, same row-locking fix."""
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    test_case = await _get_test_case_row(db, project_id, test_case_id, for_update=True)
    if test_case is None:
        raise TestCaseNotFoundError()

    normalized = _normalize_enum_fields(updates)
    for field in _EDITABLE_FIELDS:
        if field not in normalized:
            continue
        value = normalized[field]
        if value is None:
            continue
        setattr(test_case, field, value)
    test_case.updated_by = user_id
    await db.flush()

    count_result = await db.execute(
        select(func.count()).select_from(TestCaseVersion).where(TestCaseVersion.test_case_id == test_case.id)
    )
    next_version_number = int(count_result.scalar_one()) + 1

    snapshot = {field: _serialize(getattr(test_case, field)) for field in _EDITABLE_FIELDS}
    version = TestCaseVersion(
        test_case_id=test_case.id,
        version_number=next_version_number,
        snapshot=snapshot,
        edited_by=user_id,
    )
    db.add(version)

    await db.commit()
    await db.refresh(test_case)
    return test_case


async def approve_test_case(
    db: AsyncSession, project_id: uuid.UUID, test_case_id: uuid.UUID, user_id: uuid.UUID
) -> TestCase:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    test_case = await _get_test_case_row(db, project_id, test_case_id)
    if test_case is None:
        raise TestCaseNotFoundError()
    if test_case.status != TestCaseStatus.draft:
        raise TestCaseAlreadyApprovedError()

    test_case.status = TestCaseStatus.approved
    test_case.updated_by = user_id
    await db.commit()
    await db.refresh(test_case)
    return test_case


async def delete_test_case(
    db: AsyncSession, project_id: uuid.UUID, test_case_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.admin)
    test_case = await _get_test_case_row(db, project_id, test_case_id)
    if test_case is None:
        raise TestCaseNotFoundError()

    await db.delete(test_case)
    await db.commit()


async def list_test_case_versions(
    db: AsyncSession, project_id: uuid.UUID, test_case_id: uuid.UUID, user_id: uuid.UUID
) -> list[TestCaseVersion]:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    test_case = await _get_test_case_row(db, project_id, test_case_id)
    if test_case is None:
        raise TestCaseNotFoundError()

    stmt = (
        select(TestCaseVersion)
        .where(TestCaseVersion.test_case_id == test_case_id)
        .order_by(TestCaseVersion.version_number.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
