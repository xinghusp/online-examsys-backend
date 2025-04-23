from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Any

from app import crud, schemas
from app.db import models
from app.api import deps

router = APIRouter()

@router.post("/", response_model=schemas.Role, status_code=status.HTTP_201_CREATED)
async def create_role(
    *,
    db: AsyncSession = Depends(deps.get_db),
    role_in: schemas.RoleCreate,
    current_user: models.User = Depends(deps.get_current_active_admin)
) -> Any:
    """
    Create new role with initial permissions. Requires admin privileges.
    """
    try:
        role = await crud.CRUDRole.create(db=db, obj_in=role_in)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
         # Log the exception e
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creating role")
    return role

@router.get("/", response_model=List[schemas.Role])
async def read_roles(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: models.User = Depends(deps.get_current_active_admin)
) -> Any:
    """
    Retrieve roles. Includes assigned permissions. Requires admin privileges.
    """
    roles = await crud.CRUDRole.get_multi(db, skip=skip, limit=limit)
    return roles

@router.get("/{role_id}", response_model=schemas.Role)
async def read_role(
    role_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_admin)
) -> Any:
    """
    Get a specific role by ID, including permissions. Requires admin privileges.
    """
    role = await crud.CRUDRole.get(db, id=role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    return role

@router.put("/{role_id}", response_model=schemas.Role)
async def update_role(
    *,
    db: AsyncSession = Depends(deps.get_db),
    role_id: int,
    role_in: schemas.RoleUpdate,
    current_user: models.User = Depends(deps.get_current_active_admin)
) -> Any:
    """
    Update a role. Can update name, description, and replace permissions.
    Requires admin privileges.
    """
    role = await crud.CRUDRole.get(db, id=role_id) # Get loads permissions too
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    try:
        updated_role = await crud.CRUDRole.update(db=db, db_obj=role, obj_in=role_in)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Log the exception e
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error updating role")

    return updated_role

@router.delete("/{role_id}", response_model=schemas.Role)
async def delete_role(
    *,
    db: AsyncSession = Depends(deps.get_db),
    role_id: int,
    current_user: models.User = Depends(deps.get_current_active_admin)
) -> Any:
    """
    Delete a role. Requires admin privileges.
    Prevents deletion of 'System Admin' role.
    (Note: Add check if role is assigned to users before deletion if needed).
    """
    try:
        deleted_role = await crud.CRUDRole.remove(db=db, id=role_id)
        if not deleted_role:
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    except ValueError as e: # Catch error from CRUD (e.g., trying to delete admin)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
         # Log the exception e
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error deleting role")

    return deleted_role

# --- Endpoint to assign roles to a user ---
# This could also live in users.py, but placing here keeps role logic together
@router.put("/assign-to-user/{user_id}", response_model=schemas.User) # Return the updated user
async def assign_roles_to_user(
    user_id: int,
    *,
    db: AsyncSession = Depends(deps.get_db),
    roles_in: schemas.UserAssignRoles,
    current_user: models.User = Depends(deps.get_current_active_admin) # Admin required
) -> Any:
    """
    Assign roles to a specific user, replacing their current roles.
    Requires admin privileges.
    """
    user_to_update = await crud.CRUDUser.get(db=db, id=user_id) # Fetch user
    if not user_to_update:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Prevent admin from removing their own admin role?
    if user_to_update.id == current_user.id:
        admin_role_id = None
        current_admin_role = await crud.CRUDRole.get_by_name(db, name="System Admin")
        if current_admin_role:
            admin_role_id = current_admin_role.id
        if admin_role_id and admin_role_id not in roles_in.role_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin cannot remove their own System Admin role.")

    try:
        updated_user = await crud.CRUDRole.assign_roles_to_user(db=db, user=user_to_update, role_ids=roles_in.role_ids)
    except Exception as e:
        # Log e
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error assigning roles to user")

    # Need to load roles for the response model (schemas.User doesn't include them by default)
    # We might need a UserWithRoles schema or adjust the crud.role.assign_roles_to_user return/refresh logic
    # For now, return the user object which *should* have roles loaded due to refresh in CRUD
    # Re-fetch user with roles loaded to be safe for response model
    user_with_roles = await crud.CRUDUser.get(db=db, id=user_id) # crud.user.get doesn't load roles by default...
    # Let's modify crud.user.get to optionally load roles, or create a specific function
    # Quick fix: reload here (not ideal)
    await db.refresh(user_with_roles, attribute_names=['roles'])
    # Now create the response model. We need a User schema that includes roles.
    # Let's define UserWithRoles in schemas/user.py
    # Assuming UserWithRoles schema exists: return schemas.UserWithRoles.from_orm(user_with_roles)
    # If not, just return the basic user schema for now:
    return schemas.User.model_validate(user_with_roles) # Validate against basic User schema
