"""Business logic for registration, authentication, and token issuance."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.domains.identity.models import User


class EmailAlreadyRegisteredError(Exception):
    """Raised when attempting to register an email that already exists."""


class InvalidCredentialsError(Exception):
    """Raised when login credentials don't match a user."""


class InvalidRefreshTokenError(Exception):
    """Raised when a refresh token is invalid, expired, or not a refresh token."""


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str | uuid.UUID) -> User | None:
    try:
        uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
    except ValueError:
        return None
    result = await db.execute(select(User).where(User.id == uid))
    return result.scalar_one_or_none()


async def register_user(db: AsyncSession, email: str, password: str, full_name: str) -> User:
    existing = await get_user_by_email(db, email)
    if existing is not None:
        raise EmailAlreadyRegisteredError()

    user = User(email=email, full_name=full_name, hashed_password=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(db, email)
    if user is None or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError()
    return user


def issue_token_pair(user_id: uuid.UUID) -> tuple[str, str]:
    subject = str(user_id)
    return create_access_token(subject), create_refresh_token(subject)


async def refresh_token_pair(db: AsyncSession, refresh_token: str) -> tuple[str, str]:
    try:
        payload = decode_token(refresh_token)
    except InvalidTokenError as exc:
        raise InvalidRefreshTokenError() from exc

    if payload.get("type") != "refresh":
        raise InvalidRefreshTokenError()

    user_id = payload.get("sub")
    if not user_id:
        raise InvalidRefreshTokenError()

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise InvalidRefreshTokenError()

    return issue_token_pair(user.id)
