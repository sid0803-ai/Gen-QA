"""Routes: /api/v1/projects/{project_id}/requirements/* and nested
/analyses/* (requirements + ai-analysis domains).

Role rule: `viewer` can read (GET) everything; `member`/`admin` can
create/update requirements and trigger/approve/reject analyses; only `admin`
can delete a requirement. Enforced the same way as the projects domain:
repository functions call `project_repository.require_membership(...,
min_role=...)` and raise `NotAMemberError` (-> 404, never leaks existence)
or `InsufficientRoleError` (-> 403); GET routes additionally declare
`Depends(require_project_role(...))` as a belt-and-braces gate, matching the
existing projects router's convention.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, require_project_role
from app.domains.identity.models import User
from app.domains.projects import repository as project_repository
from app.domains.projects.models import ProjectMember, ProjectRole
from app.domains.requirements import repository, schemas, service

router = APIRouter(prefix="/projects", tags=["requirements"])


# --- Requirements ---------------------------------------------------------


@router.post(
    "/{project_id}/requirements",
    response_model=schemas.RequirementRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_requirement(
    project_id: uuid.UUID,
    payload: schemas.RequirementCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.RequirementRead:
    try:
        requirement = await repository.create_requirement(
            db,
            project_id,
            current_user.id,
            title=payload.title,
            description=payload.description,
            business_objective=payload.business_objective,
            acceptance_criteria=payload.acceptance_criteria,
            priority=payload.priority,
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(
            status_code=403, detail="Member role required on this project."
        ) from exc
    return schemas.RequirementRead.model_validate(requirement)


@router.get("/{project_id}/requirements", response_model=list[schemas.RequirementListItem])
async def list_requirements(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[schemas.RequirementListItem]:
    try:
        rows = await repository.list_requirements(db, project_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    return [
        schemas.RequirementListItem(
            id=requirement.id,
            title=requirement.title,
            priority=requirement.priority,
            latest_analysis_status=latest_status,
            created_at=requirement.created_at,
        )
        for requirement, latest_status in rows
    ]


@router.get("/{project_id}/requirements/{requirement_id}", response_model=schemas.RequirementRead)
async def get_requirement(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> schemas.RequirementRead:
    try:
        requirement = await repository.get_requirement(
            db, project_id, requirement_id, current_user.id
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requirement not found.") from exc
    return schemas.RequirementRead.model_validate(requirement)


@router.patch("/{project_id}/requirements/{requirement_id}", response_model=schemas.RequirementRead)
async def update_requirement(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    payload: schemas.RequirementUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.RequirementRead:
    try:
        requirement = await repository.update_requirement(
            db,
            project_id,
            requirement_id,
            current_user.id,
            title=payload.title,
            description=payload.description,
            business_objective=payload.business_objective,
            acceptance_criteria=payload.acceptance_criteria,
            priority=payload.priority,
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(
            status_code=403, detail="Member role required on this project."
        ) from exc
    except repository.RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requirement not found.") from exc
    return schemas.RequirementRead.model_validate(requirement)


@router.delete("/{project_id}/requirements/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_requirement(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await repository.delete_requirement(db, project_id, requirement_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(
            status_code=403, detail="Admin role required on this project."
        ) from exc
    except repository.RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requirement not found.") from exc


# --- AI Analyses ------------------------------------------------------------


@router.post(
    "/{project_id}/requirements/{requirement_id}/analyses",
    response_model=schemas.AnalysisRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_analysis(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.AnalysisRead:
    try:
        analysis = await service.generate_analysis(db, project_id, requirement_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(
            status_code=403, detail="Member role required on this project."
        ) from exc
    except repository.RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requirement not found.") from exc
    return schemas.AnalysisRead.model_validate(analysis)


@router.get(
    "/{project_id}/requirements/{requirement_id}/analyses",
    response_model=list[schemas.AnalysisListItem],
)
async def list_analyses(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[schemas.AnalysisListItem]:
    try:
        analyses = await repository.list_analyses(db, project_id, requirement_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requirement not found.") from exc
    return [schemas.AnalysisListItem.model_validate(a) for a in analyses]


@router.get(
    "/{project_id}/requirements/{requirement_id}/analyses/{analysis_id}",
    response_model=schemas.AnalysisRead,
)
async def get_analysis(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    analysis_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> schemas.AnalysisRead:
    try:
        analysis = await repository.get_analysis(
            db, project_id, requirement_id, analysis_id, current_user.id
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requirement not found.") from exc
    except repository.AnalysisNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Analysis not found.") from exc
    return schemas.AnalysisRead.model_validate(analysis)


@router.patch(
    "/{project_id}/requirements/{requirement_id}/analyses/{analysis_id}",
    response_model=schemas.AnalysisRead,
)
async def update_analysis(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    analysis_id: uuid.UUID,
    payload: schemas.AnalysisPayloadUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.AnalysisRead:
    try:
        analysis = await repository.update_analysis_payload(
            db,
            project_id,
            requirement_id,
            analysis_id,
            current_user.id,
            payload.payload.model_dump(mode="json"),
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(
            status_code=403, detail="Member role required on this project."
        ) from exc
    except repository.RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requirement not found.") from exc
    except repository.AnalysisNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Analysis not found.") from exc
    except repository.AnalysisNotDraftError as exc:
        raise HTTPException(
            status_code=409, detail="Analysis can only be edited while in draft status."
        ) from exc
    return schemas.AnalysisRead.model_validate(analysis)


@router.post(
    "/{project_id}/requirements/{requirement_id}/analyses/{analysis_id}/approve",
    response_model=schemas.AnalysisRead,
)
async def approve_analysis(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    analysis_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.AnalysisRead:
    try:
        analysis = await repository.approve_analysis(
            db, project_id, requirement_id, analysis_id, current_user.id
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(
            status_code=403, detail="Member role required on this project."
        ) from exc
    except repository.RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requirement not found.") from exc
    except repository.AnalysisNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Analysis not found.") from exc
    except repository.AnalysisNotDraftError as exc:
        raise HTTPException(
            status_code=409, detail="Only a draft analysis can be approved."
        ) from exc
    return schemas.AnalysisRead.model_validate(analysis)


@router.post(
    "/{project_id}/requirements/{requirement_id}/analyses/{analysis_id}/reject",
    response_model=schemas.AnalysisRead,
)
async def reject_analysis(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    analysis_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.AnalysisRead:
    try:
        analysis = await repository.reject_analysis(
            db, project_id, requirement_id, analysis_id, current_user.id
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(
            status_code=403, detail="Member role required on this project."
        ) from exc
    except repository.RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requirement not found.") from exc
    except repository.AnalysisNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Analysis not found.") from exc
    except repository.AnalysisNotDraftError as exc:
        raise HTTPException(
            status_code=409, detail="Only a draft analysis can be rejected."
        ) from exc
    return schemas.AnalysisRead.model_validate(analysis)
