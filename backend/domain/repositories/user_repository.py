from __future__ import annotations

from database.models.user import User


class IUserRepository:
    async def get_by_email(self, email: str) -> User | None:
        raise NotImplementedError

    async def get_by_id(self, user_id: str) -> User | None:
        raise NotImplementedError

    async def create(self, user: User) -> User:
        raise NotImplementedError
