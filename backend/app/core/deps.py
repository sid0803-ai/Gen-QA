"""Shared FastAPI dependencies: current-user auth, and a project-role gate
that future domains (requirements, test cases, executions, ...) can reuse
by simply declaring `Depends(require_project_role(ProjectRole.member))` on
any route that has a `project_id` path parameter.
"""
import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import InvalidTokenError, decode_token
from app.domains.identity.models import User
from app.domains.identity.service import get_user_by_id
from app.domains.projects import repository as project_repository
from app.domains.projects.models import ProjectMember, ProjectRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
    except InvalidTokenError as exc:
        raise credentials_exception from exc

    if payload.get("type") != "access":
        raise credentials_exception

    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exception

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise credentials_exception

    return user


def require_project_role(
    min_role: ProjectRole,
) -> Callable[..., Coroutine[Any, Any, ProjectMember]]:
    """Dependency factory: requires the caller to be a member of `project_id`
    (a path parameter on the route) with at least `min_role`.

    Raises 404 if the caller isn't a member (never 403, to avoid leaking
    project existence), or 403 if they are a member but under-privileged.
    """

    async def dependency(
        project_id: uuid.UUID,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> ProjectMember:
        try:
            return await project_repository.require_membership(
                db, project_id, current_user.id, min_role
            )
        except project_repository.NotAMemberError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found."
            ) from exc
        except project_repository.InsufficientRoleError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires '{min_role.value}' role or higher on this project.",
            ) from exc

    return dependency
