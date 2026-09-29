from __future__ import annotations

from uuid import uuid4

from passlib.context import CryptContext

from backend.domain.repositories.user_repository import IUserRepository
from database.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserService:
    def __init__(self, user_repository: IUserRepository) -> None:
        self.user_repository = user_repository

    async def create_user(self, email: str, password: str, full_name: str | None = None) -> User:
        hashed_password = self.hash_password(password)
        user = User(
            id=str(uuid4()),
            email=email,
            full_name=full_name,
            hashed_password=hashed_password,
        )
        return await self.user_repository.create(user)

    async def authenticate(self, email: str, password: str) -> User | None:
        user = await self.user_repository.get_by_email(email)
        if not user or not self.verify_password(password, user.hashed_password):
            return None
        if not user.is_active:
            return None
        return user

    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        return pwd_context.verify(password, hashed_password)

    async def update_password(self, email: str, new_password: str) -> bool:
        user = await self.user_repository.get_by_email(email)
        if not user:
            return False
        user.hashed_password = self.hash_password(new_password)
        await self.user_repository.update(user)
        return True

    async def verify_email(self, email: str) -> bool:
        user = await self.user_repository.get_by_email(email)
        if not user:
            return False
        user.is_verified = True
        await self.user_repository.update(user)
        return True

    async def delete_user(self, user: User) -> None:
        await self.user_repository.delete(user)
