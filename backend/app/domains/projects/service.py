"""Business logic that crosses domain boundaries (e.g. looking up a user by
email in the identity domain before adding them as a project member).

Pure project-scoped persistence/authorization stays in repository.py.
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.identity.service import get_user_by_email
from app.domains.projects import repository
from app.domains.projects.models import ProjectMember, ProjectRole


class UserNotFoundError(Exception):
    """No registered user exists with the given email."""


async def add_member_by_email(
    db: AsyncSession,
    project_id: uuid.UUID,
    requesting_user_id: uuid.UUID,
    email: str,
    role: ProjectRole,
) -> ProjectMember:
    # Membership/role check happens inside repository.add_member as well, but
    # we need the target user resolved (identity domain) before we can call it.
    await repository.require_membership(db, project_id, requesting_user_id, ProjectRole.admin)

    target_user = await get_user_by_email(db, email)
    if target_user is None:
        raise UserNotFoundError()

    return await repository.add_member(db, project_id, requesting_user_id, target_user, role)
