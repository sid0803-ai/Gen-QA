"""Data-access layer for the api_performer domain (project-scoped).

Same isolation rule as every other domain: every function takes
`project_id` + the requesting user's id and enforces membership (and a
minimum role, where relevant) via `project_repository.require_membership`
before touching any row. Rows are additionally always filtered by
`project_id`, so a saved-request id from another project can never be
reached even if guessed.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.api_performer.models import HttpMethod, SavedApiRequest
from app.domains.projects import repository as project_repository
from app.domains.projects.models import ProjectRole


class SavedApiRequestNotFoundError(Exception):
    """Saved request doesn't exist in this project (or the project doesn't) -> 404."""


async def _get_request_row(
    db: AsyncSession, project_id: uuid.UUID, request_id: uuid.UUID
) -> SavedApiRequest | None:
    stmt = select(SavedApiRequest).where(
        SavedApiRequest.id == request_id, SavedApiRequest.project_id == project_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_saved_request(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    name: str,
    method: HttpMethod,
    url: str,
    headers: dict[str, str] | None,
    query_params: dict[str, str] | None,
    body: str | None,
    environment_id: uuid.UUID | None,
) -> SavedApiRequest:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    saved_request = SavedApiRequest(
        project_id=project_id,
        name=name,
        method=method,
        url=url,
        headers=headers or {},
        query_params=query_params or {},
        body=body,
        environment_id=environment_id,
        created_by=user_id,
    )
    db.add(saved_request)
    await db.commit()
    await db.refresh(saved_request)
    return saved_request


async def list_saved_requests(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID
) -> list[SavedApiRequest]:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    stmt = (
        select(SavedApiRequest)
        .where(SavedApiRequest.project_id == project_id)
        .order_by(SavedApiRequest.sequence.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_saved_request(
    db: AsyncSession, project_id: uuid.UUID, request_id: uuid.UUID, user_id: uuid.UUID
) -> SavedApiRequest:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    saved_request = await _get_request_row(db, project_id, request_id)
    if saved_request is None:
        raise SavedApiRequestNotFoundError()
    return saved_request


async def update_saved_request(
    db: AsyncSession,
    project_id: uuid.UUID,
    request_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    name: str | None,
    method: HttpMethod | None,
    url: str | None,
    headers: dict[str, str] | None,
    query_params: dict[str, str] | None,
    body: str | None,
    environment_id: uuid.UUID | None,
) -> SavedApiRequest:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    saved_request = await _get_request_row(db, project_id, request_id)
    if saved_request is None:
        raise SavedApiRequestNotFoundError()

    if name is not None:
        saved_request.name = name
    if method is not None:
        saved_request.method = method
    if url is not None:
        saved_request.url = url
    if headers is not None:
        saved_request.headers = headers
    if query_params is not None:
        saved_request.query_params = query_params
    if body is not None:
        saved_request.body = body
    if environment_id is not None:
        saved_request.environment_id = environment_id

    await db.commit()
    await db.refresh(saved_request)
    return saved_request


async def delete_saved_request(
    db: AsyncSession, project_id: uuid.UUID, request_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.admin)
    saved_request = await _get_request_row(db, project_id, request_id)
    if saved_request is None:
        raise SavedApiRequestNotFoundError()

    await db.delete(saved_request)
    await db.commit()
