from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Any

from app import crud, schemas
from app.api import deps
from app.db import models

from app.crud.crud_permission import permission as crud_permission

router = APIRouter()

# Endpoint to list permissions (usually sufficient)
@router.get("/", response_model=List[schemas.Permission])
async def read_permissions(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1), # High limit, usually not many permissions
    current_user: models.User = Depends(deps.get_current_active_admin) # Require admin
) -> Any:
    """
    Retrieve all permissions. Requires admin privileges.
    """
    permissions = await crud_permission.get_multi(db, skip=skip, limit=limit)
    return permissions

# Optional: Endpoint to create a permission (maybe restrict this in production)
@router.post("/", response_model=schemas.Permission, status_code=status.HTTP_201_CREATED)
async def create_permission(
    *,
    db: AsyncSession = Depends(deps.get_db),
    permission_in: schemas.PermissionCreate,
    current_user: models.User = Depends(deps.get_current_active_admin) # Require admin
) -> Any:
    """
    Create a new permission. Requires admin privileges.
    (Use with caution, consider if dynamic permission creation is needed).
    """
    existing_permission = await crud_permission.get_by_code(db, code=permission_in.code)
    if existing_permission:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Permission code '{permission_in.code}' already exists.",
        )
    permission = await crud_permission.create(db=db, obj_in=permission_in)
    return permission

# Optional: Endpoint to get a single permission
@router.get("/{permission_id}", response_model=schemas.Permission)
async def read_permission(
    permission_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_admin) # Require admin
) -> Any:
    """
    Get a specific permission by ID. Requires admin privileges.
    """
    permission = await crud_permission.get(db, id=permission_id)
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found",
        )
    return permission

# Optional: Endpoint to update a permission (likely just description)
@router.put("/{permission_id}", response_model=schemas.Permission)
async def update_permission(
    *,
    db: AsyncSession = Depends(deps.get_db),
    permission_id: int,
    permission_in: schemas.PermissionUpdate,
    current_user: models.User = Depends(deps.get_current_active_admin) # Require admin
) -> Any:
    """
    Update a permission (e.g., description). Requires admin privileges.
    """
    permission = await crud_permission.get(db, id=permission_id)
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found",
        )
    updated_permission = await crud_permission.update(db=db, db_obj=permission, obj_in=permission_in)
    return updated_permission

# Optional: Endpoint to delete a permission (Use with extreme caution)
# @router.delete("/{permission_id}", response_model=schemas.Permission)
# async def delete_permission(...):
#    ... check if permission is in use by roles ...