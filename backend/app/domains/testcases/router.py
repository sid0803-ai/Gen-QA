"""Routes: /api/v1/projects/{project_id}/test-cases/* (testcases domain).

Project-scoped Test Case Repository - NOT nested under a requirement (a
test case always carries a `requirement_id` for traceability, but is
listed/searched/reached at the project level, since it can also stand
independently of any single Test Design). Role rule: `viewer` reads,
`member` creates/edits/approves, `admin` deletes - same convention as every
other domain.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, require_project_role
from app.domains.identity.models import User
from app.domains.projects import repository as project_repository
from app.domains.projects.models import ProjectMember, ProjectRole
from app.domains.requirements.models import RequirementPriority
from app.domains.testcases import repository, schemas
from app.domains.testcases.models import TestCaseCategory, TestCaseStatus, TestingLevel

router = APIRouter(prefix="/projects", tags=["test-cases"])


def _to_list_item(test_case, requirement_title: str) -> schemas.TestCaseListItem:
    return schemas.TestCaseListItem(
        id=test_case.id,
        code=test_case.code,
        title=test_case.title,
        testing_level=test_case.testing_level,
        category=test_case.category,
        priority=test_case.priority,
        severity=test_case.severity,
        status=test_case.status,
        source=test_case.source,
        automation_candidate=test_case.automation_candidate,
        execution_type=test_case.execution_type,
        requirement_id=test_case.requirement_id,
        requirement_title=requirement_title,
        tags=test_case.tags,
        created_at=test_case.created_at,
    )


@router.get("/{project_id}/test-cases", response_model=list[schemas.TestCaseListItem])
async def list_test_cases(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID | None = None,
    testing_level: TestingLevel | None = None,
    category: TestCaseCategory | None = None,
    priority: RequirementPriority | None = None,
    status: TestCaseStatus | None = None,
    automation_candidate: bool | None = None,
    search: str | None = None,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[schemas.TestCaseListItem]:
    try:
        rows = await repository.list_test_cases(
            db,
            project_id,
            current_user.id,
            requirement_id=requirement_id,
            testing_level=testing_level.value if testing_level else None,
            category=category.value if category else None,
            priority=priority.value if priority else None,
            status=status.value if status else None,
            automation_candidate=automation_candidate,
            search=search,
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    return [_to_list_item(tc, title) for tc, title in rows]


@router.get("/{project_id}/test-cases/{test_case_id}", response_model=schemas.TestCaseRead)
async def get_test_case(
    project_id: uuid.UUID,
    test_case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> schemas.TestCaseRead:
    try:
        test_case = await repository.get_test_case(db, project_id, test_case_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.TestCaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Test case not found.") from exc
    return schemas.TestCaseRead.model_validate(test_case)


@router.post(
    "/{project_id}/test-cases",
    response_model=schemas.TestCaseRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_test_case(
    project_id: uuid.UUID,
    payload: schemas.TestCaseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.TestCaseRead:
    try:
        test_case = await repository.create_test_case(
            db,
            project_id,
            current_user.id,
            requirement_id=payload.requirement_id,
            title=payload.title,
            category=payload.category.value,
            testing_level=payload.testing_level.value,
            priority=payload.priority.value,
            severity=payload.severity.value,
            preconditions=payload.preconditions,
            test_data=payload.test_data,
            steps=payload.steps,
            expected_result=payload.expected_result,
            business_rule=payload.business_rule,
            automation_candidate=payload.automation_candidate,
            execution_type=payload.execution_type.value if payload.execution_type else None,
            tags=payload.tags,
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(
            status_code=403, detail="Member role required on this project."
        ) from exc
    except repository.RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requirement not found.") from exc
    return schemas.TestCaseRead.model_validate(test_case)


@router.patch("/{project_id}/test-cases/{test_case_id}", response_model=schemas.TestCaseRead)
async def update_test_case(
    project_id: uuid.UUID,
    test_case_id: uuid.UUID,
    payload: schemas.TestCaseUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.TestCaseRead:
    # repository.update_test_case() normalizes enum-typed fields itself
    # (accepts either a plain str or an already-correct Enum instance), so
    # this dict can be handed off as-is - see
    # app.domains.testcases.repository._normalize_enum_fields().
    updates = payload.model_dump(exclude_unset=True)
    try:
        test_case = await repository.update_test_case(db, project_id, test_case_id, current_user.id, updates)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(
            status_code=403, detail="Member role required on this project."
        ) from exc
    except repository.TestCaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Test case not found.") from exc
    return schemas.TestCaseRead.model_validate(test_case)


@router.post("/{project_id}/test-cases/{test_case_id}/approve", response_model=schemas.TestCaseRead)
async def approve_test_case(
    project_id: uuid.UUID,
    test_case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.TestCaseRead:
    try:
        test_case = await repository.approve_test_case(db, project_id, test_case_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(
            status_code=403, detail="Member role required on this project."
        ) from exc
    except repository.TestCaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Test case not found.") from exc
    except repository.TestCaseAlreadyApprovedError as exc:
        raise HTTPException(status_code=409, detail="Test case is already approved.") from exc
    return schemas.TestCaseRead.model_validate(test_case)


@router.delete("/{project_id}/test-cases/{test_case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_case(
    project_id: uuid.UUID,
    test_case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await repository.delete_test_case(db, project_id, test_case_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Admin role required on this project.") from exc
    except repository.TestCaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Test case not found.") from exc


@router.get(
    "/{project_id}/test-cases/{test_case_id}/versions",
    response_model=list[schemas.TestCaseVersionRead],
)
async def list_test_case_versions(
    project_id: uuid.UUID,
    test_case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[schemas.TestCaseVersionRead]:
    try:
        versions = await repository.list_test_case_versions(db, project_id, test_case_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.TestCaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Test case not found.") from exc
    return [schemas.TestCaseVersionRead.model_validate(v) for v in versions]
