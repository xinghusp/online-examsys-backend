import io

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from fastapi.responses import StreamingResponse # For export
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Any, Optional

from app import crud, schemas
from app.crud.crud_attempt import crud_exam_attempt
from app.db import models
from app.api import deps
from app.crud import CRUDExamAttempt, crud_answer, crud_exam # Import specific CRUDs
from app.utils import excel_processor # For export

router = APIRouter()

# --- Permission Dependencies ---
async def check_grade_exams_permission(
    current_user: models.User = Depends(deps.get_current_active_user)
) -> models.User:
    """Checks if the user has the 'grade_exams' permission."""
    required_permission_code = "grade_exams" # Adjust code if needed
    # ... (Permission checking logic - assuming loaded roles/permissions) ...
    has_permission = False
    if hasattr(current_user, 'roles'):
        for role in current_user.roles:
            if hasattr(role, 'permissions'):
                 if any(p.code == required_permission_code for p in role.permissions):
                      has_permission = True
                      break
    if not has_permission:
        raise HTTPException(status_code=403, detail=f"Missing required permission: {required_permission_code}")
    return current_user

async def check_view_all_results_permission(
    current_user: models.User = Depends(deps.get_current_active_user)
) -> models.User:
    """Checks if the user has the 'view_all_results' permission."""
    required_permission_code = "view_all_results" # Adjust code if needed
    # ... (Permission checking logic) ...
    has_permission = False
    if hasattr(current_user, 'roles'):
        for role in current_user.roles:
            if hasattr(role, 'permissions'):
                 if any(p.code == required_permission_code for p in role.permissions):
                      has_permission = True
                      break
    if not has_permission:
        raise HTTPException(status_code=403, detail=f"Missing required permission: {required_permission_code}")
    return current_user

# --- Grading Endpoints ---

@router.get("/grading/manual", response_model=List[schemas.grading.AnswerForGrading], tags=["Grading"])
async def list_answers_for_manual_grading(
    exam_id: Optional[int] = Query(None, description="Filter by specific Exam ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(deps.get_db),
    grader: models.User = Depends(check_grade_exams_permission),
):
    """
    Lists answers requiring manual grading (e.g., short answer, not yet graded).
    Requires 'grade_exams' permission.
    """
    answers_db = await crud_answer.get_answers_needing_manual_grade(db=db, exam_id=exam_id, limit=limit, offset=offset)

    response_list = []
    for answer in answers_db:
        # Adapt DB model to response schema
        question = answer.question
        attempt = answer.attempt
        user = attempt.user if attempt else None
        # Get max score for this question in this exam (complex if random_individual)
        # For now, use default question score. Needs refinement for accuracy.
        max_score = question.score if question else 0.0

        response_list.append(schemas.grading.AnswerForGrading(
            answer_id=answer.id,
            attempt_id=answer.attempt_id,
            question_id=answer.question_id,
            user_id=attempt.user_id if attempt else -1,
            question_stem=question.stem if question else "N/A",
            question_type=question.question_type if question else "N/A",
            question_max_score=max_score,
            model_answer=question.answer if question else None, # Show model answer from Question table
            user_answer=answer.user_answer,
            current_score=answer.score,
            current_comments=answer.grading_comments
        ))
    return response_list


@router.put("/grading/manual/answers/{answer_id}", response_model=schemas.question.AnswerResponse, tags=["Grading"])
async def submit_manual_grade(
    answer_id: int,
    grade_in: schemas.grading.ManualGradeInput,
    db: AsyncSession = Depends(deps.get_db),
    grader: models.User = Depends(check_grade_exams_permission),
):
    """
    Submits a manual grade (score, comments) for a specific answer.
    Requires 'grade_exams' permission.
    """
    updated_answer = await crud_answer.apply_manual_grade(
        db=db, answer_id=answer_id, grade_in=grade_in, grader_id=grader.id
    )
    if not updated_answer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer not found.")

    # TODO: Optionally trigger attempt score recalculation here or via separate process
    # await crud_exam_attempt.calculate_and_save_final_score(db=db, attempt_id=updated_answer.attempt_id)

    return updated_answer


@router.post("/grading/attempts/{attempt_id}/calculate-score", response_model=schemas.attempt.ExamAttempt, tags=["Grading"])
async def calculate_final_score_for_attempt(
    attempt_id: int,
    db: AsyncSession = Depends(deps.get_db),
    grader: models.User = Depends(check_grade_exams_permission), # Or admin?
):
    """
    Triggers the calculation and saving of the final score for an attempt.
    Assumes all necessary grading (auto + manual) is complete.
    Requires 'grade_exams' permission.
    """
    updated_attempt = await crud_exam_attempt.calculate_and_save_final_score(db=db, attempt_id=attempt_id)
    if not updated_attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found.")
    return updated_attempt


# --- Student Result Endpoints ---

@router.get("/results/my-attempts", response_model=List[schemas.grading.AttemptResultStudent], tags=["Results (Student)"])
async def get_my_exam_results(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """
    Retrieves the current student's history of completed exam attempts.
    """
    attempts_db = await crud_exam_attempt.get_student_results(db=db, user_id=current_user.id, skip=skip, limit=limit)

    response_list = []
    for attempt in attempts_db:
        exam = attempt.exam
        # TODO: Calculate total possible score for this attempt's paper
        total_possible = None # Placeholder
        response_list.append(schemas.grading.AttemptResultStudent(
            attempt_id=attempt.id,
            exam_id=attempt.exam_id,
            exam_name=exam.name if exam else "N/A",
            start_time=attempt.start_time,
            submit_time=attempt.submit_time,
            status=attempt.status,
            final_score=attempt.final_score,
            total_possible_score=total_possible,
        ))
    return response_list


@router.get("/results/my-attempts/{attempt_id}", response_model=schemas.grading.AttemptResultDetail, tags=["Results (Student)"])
async def get_my_attempt_details(
    attempt_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """
    Retrieves detailed results for a specific attempt belonging to the current student,
    including scores per question and potentially correct answers/explanations based on exam settings.
    """
    attempt = await crud_exam_attempt.get_attempt_details_for_result(db=db, attempt_id=attempt_id)

    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found.")
    if attempt.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this attempt.")
    if attempt.status not in [schemas.attempt.ExamAttemptStatusEnum.graded, schemas.attempt.ExamAttemptStatusEnum.aborted]: # Only show graded? Or submitted?
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attempt results are not yet available.")

    exam = attempt.exam
    show_answers = exam.show_answers_after_exam if exam else False # Control visibility

    # Get the paper structure (question_id -> {order_index, max_score})
    paper_structure_raw = await crud_exam_attempt.get_attempt_paper_questions(db=db, attempt_id=attempt_id)
    paper_map = {q.id: {"order": idx, "max_score": score} for q, idx, score in paper_structure_raw}

    answer_details = []
    answers_by_qid = {ans.question_id: ans for ans in attempt.answers}

    for q_id, paper_info in sorted(paper_map.items(), key=lambda item: item[1]["order"]):
        answer = answers_by_qid.get(q_id)
        question = answer.question if answer else None # Question should be loaded with answer

        if not question: continue # Should not happen if paper/answers are consistent

        answer_details.append(schemas.grading.AnswerResultDetail(
            question_id=q_id,
            order_index=paper_info["order"],
            question_stem=question.stem,
            question_type=question.question_type,
            max_score=float(paper_info["max_score"]),
            user_answer=answer.user_answer if answer else None,
            is_correct=answer.is_correct if answer else None,
            score=answer.score if answer else None,
            correct_answer=question.answer if show_answers else None, # Show based on setting
            explanation=question.explanation if show_answers else None, # Show based on setting
            grading_comments=answer.grading_comments if answer else None,
        ))

    # TODO: Calculate total possible score based on paper_map
    total_possible = sum(p["max_score"] for p in paper_map.values())

    return schemas.grading.AttemptResultDetail(
        attempt_id=attempt.id,
        exam_id=attempt.exam_id,
        exam_name=exam.name if exam else "N/A",
        start_time=attempt.start_time,
        submit_time=attempt.submit_time,
        status=attempt.status,
        final_score=attempt.final_score,
        total_possible_score=total_possible,
        answers=answer_details,
        show_answers_after_exam=show_answers,
    )


# --- Admin Result Endpoints ---

@router.get("/results/admin/exams/{exam_id}/overview", response_model=schemas.grading.ExamResultOverviewAdmin, tags=["Results (Admin)"])
async def get_exam_results_overview_admin(
    exam_id: int,
    db: AsyncSession = Depends(deps.get_db),
    admin_user: models.User = Depends(check_view_all_results_permission),
):
    """
    Retrieves overview statistics for a specific exam's results.
    Requires 'view_all_results' permission.
    """
    exam = await db.get(models.Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found.")

    stats = await crud_exam_attempt.get_exam_statistics_admin(db=db, exam_id=exam_id)

    return schemas.grading.ExamResultOverviewAdmin(
        exam_id=exam_id,
        exam_name=exam.name,
        **stats # Unpack stats dict
    )


@router.get("/results/admin/exams/{exam_id}/attempts", response_model=List[schemas.grading.AttemptResultAdmin], tags=["Results (Admin)"])
async def list_exam_attempts_admin(
    exam_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    db: AsyncSession = Depends(deps.get_db),
    admin_user: models.User = Depends(check_view_all_results_permission),
):
    """
    Lists individual attempts for a specific exam for admin view.
    Requires 'view_all_results' permission.
    """
    attempts_db = await crud_exam_attempt.get_exam_results_admin(db=db, exam_id=exam_id, skip=skip, limit=limit)
    # TODO: Calculate max possible score once for the exam
    max_score_query = select(sql_func.sum(models.ExamQuestion.score)).where(models.ExamQuestion.exam_id == exam_id)
    max_score_res = await db.execute(max_score_query)
    max_score_possible = max_score_res.scalar_one_or_none()


    response_list = []
    for attempt in attempts_db:
        user = attempt.user
        response_list.append(schemas.grading.AttemptResultAdmin(
             attempt_id=attempt.id,
             exam_id=attempt.exam_id,
             exam_name="N/A", # Not loaded by default in get_exam_results_admin, could add if needed
             start_time=attempt.start_time,
             submit_time=attempt.submit_time,
             status=attempt.status,
             final_score=attempt.final_score,
             total_possible_score=float(max_score_possible) if max_score_possible else None,
             user_id=attempt.user_id,
             user_username=user.username if user else None,
             user_fullname=user.fullname if user else None,
        ))
    return response_list


@router.get("/results/admin/attempts/{attempt_id}", response_model=schemas.grading.AttemptResultDetail, tags=["Results (Admin)"])
async def get_attempt_details_admin(
    attempt_id: int,
    db: AsyncSession = Depends(deps.get_db),
    admin_user: models.User = Depends(check_view_all_results_permission),
):
    """
    Retrieves detailed results for a specific attempt (admin view).
    Requires 'view_all_results' permission.
    (Similar logic to student view, but accessed by admin)
    """
    # Use the same logic as get_my_attempt_details, but without the user check
    attempt = await crud_exam_attempt.get_attempt_details_for_result(db=db, attempt_id=attempt_id)

    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found.")
    # No user check needed for admin

    if attempt.status not in [schemas.attempt.ExamAttemptStatusEnum.graded, schemas.attempt.ExamAttemptStatusEnum.aborted]:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attempt results are not yet available.")

    exam = attempt.exam
    # Admin view always shows answers? Or respect exam setting? Respect setting for now.
    show_answers = exam.show_answers_after_exam if exam else False

    paper_structure_raw = await crud_exam_attempt.get_attempt_paper_questions(db=db, attempt_id=attempt_id)
    paper_map = {q.id: {"order": idx, "max_score": score} for q, idx, score in paper_structure_raw}

    answer_details = []
    answers_by_qid = {ans.question_id: ans for ans in attempt.answers}

    for q_id, paper_info in sorted(paper_map.items(), key=lambda item: item[1]["order"]):
        answer = answers_by_qid.get(q_id)
        question = answer.question if answer else None
        if not question: continue

        answer_details.append(schemas.grading.AnswerResultDetail(
            question_id=q_id, order_index=paper_info["order"], question_stem=question.stem,
            question_type=question.question_type, max_score=float(paper_info["max_score"]),
            user_answer=answer.user_answer if answer else None,
            is_correct=answer.is_correct if answer else None, score=answer.score if answer else None,
            correct_answer=question.answer if show_answers else None,
            explanation=question.explanation if show_answers else None,
            grading_comments=answer.grading_comments if answer else None,
        ))

    total_possible = sum(p["max_score"] for p in paper_map.values())

    return schemas.grading.AttemptResultDetail(
        attempt_id=attempt.id, exam_id=attempt.exam_id, exam_name=exam.name if exam else "N/A",
        start_time=attempt.start_time, submit_time=attempt.submit_time, status=attempt.status,
        final_score=attempt.final_score, total_possible_score=total_possible,
        answers=answer_details, show_answers_after_exam=show_answers,
    )


@router.get("/results/admin/exams/{exam_id}/export", response_class=StreamingResponse, tags=["Results (Admin)"])
async def export_exam_results_admin(
    exam_id: int,
    db: AsyncSession = Depends(deps.get_db),
    admin_user: models.User = Depends(check_view_all_results_permission),
):
    """
    Exports the results for a specific exam to an Excel file (.xlsx).
    Requires 'view_all_results' permission.
    """
    try:
        file_content: bytes = await excel_processor.generate_results_export(db, exam_id)
        exam = await db.get(models.Exam, exam_id) # Fetch exam for name
        exam_name = exam.name.replace(' ', '_') if exam else f"exam_{exam_id}"
        filename = f"{exam_name}_results_export.xlsx"

        return StreamingResponse(
                io.BytesIO(file_content),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
            )
    except ValueError as ve:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve)) # e.g., Exam not found
    except Exception as e:
         print(f"Unexpected error during results export: {e}")
         # import traceback; traceback.print_exc()
         raise HTTPException(status_code=500, detail=f"An unexpected error occurred during export: {e}")
