from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional

from app.db.models import Permission
from app.schemas.permission import PermissionCreate, PermissionUpdate # Assuming schemas are defined

class CRUDPermission:
    async def get(self, db: AsyncSession, *, id: int) -> Optional[Permission]:
        """Get a permission by ID."""
        result = await db.execute(select(Permission).filter(Permission.id == id))
        return result.scalars().first()

    async def get_by_code(self, db: AsyncSession, *, code: str) -> Optional[Permission]:
        """Get a permission by code."""
        result = await db.execute(select(Permission).filter(Permission.code == code))
        return result.scalars().first()

    async def get_multi(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 1000 # Often fewer permissions
    ) -> List[Permission]:
        """Get multiple permissions."""
        result = await db.execute(
            select(Permission).offset(skip).limit(limit).order_by(Permission.code)
        )
        return result.scalars().all()

    async def create(self, db: AsyncSession, *, obj_in: PermissionCreate) -> Permission:
        """Create a new permission."""
        # Ensure code doesn't already exist
        existing = await self.get_by_code(db, code=obj_in.code)
        if existing:
            # Or raise an exception, depending on desired behavior
            return existing
        db_obj = Permission(**obj_in.model_dump())
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self, db: AsyncSession, *, db_obj: Permission, obj_in: PermissionUpdate
    ) -> Permission:
        """Update a permission (likely just description)."""
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    # Delete might be restricted in production, maybe disable/hide instead
    async def remove(self, db: AsyncSession, *, id: int) -> Optional[Permission]:
        """Delete a permission by ID."""
        obj = await self.get(db, id=id)
        if obj:
            # Check if permission is used by any roles before deleting?
            await db.delete(obj)
            await db.commit()
        return obj

permission = CRUDPermission()