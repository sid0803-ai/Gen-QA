"""Data-access layer for the environments domain (project-scoped).

Same isolation rule as every other domain: every function takes `project_id`
+ the requesting user's id and enforces membership (and a minimum role,
where relevant) via `project_repository.require_membership` before touching
any row. Environment rows are additionally always filtered by `project_id`,
so an environment id from another project can never be reached even if
guessed.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.environments.models import Environment
from app.domains.projects import repository as project_repository
from app.domains.projects.models import ProjectRole


class EnvironmentNotFoundError(Exception):
    """Environment doesn't exist in this project (or the project doesn't) -> 404."""


async def _get_environment_row(
    db: AsyncSession, project_id: uuid.UUID, environment_id: uuid.UUID
) -> Environment | None:
    stmt = select(Environment).where(
        Environment.id == environment_id, Environment.project_id == project_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_environment(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    name: str,
    base_url: str,
    variables: dict[str, str] | None,
) -> Environment:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    environment = Environment(
        project_id=project_id,
        name=name,
        base_url=base_url,
        variables=variables or {},
        created_by=user_id,
    )
    db.add(environment)
    await db.commit()
    await db.refresh(environment)
    return environment


async def list_environments(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID
) -> list[Environment]:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    stmt = (
        select(Environment)
        .where(Environment.project_id == project_id)
        .order_by(Environment.created_at)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_environment(
    db: AsyncSession, project_id: uuid.UUID, environment_id: uuid.UUID, user_id: uuid.UUID
) -> Environment:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    environment = await _get_environment_row(db, project_id, environment_id)
    if environment is None:
        raise EnvironmentNotFoundError()
    return environment


async def update_environment(
    db: AsyncSession,
    project_id: uuid.UUID,
    environment_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    name: str | None,
    base_url: str | None,
    variables: dict[str, str] | None,
) -> Environment:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    environment = await _get_environment_row(db, project_id, environment_id)
    if environment is None:
        raise EnvironmentNotFoundError()

    if name is not None:
        environment.name = name
    if base_url is not None:
        environment.base_url = base_url
    if variables is not None:
        environment.variables = variables

    await db.commit()
    await db.refresh(environment)
    return environment


async def delete_environment(
    db: AsyncSession, project_id: uuid.UUID, environment_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.admin)
    environment = await _get_environment_row(db, project_id, environment_id)
    if environment is None:
        raise EnvironmentNotFoundError()

    await db.delete(environment)
    await db.commit()
