from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload, Session # Synchronous Session for count example
from sqlalchemy import func # For count

from typing import List, Optional

from app.db.models import Group, User # Import models
from app.schemas.group import GroupCreate, GroupUpdate # Import schemas

class CRUDGroup:
    async def get(self, db: AsyncSession, *, id: int) -> Optional[Group]:
        """Get a group by ID."""
        # Decide if users should be loaded by default. Probably not for performance.
        result = await db.execute(select(Group).filter(Group.id == id))
        return result.scalars().first()

    async def get_by_name(self, db: AsyncSession, *, name: str) -> Optional[Group]:
        """Get a group by name."""
        result = await db.execute(select(Group).filter(Group.name == name))
        return result.scalars().first()

    async def get_multi(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[Group]:
        """Get multiple groups with pagination."""
        result = await db.execute(
            select(Group)
            .offset(skip)
            .limit(limit)
            .order_by(Group.name)
        )
        # Note: This doesn't load users by default.
        return result.scalars().all()

    async def get_user_count(self, db: AsyncSession, *, group_id: int) -> int:
         """Get the number of users in a group."""
         # Use count aggregate function
         count_query = select(func.count(User.id)).join(Group.users).where(Group.id == group_id)
         result = await db.execute(count_query)
         count = result.scalar_one_or_none()
         return count if count is not None else 0


    async def create(self, db: AsyncSession, *, obj_in: GroupCreate) -> Group:
        """Create a new group and add initial users."""
        # Check if name exists
        existing = await self.get_by_name(db, name=obj_in.name)
        if existing:
            raise ValueError(f"Group with name '{obj_in.name}' already exists.")

        db_obj = Group(name=obj_in.name, description=obj_in.description)

        # Fetch and assign users
        if obj_in.user_ids:
            users_result = await db.execute(
                select(User).filter(User.id.in_(obj_in.user_ids))
            )
            db_obj.users.extend(users_result.scalars().all())

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        # Note: users relationship is likely not loaded after refresh unless specified
        return db_obj

    async def update(
        self, db: AsyncSession, *, db_obj: Group, obj_in: GroupUpdate
    ) -> Group:
        """Update a group, potentially replacing its users."""
        update_data = obj_in.model_dump(exclude_unset=True)

        if "name" in update_data and update_data["name"] != db_obj.name:
            existing = await self.get_by_name(db, name=update_data["name"])
            if existing and existing.id != db_obj.id:
                raise ValueError(f"Group name '{update_data['name']}' is already taken.")

        # Handle user updates (replace mode)
        if "user_ids" in update_data and update_data["user_ids"] is not None:
            user_ids = update_data.pop("user_ids") # Remove from update_data
            if not user_ids: # Empty list means remove all users
                db_obj.users.clear()
            else:
                users_result = await db.execute(
                    select(User).filter(User.id.in_(user_ids))
                )
                db_obj.users = users_result.scalars().all() # Replace existing

        # Update other fields
        for field, value in update_data.items():
            if field != "users": # Avoid accidental overwrite
                 setattr(db_obj, field, value)

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        # Note: users relationship is likely not loaded after refresh
        return db_obj

    async def remove(self, db: AsyncSession, *, id: int) -> Optional[Group]:
        """Delete a group by ID."""
        # Consider checking if group is used in exams before deleting
        obj = await self.get(db, id=id)
        if obj:
            await db.delete(obj)
            await db.commit()
        return obj

    # --- User Assignment to Group ---
    async def assign_users_to_group(self, db: AsyncSession, *, group: Group, user_ids: List[int]) -> Group:
        """Assigns a list of users to a group, replacing existing ones."""
        if not user_ids:
             group.users.clear()
        else:
            users_result = await db.execute(
                select(User).filter(User.id.in_(user_ids))
            )
            group.users = users_result.scalars().all() # Replace current users

        db.add(group)
        await db.commit()
        await db.refresh(group)
        # Consider refreshing users relationship if needed for response, but might be slow
        # await db.refresh(group, attribute_names=['users'])
        return group

group = CRUDGroup()