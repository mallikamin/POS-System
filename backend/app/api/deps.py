"""FastAPI dependencies for authentication and authorization."""

import uuid
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.utils.security import TokenError, verify_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    request: Request,
    bearer_token: Optional[str] = Depends(oauth2_scheme),
    query_token: Optional[str] = Query(None, alias="token", include_in_schema=False),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Decode the JWT, fetch the user from the database, and verify they are active.

    Accepts the token from either:
      1. Authorization: Bearer <token>  header  (standard)
      2. ?token=<token>  query parameter  (fallback for file downloads)

    Raises:
        HTTPException 401: If the token is invalid, the user does not exist,
                           or the user's account is deactivated.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Pick whichever token source is available
    token = bearer_token or query_token
    if not token:
        raise credentials_exception

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

    # Filter by BOTH user_id AND tenant_id for tenant isolation
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


def require_permission(*permissions: str) -> Callable:
    """Dependency factory that restricts access to users whose role has ALL
    specified permission codes.

    Usage:
        @router.post("/apply", dependencies=[Depends(require_permission("discount.apply"))])
    """

    async def permission_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        user_perms = {p.code for p in current_user.role.permissions}
        missing = set(permissions) - user_perms
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission(s): {', '.join(sorted(missing))}",
            )
        return current_user

    return permission_checker
