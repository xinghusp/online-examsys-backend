from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Any
from datetime import datetime, timezone

from sqlalchemy.orm import selectinload

from app import crud, schemas
from app.crud.crud_answer import CRUDAnswer
from app.db import models
from app.api import deps
from app.crud import CRUDExamAttempt, crud_answer, crud_exam # Import specific CRUDs

router = APIRouter()

# --- Helper Function ---
async def get_valid_active_attempt(attempt_id: int, current_user: models.User, db: AsyncSession) -> models.ExamAttempt:
    """Dependency-like function to get and validate an active attempt."""
    attempt = await CRUDExamAttempt.get(db=db, attempt_id=attempt_id)
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam attempt not found.")
    if attempt.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this attempt.")
    if attempt.status != schemas.attempt.ExamAttemptStatusEnum.in_progress:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Exam attempt is not in progress (status: {attempt.status.value}).")
    # Check timing (optional, but good)
    now = datetime.now(timezone.utc)
    if attempt.calculated_end_time and now > attempt.calculated_end_time:
         # TODO: Should trigger auto-submit via background task, but raise error here for now
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exam time has expired.")
    return attempt

# --- Endpoints ---

@router.get("/exams/available", response_model=List[schemas.exam.ExamForStudent], tags=["Exam Taking"])
async def list_available_exams(
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """
    Lists exams available for the current student to take or resume.
    Includes exams they are assigned to (directly or via group) that are 'published' or 'ongoing'.
    """
    now = datetime.now(timezone.utc)
    user_id = current_user.id
    group_ids = [group.id for group in getattr(current_user, 'groups', [])] # Assumes groups are loaded

    # Find exams assigned to user or their groups, within time, and published/ongoing
    assigned_exam_ids_query = (
        select(models.ExamParticipant.exam_id)
        .distinct()
        .where(
            (models.ExamParticipant.user_id == user_id) |
            (models.ExamParticipant.group_id.in_(group_ids) if group_ids else False)
        )
    )
    assigned_exam_ids_res = await db.execute(assigned_exam_ids_query)
    assigned_exam_ids = assigned_exam_ids_res.scalars().all()

    if not assigned_exam_ids:
        return []

    # Fetch relevant exams and attempts
    exams_query = (
        select(models.Exam)
        .options(selectinload(models.Exam.attempts.and_(models.ExamAttempt.user_id == user_id))) # Load only user's attempt
        .where(
            models.Exam.id.in_(assigned_exam_ids),
            models.Exam.start_time <= now, # Exam has started
            models.Exam.end_time > now,    # Exam hasn't ended yet
            models.Exam.status.in_([schemas.exam.ExamStatusEnum.published, schemas.exam.ExamStatusEnum.ongoing])
        )
        .order_by(models.Exam.start_time)
    )
    exams_result = await db.execute(exams_query)
    available_exams = exams_result.scalars().unique().all()

    response_list = []
    for exam in available_exams:
        attempt = exam.attempts[0] if exam.attempts else None # Should be max 1 attempt per user/exam loaded
        exam_data = schemas.exam.ExamForStudent(
            id=exam.id,
            name=exam.name,
            start_time=exam.start_time,
            end_time=exam.end_time,
            duration_minutes=exam.duration_minutes,
            status=exam.status,
            attempt_status=attempt.status if attempt else None,
            attempt_id=attempt.id if attempt else None,
        )
        # Only include if not already fully completed
        if not attempt or attempt.status not in [schemas.attempt.ExamAttemptStatusEnum.submitted, schemas.attempt.ExamAttemptStatusEnum.graded, schemas.attempt.ExamAttemptStatusEnum.aborted]:
             response_list.append(exam_data)

    return response_list


@router.post("/attempts/start/{exam_id}", response_model=schemas.attempt.ExamAttempt, tags=["Exam Taking"])
async def start_or_resume_exam_attempt(
    exam_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """
    Starts a new exam attempt or resumes an 'in_progress' one for the current user and specified exam.
    Generates paper for 'random_individual' mode on first start.
    """
    # 1. Validate Exam and Participation
    exam = await db.get(models.Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found.")

    now = datetime.now(timezone.utc)
    if exam.start_time > now:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exam has not started yet.")
    if exam.end_time <= now:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exam has already ended.")
    if exam.status not in [schemas.exam.ExamStatusEnum.published, schemas.exam.ExamStatusEnum.ongoing]:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Exam cannot be started (status: {exam.status.value}).")

    # Check participation (more robust check needed for groups)
    is_participant_query = select(models.ExamParticipant.id).where(
        models.ExamParticipant.exam_id == exam_id,
        (models.ExamParticipant.user_id == current_user.id) |
        (models.ExamParticipant.group_id.in_([g.id for g in getattr(current_user, 'groups', [])]))
    ).limit(1)
    participant_check = await db.execute(is_participant_query)
    if not participant_check.scalar_one_or_none():
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not assigned to this exam.")

    # 2. Get or Create Attempt record
    try:
        attempt = await CRUDExamAttempt.create_or_get_pending(db=db, user_id=current_user.id, exam_id=exam_id)
    except ValueError as e: # Handles case where attempt is already completed
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # 3. Start the attempt if pending
    if attempt.status == schemas.attempt.ExamAttemptStatusEnum.pending:
        try:
             # Generate paper if random_individual *before* starting
             if exam.paper_generation_mode == schemas.exam.PaperGenerationModeEnum.random_individual:
                  # TODO: Fetch random rules associated with the exam
                  # random_rules_data = fetch_random_rules_for_exam(exam_id) # Needs implementation
                  # For now, assuming rules are somehow available (e.g., stored on exam model or fetched)
                  # Let's assume rules are passed or fetched - requires schema/db adjustment
                  # This generation should ideally happen within the start_attempt transaction
                  # await crud_exam_attempt.generate_individual_paper(db=db, attempt=attempt, rules=random_rules_data)
                  pass # Placeholder - Paper generation needs rules source

             attempt = await CRUDExamAttempt.start_attempt(db=db, attempt=attempt, duration_minutes=exam.duration_minutes)
             # Update exam status to ongoing if it was published
             if exam.status == schemas.exam.ExamStatusEnum.published:
                  exam.status = schemas.exam.ExamStatusEnum.ongoing
                  db.add(exam)
                  await db.commit() # Commit exam status change
                  await db.refresh(exam)

        except ValueError as e:
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    elif attempt.status != schemas.attempt.ExamAttemptStatusEnum.in_progress:
         # Should not happen if create_or_get_pending worked correctly
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot resume attempt with status '{attempt.status.value}'.")

    # 4. Return attempt details
    return attempt


@router.get("/attempts/{attempt_id}/questions", response_model=schemas.attempt.ExamAttemptQuestionsResponse, tags=["Exam Taking"])
async def get_attempt_questions(
    attempt_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
    # Add pagination if needed (e.g., ?page=1&size=1 for one-by-one)
    # page: int = Query(1, ge=1),
    # size: int = Query(1000, ge=1) # Default to all questions for now
):
    """
    Fetches the list of questions for the specified active exam attempt.
    """
    attempt = await get_valid_active_attempt(attempt_id, current_user, db)

    # Fetch the actual question objects based on the attempt/exam mode
    # Returns list of (Question, order_index, score) tuples
    paper_questions_raw = await CRUDExamAttempt.get_attempt_paper_questions(db=db, attempt_id=attempt_id)

    questions_for_student = []
    for question_db, order_index, score in paper_questions_raw:
         # Adapt Question model to QuestionForStudent schema
         options_data = None
         if question_db.options and isinstance(question_db.options, list):
              options_data = [schemas.question.QuestionOption.model_validate(opt) for opt in question_db.options]

         q_student = schemas.question.QuestionForStudent(
             id=question_db.id,
             question_type=question_db.question_type,
             stem=question_db.stem,
             score=float(score), # Use the score specific to this exam paper
             options=options_data,
             order_index=order_index
         )
         questions_for_student.append(q_student)

    # TODO: Implement pagination logic if size < total questions

    return schemas.attempt.ExamAttemptQuestionsResponse(
        attempt_status=attempt.status,
        questions=questions_for_student,
        calculated_end_time=attempt.calculated_end_time
    )


@router.put("/attempts/{attempt_id}/answers/{question_id}", response_model=schemas.question.AnswerResponse, tags=["Exam Taking"])
async def save_answer(
    attempt_id: int,
    question_id: int,
    answer_in: schemas.question.AnswerSubmit, # Get answer from request body
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """
    Saves a student's answer for a specific question within an active attempt.
    Uses Upsert logic (creates or updates).
    """
    attempt = await get_valid_active_attempt(attempt_id, current_user, db)

    # TODO: Validate that question_id is actually part of this attempt's paper?

    try:
        # user_answer needs validation based on question type before saving?
        # crud_answer.save_answer handles the upsert
        saved_answer = await CRUDAnswer.save_answer(
            db=db,
            attempt_id=attempt.id,
            question_id=question_id,
            user_answer=answer_in.user_answer # Pass the raw user answer
        )
        return saved_answer
    except Exception as e:
        # Log e
        print(f"Error saving answer for attempt {attempt_id}, question {question_id}: {e}")
        raise HTTPException(status_code=500, detail="Error saving answer.")


@router.post("/attempts/{attempt_id}/submit", response_model=schemas.attempt.ExamAttempt, tags=["Exam Taking"])
async def submit_exam_attempt(
    attempt_id: int,
    # submit_data: schemas.attempt.ExamAttemptSubmit, # Use if confirmation needed
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """
    Finalizes and submits the active exam attempt.
    """
    # get_valid_active_attempt checks status and ownership
    attempt = await get_valid_active_attempt(attempt_id, current_user, db)

    # if not submit_data.confirm:
    #      raise HTTPException(status_code=400, detail="Submission not confirmed.")

    try:
        submitted_attempt = await CRUDExamAttempt.submit_attempt(db=db, attempt=attempt)
        # TODO: Trigger background grading task (e.g., Celery) here
        # trigger_auto_grading.delay(submitted_attempt.id)
        return submitted_attempt
    except ValueError as e: # Catch invalid status from CRUD
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Log e
        print(f"Error submitting attempt {attempt_id}: {e}")
        raise HTTPException(status_code=500, detail="Error submitting exam.")


@router.post("/attempts/{attempt_id}/heartbeat", response_model=schemas.attempt.HeartbeatResponse, tags=["Exam Taking"])
async def attempt_heartbeat(
    attempt_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """
    Client sends this periodically while the student is actively taking the exam.
    Updates the `last_heartbeat` timestamp on the attempt record.
    """
    # Attempt validation (ownership, status) happens implicitly in crud update
    success = await CRUDExamAttempt.update_heartbeat(db=db, attempt_id=attempt_id)

    if not success:
        # Attempt might be over, submitted, or doesn't belong to user
        # Client should ideally check attempt status if heartbeat fails
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active attempt not found or already finished.")

    return schemas.attempt.HeartbeatResponse()
