from __future__ import annotations

import jwt
from app.core.security.jwt import decode_access_token
from app.core.security.blocklist import blocklist
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.infrastructure.repositories.user_repository import SQLAlchemyUserRepository
from database.core.session import get_db
from database.models.user import User
from fastapi import Depends, HTTPException, Security, status

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),  # noqa: B008
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> User:
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token") from exc

    jti = payload.get("jti")
    if jti and await blocklist.is_blocked(jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")

    repository = SQLAlchemyUserRepository(session)
    user = await repository.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return user


async def rate_limit_api(user: User = Depends(get_current_user)) -> User:
    from app.core.security.rate_limit import api_rate_limiter
    from backend.application.services.billing import is_pro

    limit = 600 if is_pro(user) else 100
    await api_rate_limiter.check(f"api:{user.id}", limit=limit, window_seconds=3600)
    return user
