# ... imports ...
from typing import AsyncGenerator

from fastapi import HTTPException
from fastapi.params import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from app import crud
from app.core import security
from app.core.config import settings
from app.db.database import AsyncSessionFactory
from app.db.models import User
from app.crud.crud_user import user as crud_user

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get an async database session.
    """
    async with AsyncSessionFactory() as session:
        yield session

async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(reusable_oauth2)
) -> User:
    """
    Dependency to get the current user from the JWT token, including roles.
    Raises HTTPException if token is invalid or user not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token_data = security.decode_token(token)
    if token_data is None or token_data.sub is None:
        raise credentials_exception

    try:
        user_id = int(token_data.sub)
    except ValueError:
        raise credentials_exception

    # Use selectinload to eagerly load the roles relationship
    query = select(User).options(selectinload(User.roles)).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalars().first()

    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency to get the current active user.
    Raises HTTPException if the user is inactive.
    """
    if not await crud_user.is_active(current_user):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user

# Dependency for checking admin privileges
async def get_current_active_admin(
   current_user: User = Depends(get_current_active_user),
) -> User:
   """
   Dependency to ensure the current user is active and has admin privileges.
   Requires the 'roles' relationship to be loaded (handled by get_current_user).
   """
   # Check if user has 'System Admin' role (adjust role name if different)
   is_admin = any(role.name == 'System Admin' for role in current_user.roles)
   if not is_admin:
       # You might want to log this attempt
       print(f"Permission denied for user {current_user.username}. Roles: {[r.name for r in current_user.roles]}") # Debug/Log
       raise HTTPException(
           status_code=status.HTTP_403_FORBIDDEN,
           detail="The user doesn't have enough privileges"
       )
   return current_user