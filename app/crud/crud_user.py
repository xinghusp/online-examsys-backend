from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import Any, Dict, Optional, Union, List, Tuple

from app.core import security
from app.core.security import get_password_hash, verify_password
from app.db import models
from app.db.models import User # Import the User model correctly
from app.schemas.user import UserCreate, UserUpdate, UserImportRecord, UserStatus  # Import Pydantic schemas

class CRUDUser:
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

    async def bulk_create(
            self, db: AsyncSession, *, users_in: List[UserImportRecord]
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Creates multiple users in bulk.

        Args:
            db: The database session.
            users_in: A list of UserImportRecord schema objects.

        Returns:
            A tuple containing:
                - success_count: Number of users successfully created.
                - errors: A list of dictionaries detailing failed creations (e.g., {'username': '...', 'error': '...'}).
        """
        success_count = 0
        errors: List[Dict[str, Any]] = []
        created_users = []  # Store successfully created user objects temporarily

        # Optional: Pre-fetch existing roles/groups if assigning during import
        all_role_names = set(r_name for u in users_in if u.role_names for r_name in u.role_names)
        all_group_names = set(g_name for u in users_in if u.group_names for g_name in u.group_names)
        roles_map: Dict[str, models.Role] = {}
        groups_map: Dict[str, models.Group] = {}

        if all_role_names:
            roles_db = await db.execute(select(models.Role).filter(models.Role.name.in_(all_role_names)))
            roles_map = {role.name: role for role in roles_db.scalars().all()}
        if all_group_names:
            groups_db = await db.execute(select(models.Group).filter(models.Group.name.in_(all_group_names)))
            groups_map = {group.name: group for group in groups_db.scalars().all()}

        for idx, user_data in enumerate(users_in):
            hashed_password = security.get_password_hash(user_data.password)
            db_obj = models.User(
                username=user_data.username,
                id_number=user_data.id_number,
                full_name=user_data.fullname,
                password_hash=hashed_password,
                status=UserStatus.active
            )

            # Prepare roles and groups if provided
            user_roles = []
            user_groups = []
            role_errors = []
            group_errors = []

            if user_data.role_names:
                for r_name in user_data.role_names:
                    role = roles_map.get(r_name)
                    if role:
                        user_roles.append(role)
                    else:
                        role_errors.append(f"Role '{r_name}' not found")
            if user_data.group_names:
                for g_name in user_data.group_names:
                    group = groups_map.get(g_name)
                    if group:
                        user_groups.append(group)
                    else:
                        group_errors.append(f"Group '{g_name}' not found")

            if role_errors or group_errors:
                errors.append({
                    "row": idx + 2,  # Assuming header is row 1, data starts row 2
                    "username": user_data.username,
                    "error": ", ".join(role_errors + group_errors)
                })
                continue  # Skip adding this user

            # Add roles/groups to the user object before adding to session
            db_obj.roles = user_roles
            db_obj.groups = user_groups

            db.add(db_obj)
            try:
                # Flush to catch potential IntegrityErrors (like duplicate username/email) early within the loop
                await db.flush([db_obj])
                created_users.append(db_obj)  # Add to list for potential commit later
                success_count += 1
            except IntegrityError as e:
                await db.rollback()  # Rollback the failed flush for this user
                error_detail = "Username or email already exists."
                # You could try to parse e.orig for more specific details, but it's DB-dependent
                errors.append({
                    "row": idx + 2,
                    "username": user_data.username,
                    "error": error_detail
                })
            except Exception as e:
                await db.rollback()  # Rollback on other unexpected errors
                errors.append({
                    "row": idx + 2,
                    "username": user_data.username,
                    "error": f"An unexpected error occurred: {e}"
                })

        # If we successfully flushed users, commit them all at the end
        if created_users:
            try:
                await db.commit()
                # Optional: Refresh created users if needed elsewhere, but usually not necessary after bulk create
                # for user in created_users:
                #     await db.refresh(user)
            except Exception as e:
                # This commit might fail if there was a deferred constraint or other issue.
                await db.rollback()
                # Need to adjust success_count and errors if the final commit fails
                # For simplicity now, assume commit succeeds if flush worked. More robust handling might be needed.
                print(f"CRITICAL: Final commit failed after successful flushes in bulk user create: {e}")
                # Mark all 'created_users' as failed in this scenario?
                final_commit_error = {"row": "N/A", "username": "Multiple Users", "error": f"Final commit failed: {e}"}
                return 0, errors + [final_commit_error]  # Return 0 success and add a general error

        return success_count, errors

# Instantiate the CRUD object for easy import
user = CRUDUser()