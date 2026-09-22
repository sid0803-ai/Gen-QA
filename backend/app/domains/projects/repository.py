"""Data-access layer for the projects domain.

CRITICAL ISOLATION RULE: every function here that reads or writes data scoped
to a single project takes `project_id` and the *requesting* `user_id` as
mandatory parameters, and enforces membership (and, where relevant, a minimum
role) by joining/filtering through ProjectMember before touching Project
data. There must be no function added to this module that fetches or
mutates project-scoped rows without going through `require_membership`
first. This is what guarantees user A can never see or touch user B's
project, no matter which future domain (requirements, test cases, etc.)
ends up calling into project-scoped data.
"""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.identity.models import User
from app.domains.projects.models import ROLE_RANK, Project, ProjectMember, ProjectRole


class NotAMemberError(Exception):
    """Requesting user is not a member of the project (or it doesn't exist) -> 404."""


class InsufficientRoleError(Exception):
    """Requesting user is a member but lacks the required role -> 403."""


class TargetNotAMemberError(Exception):
    """The target user of a membership operation is not a project member -> 404."""


class AlreadyMemberError(Exception):
    """The target user is already a member of the project -> 409."""


class LastAdminError(Exception):
    """The operation would leave the project with zero admins -> 409."""


async def get_membership(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID
) -> ProjectMember | None:
    stmt = select(ProjectMember).where(
        ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def require_membership(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    min_role: ProjectRole = ProjectRole.viewer,
) -> ProjectMember:
    """Raise NotAMemberError / InsufficientRoleError, or return the membership."""
    membership = await get_membership(db, project_id, user_id)
    if membership is None:
        raise NotAMemberError()
    if ROLE_RANK[membership.role] < ROLE_RANK[min_role]:
        raise InsufficientRoleError()
    return membership


async def _count_admins(db: AsyncSession, project_id: uuid.UUID) -> int:
    stmt = (
        select(func.count())
        .select_from(ProjectMember)
        .where(ProjectMember.project_id == project_id, ProjectMember.role == ProjectRole.admin)
    )
    result = await db.execute(stmt)
    return int(result.scalar_one())


async def list_projects_for_user(
    db: AsyncSession, user_id: uuid.UUID
) -> list[tuple[Project, ProjectRole]]:
    """List every project the given user is a member of, with their role in each.

    Inherently isolated: the join on ProjectMember.user_id == user_id means
    a project can only appear here if the requesting user is a member of it.
    """
    stmt = (
        select(Project, ProjectMember.role)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == user_id)
        .order_by(Project.created_at.desc())
    )
    result = await db.execute(stmt)
    return [(row[0], row[1]) for row in result.all()]


async def create_project(
    db: AsyncSession, name: str, description: str | None, owner_user_id: uuid.UUID
) -> Project:
    project = Project(name=name, description=description)
    db.add(project)
    await db.flush()

    membership = ProjectMember(
        project_id=project.id, user_id=owner_user_id, role=ProjectRole.admin
    )
    db.add(membership)

    await db.commit()
    await db.refresh(project)
    return project


async def get_project_detail(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> Project:
    await require_membership(db, project_id, user_id, ProjectRole.viewer)
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if project is None:
        # Membership existed but project vanished concurrently: treat as not found.
        raise NotAMemberError()
    return project


async def update_project(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str | None = None,
    description: str | None = None,
) -> Project:
    await require_membership(db, project_id, user_id, ProjectRole.admin)
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if project is None:
        raise NotAMemberError()

    if name is not None:
        project.name = name
    if description is not None:
        project.description = description

    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> None:
    await require_membership(db, project_id, user_id, ProjectRole.admin)
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if project is None:
        raise NotAMemberError()

    await db.delete(project)
    await db.commit()


async def list_members(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID
) -> list[ProjectMember]:
    await require_membership(db, project_id, user_id, ProjectRole.viewer)
    stmt = (
        select(ProjectMember)
        .options(selectinload(ProjectMember.user))
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def add_member(
    db: AsyncSession,
    project_id: uuid.UUID,
    requesting_user_id: uuid.UUID,
    target_user: User,
    role: ProjectRole,
) -> ProjectMember:
    await require_membership(db, project_id, requesting_user_id, ProjectRole.admin)

    existing = await get_membership(db, project_id, target_user.id)
    if existing is not None:
        raise AlreadyMemberError()

    membership = ProjectMember(project_id=project_id, user_id=target_user.id, role=role)
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    membership.user = target_user
    return membership


async def update_member_role(
    db: AsyncSession,
    project_id: uuid.UUID,
    requesting_user_id: uuid.UUID,
    target_user_id: uuid.UUID,
    new_role: ProjectRole,
) -> ProjectMember:
    await require_membership(db, project_id, requesting_user_id, ProjectRole.admin)

    stmt = (
        select(ProjectMember)
        .options(selectinload(ProjectMember.user))
        .where(ProjectMember.project_id == project_id, ProjectMember.user_id == target_user_id)
    )
    result = await db.execute(stmt)
    target = result.scalar_one_or_none()
    if target is None:
        raise TargetNotAMemberError()

    if target.role == ProjectRole.admin and new_role != ProjectRole.admin:
        admin_count = await _count_admins(db, project_id)
        if admin_count <= 1:
            raise LastAdminError()

    target.role = new_role
    await db.commit()
    await db.refresh(target, attribute_names=["role"])
    return target


async def remove_member(
    db: AsyncSession,
    project_id: uuid.UUID,
    requesting_user_id: uuid.UUID,
    target_user_id: uuid.UUID,
) -> None:
    await require_membership(db, project_id, requesting_user_id, ProjectRole.admin)

    target = await get_membership(db, project_id, target_user_id)
    if target is None:
        raise TargetNotAMemberError()

    if target.role == ProjectRole.admin:
        admin_count = await _count_admins(db, project_id)
        if admin_count <= 1:
            raise LastAdminError()

    await db.delete(target)
    await db.commit()
