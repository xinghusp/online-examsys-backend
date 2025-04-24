from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload, Session  # Import Session for type hint if needed in CRUD
from typing import List, Any

from app import crud, schemas
from app.api import deps
from app.db import models
from app.crud.crud_role import role as crud_role
router = APIRouter()

@router.post("/", response_model=schemas.Role, status_code=status.HTTP_201_CREATED)
async def create_role(
    *,
    db: AsyncSession = Depends(deps.get_db),
    role_in: schemas.RoleCreate,
    current_user: models.User = Depends(deps.get_current_active_admin)
) -> Any:
    """
    Create new role.
    """
    existing_role = await crud_role.get_by_name(db, name=role_in.name)
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role with this name already exists",
        )

    # Assuming crud_role.create handles associating permission_ids if provided in role_in
    created_role_db_obj = await crud_role.create(db=db, obj_in=role_in)
    if not created_role_db_obj:
         # Handle case where CRUD op might fail silently (though it should raise)
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create role in database.")


    # --- Eager Loading Fix ---
    # Fetch the newly created role again, explicitly loading the permissions
    stmt = select(models.Role).options(selectinload(models.Role.permissions)).where(models.Role.id == created_role_db_obj.id)
    result = await db.execute(stmt)
    role_with_permissions = result.scalar_one_or_none()

    if not role_with_permissions:
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve created role with permissions.")

    return role_with_permissions


@router.get("/", response_model=List[schemas.Role])
async def read_roles(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_active_admin)
) -> Any:
    """
    Retrieve roles. Load permissions eagerly.
    """
    # TODO: Implement total count retrieval for pagination if not handled by CRUD
    # Example: total_count = await crud_role.get_count(db)

    # Using direct query with eager loading:
    stmt = select(models.Role).options(selectinload(models.Role.permissions)).offset(skip).limit(limit).order_by(models.Role.id) # Add ordering
    result = await db.execute(stmt)
    roles = result.scalars().all()

    # If your response model needs total, structure it like:
    # return {"items": roles, "total": total_count}
    # Adjust response_model accordingly (e.g., using a generic PaginatedResponse[schemas.Role])
    return roles


@router.get("/{role_id}", response_model=schemas.Role)
async def read_role(
    role_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_admin)
) -> Any:
    """
    Get a specific role by ID. Load permissions eagerly.
    """
    stmt = select(models.Role).options(selectinload(models.Role.permissions)).where(models.Role.id == role_id)
    result = await db.execute(stmt)
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


@router.put("/{role_id}", response_model=schemas.Role) # <<< --- ADDED BACK --- <<<
async def update_role(
    *,
    db: AsyncSession = Depends(deps.get_db),
    role_id: int,
    role_in: schemas.RoleUpdate,
    current_user: models.User = Depends(deps.get_current_active_admin)
) -> Any:
    """
    Update a role.
    """
    role_db_obj = await crud_role.get(db, id=role_id) # Fetch existing role first
    if not role_db_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    # Check for name conflict if name is being changed
    if role_in.name and role_in.name != role_db_obj.name:
        existing_role = await crud_role.get_by_name(db, name=role_in.name)
        if existing_role and existing_role.id != role_id:
            raise HTTPException(status_code=400, detail="Role with this name already exists.")

    # Perform the update using CRUD
    # Ensure crud_role.update handles permission_ids association correctly if they are in role_in
    updated_role_db_obj = await crud_role.update(db=db, db_obj=role_db_obj, obj_in=role_in)
    if not updated_role_db_obj:
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update role in database.")


    # --- Eager Loading Fix for Response ---
    # Fetch the updated role again, explicitly loading the permissions
    stmt = select(models.Role).options(selectinload(models.Role.permissions)).where(models.Role.id == updated_role_db_obj.id)
    result = await db.execute(stmt)
    role_with_permissions = result.scalar_one_or_none()

    if not role_with_permissions:
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve updated role with permissions.")

    return role_with_permissions


@router.delete("/{role_id}", response_model=schemas.Role) # <<< --- ADDED BACK --- <<<
async def delete_role(
    *,
    db: AsyncSession = Depends(deps.get_db),
    role_id: int,
    current_user: models.User = Depends(deps.get_current_active_admin)
) -> Any:
    """
    Delete a role.
    (Note: Consider adding checks if role is assigned to users before deletion).
    """
    role = await crud_role.get(db=db, id=role_id)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    # Optional: Check if role is assigned to any user before deleting
    # stmt = select(models.User).join(models.user_roles).where(models.user_roles.c.role_id == role_id).limit(1)
    # result = await db.execute(stmt)
    # if result.scalar_one_or_none():
    #     raise HTTPException(status_code=400, detail="Cannot delete role assigned to users. Unassign users first.")

    # --- Eager Loading before Deletion (if response_model needs it) ---
    # Fetch with permissions loaded *before* deleting, so the returned object is complete
    stmt_load = select(models.Role).options(selectinload(models.Role.permissions)).where(models.Role.id == role_id)
    result_load = await db.execute(stmt_load)
    role_to_delete_loaded = result_load.scalar_one() # Use scalar_one as we know it exists

    # Perform deletion
    deleted_role = await crud_role.remove(db=db, id=role_id)
    if not deleted_role:
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete role.")


    # Return the *loaded* object data before it was deleted
    return role_to_delete_loaded
