from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.repositories.user_repository import IUserRepository
from database.models.application import JobApplication
from database.models.lead_action import UserLeadAction
from database.models.notification import NotificationDelivery, NotificationRecord
from database.models.preference import UserPreferences
from database.models.user import User


class SQLAlchemyUserRepository(IUserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: str) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update(self, user: User) -> User:
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        # Clear user-owned rows in one transaction before removing the user.
        # Explicit deletes avoid SQLAlchemy nullifying NOT NULL FKs when related
        # rows are already in the session (even with DB ON DELETE CASCADE).
        notification_ids = (
            (
                await self.session.execute(
                    select(NotificationRecord.id).where(
                        NotificationRecord.user_id == user.id
                    )
                )
            )
            .scalars()
            .all()
        )
        if notification_ids:
            await self.session.execute(
                delete(NotificationDelivery).where(
                    NotificationDelivery.notification_id.in_(notification_ids)
                )
            )
        await self.session.execute(
            delete(NotificationRecord).where(NotificationRecord.user_id == user.id)
        )
        await self.session.execute(
            delete(UserLeadAction).where(UserLeadAction.user_id == user.id)
        )
        await self.session.execute(
            delete(JobApplication).where(JobApplication.user_id == user.id)
        )
        await self.session.execute(
            delete(UserPreferences).where(UserPreferences.user_id == user.id)
        )
        await self.session.delete(user)
        await self.session.commit()
