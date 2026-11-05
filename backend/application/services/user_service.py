from __future__ import annotations

import secrets
from uuid import uuid4

import bcrypt

from backend.domain.repositories.user_repository import IUserRepository
from database.models.user import User

# bcrypt rejects secrets longer than 72 bytes; passlib+bcrypt>=4.1 also breaks
# on backend detection. Hash with bcrypt directly.
_BCRYPT_MAX_BYTES = 72


def _password_bytes(password: str) -> bytes:
    raw = password.encode("utf-8")
    if len(raw) > _BCRYPT_MAX_BYTES:
        return raw[:_BCRYPT_MAX_BYTES]
    return raw


class UserService:
    def __init__(self, user_repository: IUserRepository) -> None:
        self.user_repository = user_repository

    async def create_user(
        self, email: str, password: str, full_name: str | None = None
    ) -> User:
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

    async def get_by_google_id(self, google_id: str) -> User | None:
        return await self.user_repository.get_by_google_id(google_id)

    async def authenticate_or_create_google_user(
        self,
        google_id: str,
        email: str,
        full_name: str | None = None,
    ) -> tuple[User, bool]:
        """
        Authenticate an existing user by Google ID or email, or create a new user.
        Returns (user, is_new_user).
        """
        normalized_email = email.strip().lower()

        # 1. Lookup by google_id
        user = await self.user_repository.get_by_google_id(google_id)
        if user:
            updated = False
            if not user.is_verified:
                user.is_verified = True
                updated = True
            if not user.full_name and full_name:
                user.full_name = full_name
                updated = True
            if updated:
                await self.user_repository.update(user)
            return user, False

        # 2. Lookup by email to link Google account to existing user
        user = await self.user_repository.get_by_email(normalized_email)
        if user:
            user.google_id = google_id
            if not user.is_verified:
                user.is_verified = True
            if not user.full_name and full_name:
                user.full_name = full_name
            await self.user_repository.update(user)
            return user, False

        # 3. Create a brand new user
        random_password = secrets.token_urlsafe(32)
        hashed_password = self.hash_password(random_password)
        new_user = User(
            id=str(uuid4()),
            email=normalized_email,
            full_name=full_name,
            hashed_password=hashed_password,
            google_id=google_id,
            is_verified=True,
            is_active=True,
        )
        created_user = await self.user_repository.create(new_user)
        return created_user, True

    async def get_by_github_id(self, github_id: str) -> User | None:
        return await self.user_repository.get_by_github_id(github_id)

    async def authenticate_or_create_github_user(
        self,
        github_id: str,
        email: str,
        full_name: str | None = None,
    ) -> tuple[User, bool]:
        """
        Authenticate an existing user by GitHub ID or email, or create a new user.
        Returns (user, is_new_user).
        """
        normalized_email = email.strip().lower()

        # 1. Lookup by github_id
        user = await self.user_repository.get_by_github_id(github_id)
        if user:
            updated = False
            if not user.is_verified:
                user.is_verified = True
                updated = True
            if not user.full_name and full_name:
                user.full_name = full_name
                updated = True
            if updated:
                await self.user_repository.update(user)
            return user, False

        # 2. Lookup by email to link GitHub account to existing user
        user = await self.user_repository.get_by_email(normalized_email)
        if user:
            user.github_id = github_id
            if not user.is_verified:
                user.is_verified = True
            if not user.full_name and full_name:
                user.full_name = full_name
            await self.user_repository.update(user)
            return user, False

        # 3. Create a brand new user
        random_password = secrets.token_urlsafe(32)
        hashed_password = self.hash_password(random_password)
        new_user = User(
            id=str(uuid4()),
            email=normalized_email,
            full_name=full_name,
            hashed_password=hashed_password,
            github_id=github_id,
            is_verified=True,
            is_active=True,
        )
        created_user = await self.user_repository.create(new_user)
        return created_user, True

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode(
            "utf-8"
        )

    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        try:
            return bcrypt.checkpw(
                _password_bytes(password), hashed_password.encode("utf-8")
            )
        except (ValueError, TypeError):
            return False

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
