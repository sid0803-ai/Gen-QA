"""Routes: POST /auth/register, /auth/login, /auth/refresh, GET /auth/me."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.domains.identity import schemas, service
from app.domains.identity.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=schemas.UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: schemas.UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    try:
        return await service.register_user(db, payload.email, payload.password, payload.full_name)
    except service.EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists."
        ) from exc


@router.post("/login", response_model=schemas.Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> schemas.Token:
    try:
        user = await service.authenticate_user(db, form_data.username, form_data.password)
    except service.InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    access_token, refresh_token = service.issue_token_pair(user.id)
    return schemas.Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=schemas.Token)
async def refresh(payload: schemas.RefreshRequest, db: AsyncSession = Depends(get_db)) -> schemas.Token:
    try:
        access_token, refresh_token = await service.refresh_token_pair(db, payload.refresh_token)
    except service.InvalidRefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        ) from exc

    return schemas.Token(access_token=access_token, refresh_token=refresh_token)


@router.get("/me", response_model=schemas.UserRead)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
