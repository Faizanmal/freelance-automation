from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from app.core.security.jwt import create_access_token
from app.core.security.rate_limit import auth_rate_limiter, client_ip
from database.core.session import get_db
from database.models.preference import UserPreferences
from backend.infrastructure.repositories.user_repository import SQLAlchemyUserRepository
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserRead
from backend.application.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db),
) -> Token:
    auth_rate_limiter.check(f"login:{client_ip(request)}", limit=20, window_seconds=60)
    repository = SQLAlchemyUserRepository(session)
    service = UserService(repository)
    user = await service.authenticate(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    expires_delta = timedelta(minutes=get_settings().access_token_expire_minutes)
    access_token = create_access_token(str(user.id), expires_delta=expires_delta)
    return Token(
        access_token=access_token,
        expires_at=datetime.utcnow() + expires_delta,
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    user_create: UserCreate,
    session: AsyncSession = Depends(get_db),
) -> UserRead:
    auth_rate_limiter.check(f"register:{client_ip(request)}", limit=10, window_seconds=3600)
    repository = SQLAlchemyUserRepository(session)
    existing = await repository.get_by_email(user_create.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    service = UserService(repository)
    user = await service.create_user(
        email=user_create.email,
        password=user_create.password,
        full_name=user_create.full_name,
    )
    prefs = UserPreferences(
        user_id=user.id,
        keywords=["python", "fastapi", "react", "typescript"],
        exclude_keywords=[],
        sources=[],
        notification_channels=["email"],
        match_threshold=0.35,
        digest_mode=False,
        alert_email=user.email,
    )
    session.add(prefs)
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)
