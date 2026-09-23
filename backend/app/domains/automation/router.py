"""Routes: /api/v1/projects/{project_id}/test-cases/{test_case_id}/
automation-script/* (automation domain).

Nested under a test case, mirroring the requirement-review-stage shape
(draft -> edit-while-draft -> approve) but simpler since there's only ever
one *current* script slot per test case (a ScriptVersion history backs it,
same idea as TestCaseVersion). Role rule: `viewer` reads, `member` generates/
edits/approves - there is no delete endpoint (regenerating/editing is how you
replace a script; deleting the test case cascades the script away).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, require_project_role
from app.domains.automation import repository, schemas, service
from app.domains.automation.models import AutomationScript
from app.domains.environments import repository as environments_repository
from app.domains.identity.models import User
from app.domains.projects import repository as project_repository
from app.domains.projects.models import ProjectMember, ProjectRole

router = APIRouter(prefix="/projects", tags=["automation"])

_PREFIX = "/{project_id}/test-cases/{test_case_id}/automation-script"


def _to_read(script: AutomationScript, versions: list) -> schemas.AutomationScriptRead:
    current = versions[-1]
    return schemas.AutomationScriptRead(
        id=script.id,
        test_case_id=script.test_case_id,
        status=script.status,
        current_version=schemas.ScriptVersionRead.model_validate(current),
        created_at=script.created_at,
        updated_at=script.updated_at,
    )


@router.post(_PREFIX, response_model=schemas.AutomationScriptRead)
async def generate_automation_script(
    project_id: uuid.UUID,
    test_case_id: uuid.UUID,
    payload: schemas.AutomationScriptGenerate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.AutomationScriptRead:
    try:
        script, versions, created = await service.generate_script(
            db, project_id, test_case_id, current_user.id, payload.environment_id
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Member role required on this project.") from exc
    except repository.TestCaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Test case not found.") from exc
    except environments_repository.EnvironmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Environment not found.") from exc

    response = _to_read(script, versions)
    # 201 the first time a script is generated for this test case, 200 on
    # every subsequent regeneration.
    return JSONResponse(
        status_code=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        content=response.model_dump(mode="json"),
    )


@router.get(_PREFIX, response_model=schemas.AutomationScriptRead)
async def get_automation_script(
    project_id: uuid.UUID,
    test_case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> schemas.AutomationScriptRead:
    try:
        script, versions = await repository.get_automation_script(db, project_id, test_case_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.TestCaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Test case not found.") from exc
    except repository.AutomationScriptNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No automation script exists yet for this test case.") from exc
    return _to_read(script, versions)


@router.patch(_PREFIX, response_model=schemas.AutomationScriptRead)
async def update_automation_script(
    project_id: uuid.UUID,
    test_case_id: uuid.UUID,
    payload: schemas.AutomationScriptUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.AutomationScriptRead:
    try:
        script, versions = await repository.update_script(
            db, project_id, test_case_id, current_user.id, code=payload.code
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Member role required on this project.") from exc
    except repository.TestCaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Test case not found.") from exc
    except repository.AutomationScriptNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No automation script exists yet for this test case.") from exc
    return _to_read(script, versions)


@router.post(f"{_PREFIX}/approve", response_model=schemas.AutomationScriptRead)
async def approve_automation_script(
    project_id: uuid.UUID,
    test_case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.AutomationScriptRead:
    try:
        script, versions = await repository.approve_script(db, project_id, test_case_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Member role required on this project.") from exc
    except repository.TestCaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Test case not found.") from exc
    except repository.AutomationScriptNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No automation script exists yet for this test case.") from exc
    except repository.AutomationScriptAlreadyApprovedError as exc:
        raise HTTPException(status_code=409, detail="Automation script is already approved.") from exc
    return _to_read(script, versions)


@router.get(f"{_PREFIX}/versions", response_model=list[schemas.ScriptVersionSummary])
async def list_automation_script_versions(
    project_id: uuid.UUID,
    test_case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[schemas.ScriptVersionSummary]:
    try:
        versions = await repository.list_versions(db, project_id, test_case_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.TestCaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Test case not found.") from exc
    except repository.AutomationScriptNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No automation script exists yet for this test case.") from exc
    # Newest first, matching every other version-list endpoint in this codebase.
    return [
        schemas.ScriptVersionSummary.model_validate(v)
        for v in sorted(versions, key=lambda v: v.version_number, reverse=True)
    ]
