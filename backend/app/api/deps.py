"""FastAPI dependencies for authentication and authorization."""

import uuid
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.utils.security import TokenError, verify_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Decode the JWT, fetch the user from the database, and verify they are active.

    Raises:
        HTTPException 401: If the token is invalid, the user does not exist,
                           or the user's account is deactivated.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = verify_token(token)
        user_id_str: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        tenant_id_str: str | None = payload.get("tenant_id")

        if user_id_str is None or token_type != "access" or tenant_id_str is None:
            raise credentials_exception

        user_id = uuid.UUID(user_id_str)
        tenant_id = uuid.UUID(tenant_id_str)
    except (TokenError, ValueError):
        raise credentials_exception

    # Fix #4: Filter by BOTH user_id AND tenant_id for tenant isolation
    result = await db.execute(
        select(User)
        .options(selectinload(User.role))
        .where(User.id == user_id, User.tenant_id == tenant_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user


def require_role(*roles: str) -> Callable:
    """Dependency factory that restricts access to users with specific role names.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role("admin"))])

    Raises:
        HTTPException 403: If the user's role is not in the allowed list.
    """

    async def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role.name not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role.name}' does not have access to this resource",
            )
        return current_user

    return role_checker
