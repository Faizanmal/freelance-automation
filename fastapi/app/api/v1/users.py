from __future__ import annotations

from app.api.dependencies import get_current_user
from app.schemas.user import UserRead

from database.models.user import User
from database.core.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from backend.application.services.user_service import UserService
from backend.infrastructure.repositories.user_repository import SQLAlchemyUserRepository
from fastapi import APIRouter, Depends, status

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def read_current_user(current_user: User = Depends(get_current_user)) -> UserRead:  # noqa: B008
    return UserRead.model_validate(current_user)

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> None:
    repository = SQLAlchemyUserRepository(session)
    service = UserService(repository)
    await service.delete_user(current_user)
