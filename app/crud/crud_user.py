from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import Any, Dict, Optional, Union, List, Tuple

from app.core import security
from app.core.security import get_password_hash, verify_password
from app.crud.base import CRUDBase
from app.db import models
from app.db.models import User # Import the User model correctly
from app.db.models.user import UserStatus
from app.schemas.user import UserCreate, UserUpdate  # Import Pydantic schemas

class CRUDUser(CRUDBase[models.User, UserCreate, UserUpdate]):
    async def get(self, db: AsyncSession, *, id: int) -> Optional[User]:
        """Get a user by ID."""
        result = await db.execute(select(User).filter(User.id == id))
        return result.scalars().first()

    async def get_by_username(self, db: AsyncSession, *, username: str) -> Optional[User]:
        """Get a user by username."""
        result = await db.execute(select(User).filter(User.username == username))
        return result.scalars().first()

    async def get_by_id_number(self, db: AsyncSession, *, id_number: str) -> Optional[User]:
        """Get a user by ID number."""
        if not id_number: # Avoid querying with empty string
             return None
        result = await db.execute(select(User).filter(User.id_number == id_number))
        return result.scalars().first()

    async def get_multi(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[User]:
        """Get multiple users with pagination."""
        result = await db.execute(
            select(User).offset(skip).limit(limit).order_by(User.id)
        )
        return result.scalars().all()

    async def create(self, db: AsyncSession, *, obj_in: UserCreate) -> User:
        """Create a new user."""
        hashed_password = get_password_hash(obj_in.password)
        # Create a dictionary excluding the plain password
        db_obj_data = obj_in.model_dump(exclude={"password"})
        db_obj_data["password_hash"] = hashed_password # Add the hashed password
        db_obj = User(**db_obj_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def create_with_roles(self, db: AsyncSession, *, obj_in: UserCreate, roles: List[models.Role]) -> models.User:
        db_obj_data = obj_in.model_dump(exclude={"password", "role_ids"})
        db_obj_data["password_hash"] = get_password_hash(obj_in.password)
        db_obj = self.model(**db_obj_data)
        db_obj.roles = roles
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        # Optional: Eager load roles for the returned object if needed immediately after create
        # stmt = select(models.User).options(selectinload(models.User.roles)).where(models.User.id == db_obj.id)
        # result = await db.execute(stmt)
        # return result.scalar_one()
        return db_obj

    async def update(
        self, db: AsyncSession, *, db_obj: User, obj_in: Union[UserUpdate, Dict[str, Any]]
    ) -> User:
        """Update an existing user."""
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            # Use exclude_unset=True to only update fields that were actually passed
            update_data = obj_in.model_dump(exclude_unset=True)

        # Hash password if it's being updated
        if "password" in update_data and update_data["password"]:
            hashed_password = get_password_hash(update_data["password"])
            del update_data["password"] # Remove plain password
            update_data["password_hash"] = hashed_password # Add hashed password

        # Update model fields
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update_with_roles(
        self,
        db: AsyncSession,
        *,
        db_obj: models.User,
        obj_in: Union[UserUpdate, Dict[str, Any]],
        roles: Optional[List[models.Role]] # Pass Role objects, None means don't change roles
    ) -> models.User:
        # Prepare update data for scalar fields
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            # Exclude role_ids as we handle roles separately
            update_data = obj_in.model_dump(exclude_unset=True, exclude={"role_ids"})

        # Handle password update specifically before calling super().update
        if update_data.get("password"):
            hashed_password = get_password_hash(update_data["password"])
            update_data["password_hash"] = hashed_password # Add hashed password
            del update_data["password"] # Remove plain password
        elif "password" in update_data:
             # Explicitly remove password if passed as None or empty string
             # to prevent it being passed to super().update
             del update_data["password"]

        # Call the working super().update for scalar fields
        # Pass only the prepared update_data dictionary
        updated_db_obj = await super().update(db, db_obj=db_obj, obj_in=update_data)

        # Update roles relationship if roles list is provided (not None)
        if roles is not None:
            await db.refresh(updated_db_obj, ["roles"])  # Explicitly load roles first
            if roles is not None:
                updated_db_obj.roles = roles  # Now safe to assign

        db.add(updated_db_obj) # Add to session again (might be redundant depending on super().update)
        await db.commit()
        await db.refresh(updated_db_obj)
        # Optional: Eager load roles for the returned object
        # await db.refresh(updated_db_obj, attribute_names=['roles'])
        return updated_db_obj


    async def authenticate(
        self, db: AsyncSession, *, username: str, password: str
    ) -> Optional[User]:
        """Authenticate a user by username and password."""
        user = await self.get_by_username(db, username=username)
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    async def is_active(self, user: User) -> bool:
        """Check if a user is active."""
        return user.status == "active" # Assuming 'active' is the enum value or string

    async def remove(self, db: AsyncSession, *, id: int) -> Optional[User]:
        """Delete a user by ID."""
        # Consider adding checks here: e.g., cannot delete if user has exam records.
        # This logic might be better suited in the API endpoint or a service layer.
        obj = await self.get(db, id=id)
        if obj:
            await db.delete(obj)
            await db.commit()
        return obj # Return the deleted object or None


# Instantiate the CRUD object for easy import
user = CRUDUser(models.User)