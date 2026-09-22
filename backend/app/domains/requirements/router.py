"""Routes: /api/v1/projects/{project_id}/requirements/* and nested
/analyses/*, /feasibility/*, /strategy/* (requirements + ai-analysis +
feasibility + test-strategy domains).

Role rule: `viewer` can read (GET) everything; `member`/`admin` can
create/update requirements and trigger/edit/approve/reject
analyses/feasibility-studies/test-strategies; only `admin` can delete a
requirement (no delete endpoint exists for analyses/feasibility/strategy).
Enforced the same way as the projects domain: repository functions call
`project_repository.require_membership(..., min_role=...)` and raise
`NotAMemberError` (-> 404, never leaks existence) or `InsufficientRoleError`
(-> 403); GET routes additionally declare `Depends(require_project_role(...))`
as a belt-and-braces gate, matching the existing projects router's
convention.
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


def _to_requirement_read(
    requirement, latest_feasibility_status: str, latest_strategy_status: str
) -> schemas.RequirementRead:
    """RequirementRead can't be built via `.model_validate(requirement)` alone
    (Sprint 3): latest_feasibility_status/latest_strategy_status aren't ORM
    columns, so every route that returns a RequirementRead must compute and
    pass them explicitly - this helper keeps that in one place."""
    return schemas.RequirementRead(
        id=requirement.id,
        project_id=requirement.project_id,
        title=requirement.title,
        description=requirement.description,
        business_objective=requirement.business_objective,
        acceptance_criteria=requirement.acceptance_criteria,
        priority=requirement.priority,
        created_by=requirement.created_by,
        created_at=requirement.created_at,
        updated_at=requirement.updated_at,
        latest_feasibility_status=latest_feasibility_status,
        latest_strategy_status=latest_strategy_status,
    )


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
        feasibility_status, strategy_status = await repository.get_latest_feasibility_and_strategy_status(
            db, requirement.id
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(
            status_code=403, detail="Member role required on this project."
        ) from exc
    return _to_requirement_read(requirement, feasibility_status, strategy_status)


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
            latest_analysis_status=latest_analysis_status,
            latest_feasibility_status=latest_feasibility_status,
            latest_strategy_status=latest_strategy_status,
            created_at=requirement.created_at,
        )
        for requirement, latest_analysis_status, latest_feasibility_status, latest_strategy_status in rows
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
        requirement, feasibility_status, strategy_status = await repository.get_requirement_latest_statuses(
            db, project_id, requirement_id, current_user.id
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requirement not found.") from exc
    return _to_requirement_read(requirement, feasibility_status, strategy_status)


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
        feasibility_status, strategy_status = await repository.get_latest_feasibility_and_strategy_status(
            db, requirement.id
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(
            status_code=403, detail="Member role required on this project."
        ) from exc
    except repository.RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requirement not found.") from exc
    return _to_requirement_read(requirement, feasibility_status, strategy_status)


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


# --- Feasibility Studies ------------------------------------------------


@router.post(
    "/{project_id}/requirements/{requirement_id}/feasibility",
    response_model=schemas.FeasibilityRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_feasibility_study(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.FeasibilityRead:
    try:
        feasibility = await service.generate_feasibility_study(
            db, project_id, requirement_id, current_user.id
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(
            status_code=403, detail="Member role required on this project."
        ) from exc
    except repository.RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requirement not found.") from exc
    return schemas.FeasibilityRead.model_validate(feasibility)


@router.get(
    "/{project_id}/requirements/{requirement_id}/feasibility",
    response_model=list[schemas.FeasibilityListItem],
)
async def list_feasibility_studies(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[schemas.FeasibilityListItem]:
    try:
        rows = await repository.list_feasibility_studies(db, project_id, requirement_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requirement not found.") from exc
    return [schemas.FeasibilityListItem.model_validate(f) for f in rows]


@router.get(
    "/{project_id}/requirements/{requirement_id}/feasibility/{feasibility_id}",
    response_model=schemas.FeasibilityRead,
)
async def get_feasibility_study(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    feasibility_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> schemas.FeasibilityRead:
    try:
        feasibility = await repository.get_feasibility_study(
            db, project_id, requirement_id, feasibility_id, current_user.id
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requirement not found.") from exc
    except repository.FeasibilityNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Feasibility study not found.") from exc
    return schemas.FeasibilityRead.model_validate(feasibility)


@router.patch(
    "/{project_id}/requirements/{requirement_id}/feasibility/{feasibility_id}",
    response_model=schemas.FeasibilityRead,
)
async def update_feasibility_study(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    feasibility_id: uuid.UUID,
    payload: schemas.FeasibilityPayloadUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.FeasibilityRead:
    try:
        feasibility = await repository.update_feasibility_payload(
            db,
            project_id,
            requirement_id,
            feasibility_id,
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
    except repository.FeasibilityNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Feasibility study not found.") from exc
    except repository.FeasibilityNotDraftError as exc:
        raise HTTPException(
            status_code=409, detail="Feasibility study can only be edited while in draft status."
        ) from exc
    return schemas.FeasibilityRead.model_validate(feasibility)


@router.post(
    "/{project_id}/requirements/{requirement_id}/feasibility/{feasibility_id}/approve",
    response_model=schemas.FeasibilityRead,
)
async def approve_feasibility_study(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    feasibility_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.FeasibilityRead:
    try:
        feasibility = await repository.approve_feasibility_study(
            db, project_id, requirement_id, feasibility_id, current_user.id
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(
            status_code=403, detail="Member role required on this project."
        ) from exc
    except repository.RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requirement not found.") from exc
    except repository.FeasibilityNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Feasibility study not found.") from exc
    except repository.FeasibilityNotDraftError as exc:
        raise HTTPException(
            status_code=409, detail="Only a draft feasibility study can be approved."
        ) from exc
    return schemas.FeasibilityRead.model_validate(feasibility)


@router.post(
    "/{project_id}/requirements/{requirement_id}/feasibility/{feasibility_id}/reject",
    response_model=schemas.FeasibilityRead,
)
async def reject_feasibility_study(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    feasibility_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.FeasibilityRead:
    try:
        feasibility = await repository.reject_feasibility_study(
            db, project_id, requirement_id, feasibility_id, current_user.id
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(
            status_code=403, detail="Member role required on this project."
        ) from exc
    except repository.RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requirement not found.") from exc
    except repository.FeasibilityNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Feasibility study not found.") from exc
    except repository.FeasibilityNotDraftError as exc:
        raise HTTPException(
            status_code=409, detail="Only a draft feasibility study can be rejected."
        ) from exc
    return schemas.FeasibilityRead.model_validate(feasibility)


# --- Test Strategies ------------------------------------------------------


@router.post(
    "/{project_id}/requirements/{requirement_id}/strategy",
    response_model=schemas.StrategyRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_test_strategy(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.StrategyRead:
    try:
        strategy = await service.generate_test_strategy(
            db, project_id, requirement_id, current_user.id
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(
            status_code=403, detail="Member role required on this project."
        ) from exc
    except repository.RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requirement not found.") from exc
    return schemas.StrategyRead.model_validate(strategy)


@router.get(
    "/{project_id}/requirements/{requirement_id}/strategy",
    response_model=list[schemas.StrategyListItem],
)
async def list_test_strategies(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[schemas.StrategyListItem]:
    try:
        rows = await repository.list_test_strategies(db, project_id, requirement_id, current_user.id)
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requirement not found.") from exc
    return [schemas.StrategyListItem.model_validate(s) for s in rows]


@router.get(
    "/{project_id}/requirements/{requirement_id}/strategy/{strategy_id}",
    response_model=schemas.StrategyRead,
)
async def get_test_strategy(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    strategy_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _membership: ProjectMember = Depends(require_project_role(ProjectRole.viewer)),
    db: AsyncSession = Depends(get_db),
) -> schemas.StrategyRead:
    try:
        strategy = await repository.get_test_strategy(
            db, project_id, requirement_id, strategy_id, current_user.id
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except repository.RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requirement not found.") from exc
    except repository.StrategyNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Test strategy not found.") from exc
    return schemas.StrategyRead.model_validate(strategy)


@router.patch(
    "/{project_id}/requirements/{requirement_id}/strategy/{strategy_id}",
    response_model=schemas.StrategyRead,
)
async def update_test_strategy(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    strategy_id: uuid.UUID,
    payload: schemas.StrategyPayloadUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.StrategyRead:
    try:
        strategy = await repository.update_test_strategy_payload(
            db,
            project_id,
            requirement_id,
            strategy_id,
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
    except repository.StrategyNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Test strategy not found.") from exc
    except repository.StrategyNotDraftError as exc:
        raise HTTPException(
            status_code=409, detail="Test strategy can only be edited while in draft status."
        ) from exc
    return schemas.StrategyRead.model_validate(strategy)


@router.post(
    "/{project_id}/requirements/{requirement_id}/strategy/{strategy_id}/approve",
    response_model=schemas.StrategyRead,
)
async def approve_test_strategy(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    strategy_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.StrategyRead:
    try:
        strategy = await repository.approve_test_strategy(
            db, project_id, requirement_id, strategy_id, current_user.id
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(
            status_code=403, detail="Member role required on this project."
        ) from exc
    except repository.RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requirement not found.") from exc
    except repository.StrategyNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Test strategy not found.") from exc
    except repository.StrategyNotDraftError as exc:
        raise HTTPException(
            status_code=409, detail="Only a draft test strategy can be approved."
        ) from exc
    return schemas.StrategyRead.model_validate(strategy)


@router.post(
    "/{project_id}/requirements/{requirement_id}/strategy/{strategy_id}/reject",
    response_model=schemas.StrategyRead,
)
async def reject_test_strategy(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    strategy_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.StrategyRead:
    try:
        strategy = await repository.reject_test_strategy(
            db, project_id, requirement_id, strategy_id, current_user.id
        )
    except project_repository.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except project_repository.InsufficientRoleError as exc:
        raise HTTPException(
            status_code=403, detail="Member role required on this project."
        ) from exc
    except repository.RequirementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requirement not found.") from exc
    except repository.StrategyNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Test strategy not found.") from exc
    except repository.StrategyNotDraftError as exc:
        raise HTTPException(
            status_code=409, detail="Only a draft test strategy can be rejected."
        ) from exc
    return schemas.StrategyRead.model_validate(strategy)
