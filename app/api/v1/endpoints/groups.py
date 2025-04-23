from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Any

from app import crud, schemas
from app.db import models
from app.api import deps

router = APIRouter()

@router.post("/", response_model=schemas.Group, status_code=status.HTTP_201_CREATED)
async def create_group(
    *,
    db: AsyncSession = Depends(deps.get_db),
    group_in: schemas.GroupCreate,
    current_user: models.User = Depends(deps.get_current_active_admin)
) -> Any:
    """
    Create new group with initial users. Requires admin privileges.
    """
    try:
        group = await crud.CRUDGroup.create(db=db, obj_in=group_in)
        # Fetch user count separately for the response model
        user_count = await crud.CRUDGroup.get_user_count(db=db, group_id=group.id)
        group_data = schemas.Group.model_validate(group).model_dump()
        group_data["user_count"] = user_count
        return group_data
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Log e
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creating group")


@router.get("/", response_model=List[schemas.Group])
async def read_groups(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: models.User = Depends(deps.get_current_active_admin)
) -> Any:
    """
    Retrieve groups. Includes user count. Requires admin privileges.
    """
    groups = await crud.CRUDGroup.get_multi(db, skip=skip, limit=limit)
    # Enhance response with user counts
    response_groups = []
    for group in groups:
        user_count = await crud.CRUDGroup.get_user_count(db=db, group_id=group.id)
        group_data = schemas.Group.model_validate(group).model_dump()
        group_data["user_count"] = user_count
        response_groups.append(group_data)
    return response_groups


@router.get("/{group_id}", response_model=schemas.Group)
async def read_group(
    group_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_admin)
) -> Any:
    """
    Get a specific group by ID, including user count. Requires admin privileges.
    """
    group = await crud.CRUDGroup.get(db, id=group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )
    user_count = await crud.CRUDGroup.get_user_count(db=db, group_id=group.id)
    group_data = schemas.Group.model_validate(group).model_dump()
    group_data["user_count"] = user_count
    return group_data


@router.put("/{group_id}", response_model=schemas.Group)
async def update_group(
    *,
    db: AsyncSession = Depends(deps.get_db),
    group_id: int,
    group_in: schemas.GroupUpdate,
    current_user: models.User = Depends(deps.get_current_active_admin)
) -> Any:
    """
    Update a group. Can update name, description, and replace users.
    Requires admin privileges.
    """
    group = await crud.CRUDGroup.get(db, id=group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )
    try:
        updated_group = await crud.CRUDGroup.update(db=db, db_obj=group, obj_in=group_in)
        user_count = await crud.CRUDGroup.get_user_count(db=db, group_id=updated_group.id)
        group_data = schemas.Group.model_validate(updated_group).model_dump()
        group_data["user_count"] = user_count
        return group_data
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Log e
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error updating group")


@router.delete("/{group_id}", response_model=schemas.Group)
async def delete_group(
    *,
    db: AsyncSession = Depends(deps.get_db),
    group_id: int,
    current_user: models.User = Depends(deps.get_current_active_admin)
) -> Any:
    """
    Delete a group. Requires admin privileges.
    (Note: Add check if group is used in exams before deletion if needed).
    """
    # --- Deletion Prevention Logic ---
    # Check if group is assigned as participant in any non-archived/finished exams
    # query = select(models.ExamParticipant).join(models.Exam).where(
    #     models.ExamParticipant.group_id == group_id,
    #     models.Exam.status.notin_(['finished', 'archived']) # Adjust statuses as needed
    # ).limit(1)
    # result = await db.execute(query)
    # if result.scalars().first():
    #      raise HTTPException(
    #          status_code=status.HTTP_400_BAD_REQUEST,
    #          detail="Cannot delete group assigned to active or upcoming exams.",
    #      )
    # --- End Deletion Prevention ---

    deleted_group = await crud.CRUDGroup.remove(db=db, id=group_id)
    if not deleted_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    # Return the data of the deleted group
    group_data = schemas.Group.model_validate(deleted_group).model_dump()
    group_data["user_count"] = 0 # User count is 0 after deletion
    return group_data


# --- Endpoint to assign users to a group ---
@router.put("/{group_id}/assign-users", response_model=schemas.Group)
async def assign_users_to_group(
    group_id: int,
    *,
    db: AsyncSession = Depends(deps.get_db),
    users_in: schemas.GroupAssignUsers,
    current_user: models.User = Depends(deps.get_current_active_admin) # Admin required
) -> Any:
    """
    Assign users to a specific group, replacing current members.
    Requires admin privileges.
    """
    group_to_update = await crud.CRUDGroup.get(db=db, id=group_id)
    if not group_to_update:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    try:
        updated_group = await crud.CRUDGroup.assign_users_to_group(db=db, group=group_to_update, user_ids=users_in.user_ids)
        user_count = await crud.CRUDGroup.get_user_count(db=db, group_id=updated_group.id)
        group_data = schemas.Group.model_validate(updated_group).model_dump()
        group_data["user_count"] = user_count
        return group_data
    except Exception as e:
        # Log e
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error assigning users to group")
