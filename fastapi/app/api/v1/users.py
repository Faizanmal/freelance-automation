from __future__ import annotations

from typing import Annotated

from app.api.dependencies import get_current_user
from app.schemas.user import UserRead
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.email_service import EmailService
from backend.application.services.user_service import UserService
from backend.infrastructure.repositories.user_repository import SQLAlchemyUserRepository
from database.core.session import get_db
from database.models.user import User
from fastapi import APIRouter, Depends, status

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
    return UserRead.model_validate(current_user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    EmailService.send_account_alert(
        current_user.email,
        "Your Signal Desk account was deleted",
        "We deleted your account and the preferences tied to it. This mailbox will not receive job alerts anymore.",
    )
    repository = SQLAlchemyUserRepository(session)
    service = UserService(repository)
    await service.delete_user(current_user)
