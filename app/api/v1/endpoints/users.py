from fastapi import APIRouter, Depends, HTTPException, status, Query, Response, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select # Import select
from sqlalchemy.orm import selectinload # Import selectinload
from typing import List, Any, Optional
import pandas as pd
import io

from app import crud, schemas
from app.api import deps
from app.db import models
from app.core.security import get_password_hash
from app.crud.crud_user import user as crud_user

router = APIRouter()

@router.get("/", response_model=List[schemas.User]) # Ensure response_model includes roles
async def read_users(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    search: Optional[str] = Query(None, description="Search by username, fullname, or id_number"), # Added search param
    current_user: models.User = Depends(deps.get_current_active_admin) # Require superuser
) -> Any:
    """
    Retrieve users. Requires superuser privileges.
    Includes optional search filter.
    """
    # --- Eager Load Roles ---
    stmt = select(models.User).options(selectinload(models.User.roles).selectinload(models.Role.permissions) )

    # --- Add Search Filter (Example) ---
    if search:
        search_term = f"%{search}%"
        stmt = stmt.filter(
            models.User.username.ilike(search_term) |
            models.User.full_name.ilike(search_term) |
            models.User.id_number.ilike(search_term)
        )

    # Apply pagination and ordering
    stmt = stmt.offset(skip).limit(limit).order_by(models.User.id)

    result = await db.execute(stmt)
    users = result.scalars().unique().all() # Use unique() with scalars() when using options

    # TODO: Implement proper total count for pagination if needed
    # total_count_stmt = select(func.count(models.User.id)).select_from(models.User)
    # if search: total_count_stmt = total_count_stmt.filter(...)
    # total_count = (await db.execute(total_count_stmt)).scalar_one()

    return users

# --- Other endpoints (create_user, read_user, update_user, delete_user, bulk_import_users) remain the same ---
# Ensure schemas.User includes 'roles: Optional[List[schemas.Role]] = []' or similar

@router.post("/", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
async def create_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_in: schemas.UserCreate,
    current_user: models.User = Depends(deps.get_current_active_admin) # Require superuser
) -> Any:
    """
    Create new user. Requires superuser privileges.
    """
    user = await crud_user.get_by_username(db, username=user_in.username)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user with this username already exists in the system.",
        )
    # Fetch roles by IDs to associate
    roles = []
    if user_in.role_ids:
        roles_result = await db.execute(select(models.Role).where(models.Role.id.in_(user_in.role_ids)))
        roles = roles_result.scalars().all()
        if len(roles) != len(user_in.role_ids):
             raise HTTPException(status_code=400, detail="One or more provided role IDs are invalid.")

    created_user = await crud_user.create_with_roles(db=db, obj_in=user_in, roles=roles)

    # Fetch again with roles loaded for the response
    stmt = select(models.User).options(selectinload(models.User.roles).selectinload(models.Role.permissions)).where(models.User.id == created_user.id)
    result = await db.execute(stmt)
    created_user_with_roles = result.scalar_one()

    return created_user_with_roles


@router.get("/{user_id}", response_model=schemas.User)
async def read_user(
    user_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_admin) # Require superuser
) -> Any:
    """
    Get user by ID. Requires superuser privileges.
    """
    # Eager load roles for the detail view as well
    stmt = select(models.User).options(selectinload(models.User.roles).selectinload(models.Role.permissions) ).where(models.User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The user with this ID does not exist in the system",
        )
    return user


@router.put("/{user_id}", response_model=schemas.User)
async def update_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_id: int,
    user_in: schemas.UserUpdate,
    current_user: models.User = Depends(deps.get_current_active_admin) # Require superuser
) -> Any:
    """
    Update a user. Requires superuser privileges.
    """
    user = await crud_user.get(db, id=user_id) # Get user first
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The user with this ID does not exist in the system",
        )

    # Fetch roles by IDs if provided
    roles = None # Use None to signal no change unless IDs are provided
    if user_in.role_ids is not None: # Check if role_ids is explicitly provided (even if empty list)
        if user_in.role_ids:
            roles_result = await db.execute(select(models.Role).where(models.Role.id.in_(user_in.role_ids)))
            roles = roles_result.scalars().all()
            if len(roles) != len(user_in.role_ids):
                raise HTTPException(status_code=400, detail="One or more provided role IDs are invalid.")
        else:
            roles = [] # Empty list means remove all roles

    # Update user using CRUD method that handles roles
    updated_user = await crud_user.update_with_roles(db=db, db_obj=user, obj_in=user_in, roles=roles)

    # Fetch again with roles loaded for the response
    stmt = select(models.User).options(selectinload(models.User.roles).selectinload(models.Role.permissions)).where(models.User.id == updated_user.id)
    result = await db.execute(stmt)
    updated_user_with_roles = result.scalar_one()

    return updated_user_with_roles


@router.delete("/{user_id}", response_model=schemas.User)
async def delete_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_id: int,
    current_user: models.User = Depends(deps.get_current_active_admin) # Require superuser
) -> Any:
    """
    Delete a user. Requires superuser privileges.
    """
    if user_id == current_user.id:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete the currently logged-in superuser.")

    # Fetch user with roles loaded *before* deleting to return it
    stmt = select(models.User).options(selectinload(models.User.roles)).where(models.User.id == user_id)
    result = await db.execute(stmt)
    user_to_delete = result.scalar_one_or_none()

    if not user_to_delete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    deleted_user = await crud_user.remove(db=db, id=user_id)
    if not deleted_user:
         # This case should ideally not happen if user_to_delete was found
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete user.")

    return user_to_delete # Return the object fetched before deletion


@router.post("/bulk-import", response_model=schemas.BulkImportResponse)
async def bulk_import_users(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_admin) # Require superuser
):
    """
    Bulk import users from an Excel (.xlsx) file.
    Required columns: username, password
    Optional columns: fullname, id_number, email, role_names (comma-separated)
    """
    if not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Invalid file type. Only .xlsx is supported.")

    contents = await file.read()
    data = io.BytesIO(contents)
    success_count = 0
    failed_count = 0
    errors = []

    try:
        df = pd.read_excel(data, dtype=str).fillna('') # Read all as string, fill NaN with empty string

        required_columns = ["username", "password"]
        if not all(col in df.columns for col in required_columns):
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns. Required: {', '.join(required_columns)}",
            )

        all_role_names = [role.name for role in (await db.execute(select(models.Role.name))).scalars().all()]
        role_name_to_id = {role.name: role.id for role in (await db.execute(select(models.Role.id, models.Role.name))).all()}

        for index, row in df.iterrows():
            row_num = index + 2 # Excel row number (1-based index + header)
            username = row.get("username", "").strip()
            password = row.get("password", "").strip()

            if not username or not password:
                errors.append({"row": row_num, "error": "Missing username or password."})
                failed_count += 1
                continue

            try:
                # Check if user already exists
                existing_user = await crud_user.get_by_username(db, username=username)
                if existing_user:
                    raise ValueError(f"Username '{username}' already exists.")

                # Prepare user data
                user_data = schemas.UserCreate(
                    username=username,
                    password=password, # Will be hashed by CRUD
                    fullname=row.get("fullname", "").strip() or None,
                    id_number=row.get("id_number", "").strip() or None,
                    email=row.get("email", "").strip() or None,
                    is_active=True, # Default to active
                    role_ids=[] # Start with empty roles
                )

                # Process roles
                role_names_str = row.get("role_names", "").strip()
                role_ids_to_assign = []
                invalid_roles = []
                if role_names_str:
                    role_names_list = [name.strip() for name in role_names_str.split(',') if name.strip()]
                    for role_name in role_names_list:
                        role_id = role_name_to_id.get(role_name)
                        if role_id:
                            role_ids_to_assign.append(role_id)
                        else:
                            invalid_roles.append(role_name)

                if invalid_roles:
                    raise ValueError(f"Invalid role names: {', '.join(invalid_roles)}. Valid roles: {', '.join(all_role_names)}")

                user_data.role_ids = role_ids_to_assign

                # Fetch role objects for CRUD
                roles_to_assign_objs = []
                if user_data.role_ids:
                    roles_result = await db.execute(select(models.Role).where(models.Role.id.in_(user_data.role_ids)))
                    roles_to_assign_objs = roles_result.scalars().all()

                # Create user using CRUD
                await crud_user.create_with_roles(db=db, obj_in=user_data, roles=roles_to_assign_objs)
                success_count += 1

            except ValueError as ve:
                 errors.append({"row": row_num, "error": str(ve)})
                 failed_count += 1
            except Exception as e: # Catch other potential errors during user creation
                 errors.append({"row": row_num, "error": f"Internal error: {str(e)}"})
                 failed_count += 1
                 # Consider rolling back transaction if needed, depending on session setup
                 # await db.rollback()

        # Commit changes if no major errors require full rollback (depends on session management)
        # await db.commit() # Often handled by middleware/dependency

    except pd.errors.EmptyDataError:
         raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    except Exception as e:
         # await db.rollback() # Rollback on general processing error
         raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
    finally:
         data.close()

    return {"success_count": success_count, "failed_count": failed_count, "errors": errors}
