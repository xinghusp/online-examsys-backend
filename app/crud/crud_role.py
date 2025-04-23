from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional

from app.db.models import Role, Permission, User # Import models
from app.schemas.role import RoleCreate, RoleUpdate # Import schemas
from .crud_permission import permission as crud_permission # Import permission CRUD

class CRUDRole:
    async def get(self, db: AsyncSession, *, id: int) -> Optional[Role]:
        """Get a role by ID, optionally loading permissions."""
        result = await db.execute(
            select(Role).options(selectinload(Role.permissions)).filter(Role.id == id)
        )
        return result.scalars().first()

    async def get_by_name(self, db: AsyncSession, *, name: str) -> Optional[Role]:
        """Get a role by name."""
        result = await db.execute(
            select(Role).options(selectinload(Role.permissions)).filter(Role.name == name)
        )
        return result.scalars().first()

    async def get_multi(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[Role]:
        """Get multiple roles with pagination, optionally loading permissions."""
        result = await db.execute(
            select(Role)
            .options(selectinload(Role.permissions)) # Eager load permissions
            .offset(skip)
            .limit(limit)
            .order_by(Role.name)
        )
        return result.scalars().all()

    async def create(self, db: AsyncSession, *, obj_in: RoleCreate) -> Role:
        """Create a new role and assign initial permissions."""
        # Check if name exists
        existing = await self.get_by_name(db, name=obj_in.name)
        if existing:
            raise ValueError(f"Role with name '{obj_in.name}' already exists.") # Or handle differently

        db_obj = Role(name=obj_in.name, description=obj_in.description)

        # Fetch and assign permissions
        if obj_in.permission_ids:
            permissions = await db.execute(
                select(Permission).filter(Permission.id.in_(obj_in.permission_ids))
            )
            db_obj.permissions.extend(permissions.scalars().all())

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        # Reload permissions after refresh if needed, though selectinload in get() handles future fetches
        # await db.refresh(db_obj, attribute_names=['permissions'])
        return db_obj

    async def update(
        self, db: AsyncSession, *, db_obj: Role, obj_in: RoleUpdate
    ) -> Role:
        """Update a role, potentially replacing its permissions."""
        update_data = obj_in.model_dump(exclude_unset=True)

        if "name" in update_data and update_data["name"] != db_obj.name:
            existing = await self.get_by_name(db, name=update_data["name"])
            if existing and existing.id != db_obj.id:
                raise ValueError(f"Role name '{update_data['name']}' is already taken.")

        # Handle permission updates (replace mode)
        if "permission_ids" in update_data and update_data["permission_ids"] is not None:
            permission_ids = update_data.pop("permission_ids") # Remove from update_data
            if not permission_ids: # Empty list means remove all permissions
                db_obj.permissions.clear()
            else:
                permissions_result = await db.execute(
                    select(Permission).filter(Permission.id.in_(permission_ids))
                )
                db_obj.permissions = permissions_result.scalars().all() # Replace existing

        # Update other fields
        for field, value in update_data.items():
             # Ensure not to overwrite permissions list accidentally if "permission_ids" wasn't in obj_in
            if field != "permissions":
                setattr(db_obj, field, value)

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        # Ensure permissions are loaded after update for the response
        await db.refresh(db_obj, attribute_names=['permissions'])
        return db_obj

    async def remove(self, db: AsyncSession, *, id: int) -> Optional[Role]:
        """Delete a role by ID."""
        # Consider checking if role is assigned to users before deleting
        obj = await self.get(db, id=id) # get loads permissions
        if obj:
            # Prevent deleting critical default roles? (e.g., 'System Admin')
            if obj.name == "System Admin":
                 raise ValueError("Cannot delete the default System Admin role.")
            await db.delete(obj)
            await db.commit()
        return obj

    # --- Role Assignment to User ---
    async def assign_roles_to_user(self, db: AsyncSession, *, user: User, role_ids: List[int]) -> User:
        """Assigns a list of roles to a user, replacing existing ones."""
        # Fetch the roles to assign
        if not role_ids:
             user.roles.clear()
        else:
            roles_result = await db.execute(
                select(Role).filter(Role.id.in_(role_ids))
            )
            user.roles = roles_result.scalars().all() # Replace current roles

        db.add(user)
        await db.commit()
        await db.refresh(user)
        await db.refresh(user, attribute_names=['roles']) # Ensure roles are loaded for return
        return user

role = CRUDRole()