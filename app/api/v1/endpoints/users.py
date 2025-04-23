from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Any

from app import crud, schemas # Updated import
from app.api import deps
from app.db import models
from app.utils import excel_processor

router = APIRouter()
@router.post("/", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
async def create_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_in: schemas.UserCreate,
    current_user: models.User = Depends(deps.get_current_active_admin) # Require admin to create users
) -> Any:
    """
    Create new user. Requires admin privileges.
    """
    # Check if username already exists
    existing_user = await crud.crud_user.user.get_by_username(db, username=user_in.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )
    # Check if ID number already exists (if provided)
    if user_in.id_number:
         existing_id = await crud.CRUDUser.get_by_id_number(db, id_number=user_in.id_number)
         if existing_id:
             raise HTTPException(
                 status_code=status.HTTP_400_BAD_REQUEST,
                 detail="ID number already registered",
             )

    user = await crud.CRUDUser.create(db=db, obj_in=user_in)
    # TODO: Assign default role (e.g., 'Student') if needed, or handle role assignment via another endpoint/parameter.
    return user


@router.get("/", response_model=List[schemas.User])
async def read_users(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: models.User = Depends(deps.get_current_active_admin) # Require admin
) -> Any:
    """
    Retrieve users. Requires admin privileges.
    """
    users = await crud.CRUDUser.get_multi(db, skip=skip, limit=limit)
    return users


@router.get("/me", response_model=schemas.User)
async def read_user_me(
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get current user's information.
    """
    return current_user


@router.get("/{user_id}", response_model=schemas.User)
async def read_user_by_id(
    user_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_admin) # Require admin
) -> Any:
    """
    Get a specific user by ID. Requires admin privileges.
    """
    user = await crud.CRUDUser.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    # Optional: Add check if non-admin user is trying to access other user's data
    # if user.id != current_user.id and not is_admin(current_user):
    #    raise HTTPException(status_code=403...)
    return user


@router.put("/{user_id}", response_model=schemas.User)
async def update_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_id: int,
    user_in: schemas.UserUpdate,
    current_user: models.User = Depends(deps.get_current_active_admin) # Require admin
) -> Any:
    """
    Update a user. Requires admin privileges.
    """
    user = await crud.CRUDUser.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check for username conflict if username is being changed
    if user_in.username and user_in.username != user.username:
        existing_user = await crud.CRUDUser.get_by_username(db, username=user_in.username)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(status_code=400, detail="Username already taken.")

    # Check for ID number conflict if it's being changed
    if user_in.id_number and user_in.id_number != user.id_number:
        existing_id = await crud.user.get_by_id_number(db, id_number=user_in.id_number)
        if existing_id and existing_id.id != user_id:
            raise HTTPException(status_code=400, detail="ID number already registered.")

    user = await crud.CRUDUser.update(db=db, db_obj=user, obj_in=user_in)
    return user


@router.delete("/{user_id}", response_model=schemas.User)
async def delete_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_id: int,
    current_user: models.User = Depends(deps.get_current_active_admin) # Require admin
) -> Any:
    """
    Delete a user. Requires admin privileges.
    (Note: Add logic to prevent deletion if user has exam records as per requirements).
    """
    user = await crud.CRUDUser.get(db=db, id=user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin users cannot delete themselves")

    # --- Deletion Prevention Logic ---
    # Check for related exam attempts before deleting
    # This requires the ExamAttempt model and relationship to be defined
    query = select(models.ExamAttempt).where(models.ExamAttempt.user_id == user_id).limit(1)
    result = await db.execute(query)
    if result.scalars().first():
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST,
             detail="Cannot delete user with existing exam records. Disable the user instead.",
         )
    # Add similar checks for other critical relationships if necessary (e.g., created exams)
    # --- End Deletion Prevention ---

    deleted_user = await crud.CRUDUser.remove(db=db, id=user_id)
    # Return the data of the deleted user, conforming to the response model
    return deleted_user
@router.post("/bulk-import", response_model=schemas.user.UserBulkImportResponse, tags=["Users"])
async def bulk_import_users(
    *,
    db: AsyncSession = Depends(deps.get_db),
    file: UploadFile = File(..., description="Excel file (.xlsx) containing user data."),
    current_user: models.User = Depends(deps.get_current_active_admin) # Check permission
) -> Any:
    """
    Bulk imports users from an Excel file.

    Requires 'manage_users' permission.

    The Excel file should have columns matching the `UserImportRecord` schema:
    `username` (required), `id-number`, `fullname`, `password` (required), `role_names` (comma-separated).
    """
    if not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file type. Only .xlsx files are accepted.")

    try:
        file_content = await file.read()
        user_records = excel_processor.parse_user_import_file(file_content)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error parsing file: {ve}")
    except Exception as e:
        # Log e
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to read or process the file: {e}")
    finally:
        await file.close()

    if not user_records:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid user records found in the file.")

    # Perform bulk creation using CRUD
    try:
        success_count, errors = await crud.crud_user.user.bulk_create(db=db, users_in=user_records)
        return schemas.user.UserBulkImportResponse(
            success_count=success_count,
            failed_count=len(errors),
            errors=errors
        )
    except Exception as e:
        # Log e
        # This might catch unexpected errors during the bulk_create process itself
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An error occurred during the bulk import process: {e}")
