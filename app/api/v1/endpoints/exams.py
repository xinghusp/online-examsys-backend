from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Any, Sequence, Optional

from app import crud, schemas
from app.db import models
from app.api import deps
from app.crud.crud_exam import crud_exam # Import the specific CRUD object

router = APIRouter()

# --- Permission Dependency ---
async def check_manage_exams_permission(
    current_user: models.User = Depends(deps.get_current_active_user)
) -> models.User:
    """Checks if the user has the 'manage_exams' permission."""
    required_permission_code = "manage_exams" # Adjust code if needed
    has_permission = False
    if hasattr(current_user, 'roles'):
        for role in current_user.roles:
            # Assuming permissions are loaded with roles (needs verification in deps.get_current_user)
            if hasattr(role, 'permissions'):
                 if any(p.code == required_permission_code for p in role.permissions):
                      has_permission = True
                      break
    if not has_permission:
        print(f"Permission denied for user {current_user.username}. Missing '{required_permission_code}'.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to manage exams.",
        )
    return current_user

# --- Exam Endpoints ---

@router.post("/", response_model=schemas.exam.Exam, status_code=status.HTTP_201_CREATED, tags=["Exams"])
async def create_exam(
    *,
    db: AsyncSession = Depends(deps.get_db),
    exam_in: schemas.exam.ExamCreate,
    current_user: models.User = Depends(check_manage_exams_permission)
) -> Any:
    """
    Create a new exam. Requires 'manage_exams' permission.
    - Assigns participants if provided.
    - Defines paper structure based on `paper_generation_mode`:
        - `manual`: Uses `manual_questions`.
        - `random_...`: Uses `random_rules` (processing logic TBD).
    """
    try:
        exam = await crud_exam.create(db=db, obj_in=exam_in, creator_id=current_user.id)
        # Construct response model - need counts and potentially details
        p_count = await crud_exam.get_participant_count(db=db, exam_id=exam.id)
        q_count = await crud_exam.get_question_count(db=db, exam_id=exam.id) # For manual/unified

        exam_data = schemas.exam.Exam.model_validate(exam).model_dump()
        exam_data["participant_count"] = p_count
        exam_data["question_count"] = q_count
        # TODO: Populate participants/questions/rules in response if needed by Exam schema
        exam_data["participants"] = [schemas.exam.ExamParticipantInfo.model_validate(p) for p in exam.participants]
        # Load questions separately for the response if manual/unified
        if exam.paper_generation_mode != schemas.exam.PaperGenerationModeEnum.random_individual:
             questions_db = await crud_exam.get_exam_questions(db=db, exam_id=exam.id)
             exam_data["questions"] = [schemas.question.Question.model_validate(q) for q in questions_db]
        else:
             exam_data["questions"] = [] # No fixed questions for random_individual

        # TODO: Add random_rules to response if stored/relevant
        exam_data["random_rules"] = exam_in.random_rules if exam_in.random_rules else None

        return exam_data

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Log e
        print(f"Error creating exam: {e}")
        raise HTTPException(status_code=500, detail="Internal server error creating exam.")


@router.get("/", response_model=List[schemas.exam.ExamListed], tags=["Exams"])
async def read_exams(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    status: Optional[schemas.exam.ExamStatusEnum] = Query(None, description="Filter by exam status"),
    # current_user: models.User = Depends(deps.get_current_active_user) # Allow any logged-in user to list?
) -> Any:
    """
    Retrieve a list of exams (summary view). Optionally filter by status.
    """
    exams_db = await crud_exam.get_multi(db, skip=skip, limit=limit, status=status)
    # Enhance with counts for response model
    response_exams = []
    for exam in exams_db:
         p_count = await crud_exam.get_participant_count(db=db, exam_id=exam.id)
         q_count = await crud_exam.get_question_count(db=db, exam_id=exam.id)
         exam_data = schemas.exam.ExamListed.model_validate(exam).model_dump()
         exam_data["participant_count"] = p_count
         exam_data["question_count"] = q_count
         response_exams.append(exam_data)
    return response_exams


@router.get("/{exam_id}", response_model=schemas.exam.Exam, tags=["Exams"])
async def read_exam(
    exam_id: int,
    db: AsyncSession = Depends(deps.get_db),
    # current_user: models.User = Depends(deps.get_current_active_user) # Allow any logged-in user? Or check participation?
) -> Any:
    """
    Get details of a specific exam, including participants and question list (for manual/unified).
    """
    exam = await crud_exam.get(db, id=exam_id) # CRUD get loads participant links and question links
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    # Construct response model
    p_count = await crud_exam.get_participant_count(db=db, exam_id=exam.id)
    q_count = await crud_exam.get_question_count(db=db, exam_id=exam.id) # For manual/unified

    exam_data = schemas.exam.Exam.model_validate(exam).model_dump()
    exam_data["participant_count"] = p_count
    exam_data["question_count"] = q_count
    exam_data["participants"] = [schemas.exam.ExamParticipantInfo.model_validate(p) for p in exam.participants]

    # Load questions separately for the response if manual/unified
    if exam.paper_generation_mode != schemas.exam.PaperGenerationModeEnum.random_individual:
         questions_db = await crud_exam.get_exam_questions(db=db, exam_id=exam.id)
         exam_data["questions"] = [schemas.question.Question.model_validate(q) for q in questions_db]
    else:
         exam_data["questions"] = []

    # TODO: Add random_rules to response if stored/relevant
    # exam_data["random_rules"] = ... # Fetch if stored

    return exam_data


@router.put("/{exam_id}", response_model=schemas.exam.Exam, tags=["Exams"])
async def update_exam(
    *,
    db: AsyncSession = Depends(deps.get_db),
    exam_id: int,
    exam_in: schemas.exam.ExamUpdate,
    current_user: models.User = Depends(check_manage_exams_permission)
) -> Any:
    """
    Update an exam. Requires 'manage_exams' permission.
    - Updates basic info, status, participants, and potentially manual questions (if in draft).
    - Restrictions apply based on exam status (e.g., cannot change times if ongoing).
    """
    exam = await crud_exam.get(db, id=exam_id) # Load relations needed for checks/updates
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    try:
        updated_exam = await crud_exam.update(db=db, db_obj=exam, obj_in=exam_in)
        # Construct response model - similar to GET /exam/{id}
        p_count = await crud_exam.get_participant_count(db=db, exam_id=updated_exam.id)
        q_count = await crud_exam.get_question_count(db=db, exam_id=updated_exam.id)

        exam_data = schemas.exam.Exam.model_validate(updated_exam).model_dump()
        exam_data["participant_count"] = p_count
        exam_data["question_count"] = q_count
        exam_data["participants"] = [schemas.exam.ExamParticipantInfo.model_validate(p) for p in updated_exam.participants]

        if updated_exam.paper_generation_mode != schemas.exam.PaperGenerationModeEnum.random_individual:
             questions_db = await crud_exam.get_exam_questions(db=db, exam_id=updated_exam.id)
             exam_data["questions"] = [schemas.question.Question.model_validate(q) for q in questions_db]
        else:
             exam_data["questions"] = []

        # TODO: Add random_rules to response if stored/relevant
        # exam_data["random_rules"] = ...

        return exam_data

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Log e
        print(f"Error updating exam {exam_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error updating exam.")


@router.delete("/{exam_id}", response_model=schemas.exam.Exam, tags=["Exams"])
async def delete_exam(
    *,
    db: AsyncSession = Depends(deps.get_db),
    exam_id: int,
    current_user: models.User = Depends(check_manage_exams_permission)
) -> Any:
    """
    Delete an exam. Requires 'manage_exams' permission.
    Only allowed if exam is in 'draft' status. Otherwise, archive it via PUT.
    """
    try:
        deleted_exam = await crud_exam.remove(db=db, id=exam_id)
        if not deleted_exam:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
        # Return basic info of the deleted exam
        return schemas.exam.ExamListed.model_validate(deleted_exam) # Use listed schema
    except ValueError as e: # Catch status restriction from CRUD
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
         # Log e
        print(f"Error deleting exam {exam_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error deleting exam.")

# --- Separate Endpoints for Participants/Questions (Optional) ---
# Alternatively, manage these via PUT /exams/{exam_id}

# Example: Get participants for an exam
@router.get("/{exam_id}/participants", response_model=List[schemas.exam.ExamParticipantInfo], tags=["Exams"])
async def read_exam_participants(
    exam_id: int,
    db: AsyncSession = Depends(deps.get_db),
    # current_user: models.User = Depends(deps.get_current_active_user) # Permissions?
):
    exam = await crud_exam.get(db, id=exam_id) # Loads participants
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return [schemas.exam.ExamParticipantInfo.model_validate(p) for p in exam.participants]

# Example: Get questions for an exam (manual/unified)
@router.get("/{exam_id}/questions", response_model=List[schemas.question.Question], tags=["Exams"])
async def read_exam_questions(
    exam_id: int,
    db: AsyncSession = Depends(deps.get_db),
    # current_user: models.User = Depends(deps.get_current_active_user) # Permissions?
):
    exam = await db.get(models.Exam, exam_id) # Check exam exists
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    if exam.paper_generation_mode == schemas.exam.PaperGenerationModeEnum.random_individual:
         return [] # No fixed list for this mode

    questions_db = await crud_exam.get_exam_questions(db=db, exam_id=exam.id)
    return [schemas.question.Question.model_validate(q) for q in questions_db]
