from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta

from app import crud, schemas # Updated import
from app.api import deps # Assuming deps.py will be created
from app.core.security import create_access_token
from app.core.config import settings

from app.crud.crud_user import user as crud_user

router = APIRouter()

@router.post("/login/access-token", response_model=schemas.Token)
async def login_access_token(
    db: AsyncSession = Depends(deps.get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
) -> schemas.Token:
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    user = await crud_user.authenticate(
        db = db, username=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    elif not await crud_user.is_active(user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id, expires_delta=access_token_expires # Use user ID as subject
    )
    return schemas.Token(access_token=access_token, token_type="bearer")