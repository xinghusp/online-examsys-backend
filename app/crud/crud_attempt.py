from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import update as sql_update, func
from sqlalchemy import func as sql_func
from typing import List, Optional, Sequence, Tuple, Dict, Any
from datetime import datetime, timedelta, timezone

from app.crud.crud_exam import crud_exam
from app.db import models
from app.schemas import attempt as schemas_attempt
from app.schemas import exam as schemas_exam

class CRUDExamAttempt:
    async def get(self, db: AsyncSession, *, attempt_id: int) -> Optional[models.ExamAttempt]:
        """Get a specific attempt by its ID."""
        result = await db.execute(
            select(models.ExamAttempt).filter(models.ExamAttempt.id == attempt_id)
            # Optionally load relations like user, exam if needed frequently
            # .options(selectinload(models.ExamAttempt.user), selectinload(models.ExamAttempt.exam))
        )
        return result.scalars().first()

    async def get_by_user_exam(self, db: AsyncSession, *, user_id: int, exam_id: int) -> Optional[models.ExamAttempt]:
        """Get an attempt for a specific user and exam."""
        result = await db.execute(
            select(models.ExamAttempt)
            .filter(models.ExamAttempt.user_id == user_id, models.ExamAttempt.exam_id == exam_id)
        )
        return result.scalars().first()

    async def get_active_attempt(self, db: AsyncSession, *, user_id: int, exam_id: int) -> Optional[models.ExamAttempt]:
        """Get an attempt for a user/exam only if it's 'in_progress'."""
        result = await db.execute(
            select(models.ExamAttempt)
            .filter(
                models.ExamAttempt.user_id == user_id,
                models.ExamAttempt.exam_id == exam_id,
                models.ExamAttempt.status == schemas_attempt.ExamAttemptStatusEnum.in_progress
            )
        )
        return result.scalars().first()

    async def create_or_get_pending(self, db: AsyncSession, *, user_id: int, exam_id: int) -> models.ExamAttempt:
        """Gets an existing attempt or creates a new one in 'pending' status."""
        attempt = await self.get_by_user_exam(db=db, user_id=user_id, exam_id=exam_id)
        if not attempt:
            # Ensure exam exists and user is participant (add checks if needed)
            db_obj = models.ExamAttempt(user_id=user_id, exam_id=exam_id, status=schemas_attempt.ExamAttemptStatusEnum.pending)
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            return db_obj
        # Should not return attempts that are already finished/graded/aborted if called for starting
        if attempt.status in [schemas_attempt.ExamAttemptStatusEnum.submitted, schemas_attempt.ExamAttemptStatusEnum.graded, schemas_attempt.ExamAttemptStatusEnum.aborted]:
             raise ValueError("Exam attempt has already been completed.")
        return attempt


    async def start_attempt(self, db: AsyncSession, *, attempt: models.ExamAttempt, duration_minutes: int) -> models.ExamAttempt:
        """Marks an attempt as 'in_progress', sets start and calculated end times."""
        if attempt.status == schemas_attempt.ExamAttemptStatusEnum.in_progress:
            return attempt # Already started

        if attempt.status != schemas_attempt.ExamAttemptStatusEnum.pending:
            raise ValueError(f"Cannot start attempt with status '{attempt.status.value}'.")

        now = datetime.now(timezone.utc)
        attempt.start_time = now
        attempt.calculated_end_time = now + timedelta(minutes=duration_minutes)
        attempt.status = schemas_attempt.ExamAttemptStatusEnum.in_progress
        attempt.last_heartbeat = now # Initial heartbeat

        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)
        return attempt

    async def submit_attempt(self, db: AsyncSession, *, attempt: models.ExamAttempt) -> models.ExamAttempt:
        """Marks an attempt as 'submitted' and records submit time."""
        if attempt.status != schemas_attempt.ExamAttemptStatusEnum.in_progress:
            # Allow resubmitting? Probably not. Allow submitting if aborted? Maybe.
             raise ValueError(f"Cannot submit attempt with status '{attempt.status.value}'.")

        now = datetime.now(timezone.utc)
        # Check if submission is late based on calculated_end_time
        # Decide policy: reject late submission or mark as late? Mark as submitted for now.
        # if attempt.calculated_end_time and now > attempt.calculated_end_time:
        #     # Handle late submission - maybe change status differently?
        #     pass

        attempt.submit_time = now
        attempt.status = schemas_attempt.ExamAttemptStatusEnum.submitted
        # Status might change to 'grading' immediately if auto-grading starts

        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)
        return attempt

    async def update_heartbeat(self, db: AsyncSession, *, attempt_id: int) -> bool:
        """Updates the last_heartbeat timestamp for an active attempt."""
        now = datetime.now(timezone.utc)
        stmt = (
            sql_update(models.ExamAttempt)
            .where(
                models.ExamAttempt.id == attempt_id,
                models.ExamAttempt.status == schemas_attempt.ExamAttemptStatusEnum.in_progress
            )
            .values(last_heartbeat=now)
            .execution_options(synchronize_session=False) # Important for async update without fetch
        )
        result = await db.execute(stmt)
        if result.rowcount > 0:
            await db.commit() # Commit the heartbeat update
            return True
        await db.rollback() # Rollback if attempt not found or not in progress
        return False

    # --- Methods related to paper generation for random_individual ---
    # These would likely involve fetching question IDs based on rules and creating ExamAttemptPaper entries.
    async def generate_individual_paper(self, db: AsyncSession, *, attempt: models.ExamAttempt, rules: List[schemas_exam.RandomQuestionParameter]):
        """Generates and saves the unique paper for a random_individual attempt."""
        # 1. Check if paper already exists for this attempt
        existing_paper = await db.execute(select(models.ExamAttemptPaper).filter_by(attempt_id=attempt.id).limit(1))
        if existing_paper.scalar_one_or_none():
            print(f"Paper already generated for attempt {attempt.id}")
            return # Already generated

        # 2. Fetch question IDs based on rules (complex logic)
        # This requires querying questions based on chapter_ids, type, and applying random sampling (e.g., func.rand() or similar depending on DB)
        # Example placeholder logic:
        selected_questions = [] # List of tuples (question_id, score)
        order_idx = 0
        for rule in rules:
            # Construct query based on rule.chapter_ids, rule.question_type
            query = select(models.Question.id).join(models.Chapter).filter(
                models.Chapter.id.in_(rule.chapter_ids)
            )
            if rule.question_type:
                 query = query.filter(models.Question.question_type == rule.question_type)

            # Add randomization and limit
            # The specific function depends on the database (e.g., RAND() for MySQL, RANDOM() for PostgreSQL)
            # query = query.order_by(func.random()).limit(rule.count) # Example for PostgreSQL
            query = query.order_by(func.rand()).limit(rule.count) # Example for MySQL

            result = await db.execute(query)
            q_ids = result.scalars().all()

            if len(q_ids) < rule.count:
                 # Handle case where not enough questions are available
                 print(f"Warning: Not enough questions found for rule {rule}. Found {len(q_ids)}, needed {rule.count}")
                 # Decide policy: fail, proceed with fewer, etc.

            for q_id in q_ids:
                 selected_questions.append({"question_id": q_id, "score": rule.score_per_question, "order_index": order_idx})
                 order_idx += 1

        # 3. Create ExamAttemptPaper entries
        if selected_questions:
            paper_entries = [models.ExamAttemptPaper(attempt_id=attempt.id, **q_data) for q_data in selected_questions]
            db.add_all(paper_entries)
            # No commit here, should be committed along with attempt start or creation

        print(f"Generated paper with {len(selected_questions)} questions for attempt {attempt.id}")


    async def get_attempt_paper_questions(self, db: AsyncSession, *, attempt_id: int) -> Sequence[Tuple[models.Question, int, float]]:
        """Fetches the actual questions for a specific attempt's paper (manual, unified, or individual)."""
        attempt = await db.get(models.ExamAttempt, attempt_id, options=[selectinload(models.ExamAttempt.exam)])
        if not attempt:
            return []

        exam = attempt.exam
        if not exam: # Should not happen if DB constraints are set
            return []

        if exam.paper_generation_mode == schemas_exam.PaperGenerationModeEnum.random_individual:
            # Fetch from ExamAttemptPaper
            stmt = (
                select(models.Question, models.ExamAttemptPaper.order_index, models.ExamAttemptPaper.score)
                .join(models.ExamAttemptPaper, models.Question.id == models.ExamAttemptPaper.question_id)
                .filter(models.ExamAttemptPaper.attempt_id == attempt_id)
                .order_by(models.ExamAttemptPaper.order_index)
            )
        else: # Manual or Random Unified - Fetch from ExamQuestion
             stmt = (
                select(models.Question, models.ExamQuestion.order_index, models.ExamQuestion.score)
                .join(models.ExamQuestion, models.Question.id == models.ExamQuestion.question_id)
                .filter(models.ExamQuestion.exam_id == exam.id)
                .order_by(models.ExamQuestion.order_index)
            )

        result = await db.execute(stmt)
        # Returns sequence of tuples: (Question Object, order_index, score)
        return result.all()

    async def update_status(self, db: AsyncSession, *, attempt_id: int,
                            new_status: schemas_attempt.ExamAttemptStatusEnum) -> Optional[models.ExamAttempt]:
        """Updates the status of an attempt."""
        attempt = await db.get(models.ExamAttempt, attempt_id)
        if not attempt:
            return None
        # Add validation if needed (e.g., status transition rules)
        attempt.status = new_status
        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)
        return attempt

    async def calculate_and_save_final_score(self, db: AsyncSession, *, attempt_id: int) -> Optional[
        models.ExamAttempt]:
        """Calculates the sum of scores from Answers, updates ExamAttempt final_score and status."""
        attempt = await db.get(models.ExamAttempt, attempt_id)
        if not attempt:
            return None

        # Ensure all relevant answers *have* a score (or handle nulls)
        # This assumes auto-grading + manual grading are complete.
        sum_query = select(sql_func.sum(models.Answer.score)).where(
            models.Answer.attempt_id == attempt_id,
            models.Answer.score.is_not(None)  # Only sum non-null scores
        )
        total_score_res = await db.execute(sum_query)
        total_score = total_score_res.scalar_one_or_none() or 0.0

        attempt.final_score = float(total_score)
        attempt.status = schemas_attempt.ExamAttemptStatusEnum.graded  # Mark as graded

        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)
        return attempt

    async def get_student_results(
            self, db: AsyncSession, *, user_id: int, skip: int = 0, limit: int = 100
    ) -> Sequence[models.ExamAttempt]:
        """Gets a student's completed exam attempts."""
        query = (
            select(models.ExamAttempt)
            .options(selectinload(models.ExamAttempt.exam))  # Load exam name
            .where(
                models.ExamAttempt.user_id == user_id,
                models.ExamAttempt.status.in_([
                    schemas_attempt.ExamAttemptStatusEnum.submitted,  # Include submitted but not yet graded?
                    schemas_attempt.ExamAttemptStatusEnum.grading,
                    schemas_attempt.ExamAttemptStatusEnum.graded,
                    schemas_attempt.ExamAttemptStatusEnum.aborted
                ])
            )
            .order_by(models.ExamAttempt.submit_time.desc().nulls_last(), models.ExamAttempt.start_time.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        return result.scalars().all()

    async def get_attempt_details_for_result(self, db: AsyncSession, *, attempt_id: int) -> Optional[
        models.ExamAttempt]:
        """Gets attempt details including exam settings and all related answers with questions."""
        attempt = await db.get(
            models.ExamAttempt,
            attempt_id,
            options=[
                selectinload(models.ExamAttempt.exam),  # Load exam settings
                selectinload(models.ExamAttempt.answers).options(  # Load answers
                    selectinload(models.Answer.question)  # And their questions
                )
            ]
        )
        return attempt

    async def get_exam_results_admin(
            self, db: AsyncSession, *, exam_id: int, skip: int = 0, limit: int = 100
    ) -> Sequence[models.ExamAttempt]:
        """Gets completed attempts for an exam for admin view."""
        query = (
            select(models.ExamAttempt)
            .options(
                selectinload(models.ExamAttempt.user),  # Load user info
                # selectinload(models.ExamAttempt.exam) # Exam info already known via exam_id filter
            )
            .where(
                models.ExamAttempt.exam_id == exam_id,
                models.ExamAttempt.status.in_([
                    schemas_attempt.ExamAttemptStatusEnum.submitted,
                    schemas_attempt.ExamAttemptStatusEnum.grading,
                    schemas_attempt.ExamAttemptStatusEnum.graded,
                    schemas_attempt.ExamAttemptStatusEnum.aborted
                ])
            )
            .order_by(models.ExamAttempt.submit_time.desc().nulls_last(), models.ExamAttempt.user_id)
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        return result.scalars().all()


async def get_exam_statistics_admin(self, db: AsyncSession, *, exam_id: int) -> Dict[str, Any]:
    """Calculates statistics for an exam's results, including max possible score for all modes."""

    # Fetch the exam to determine mode and rules
    exam = await db.get(models.Exam, exam_id)
    if not exam:
        # Or raise an error? Returning empty stats might be acceptable too.
        return {
            "participant_count": 0,
            "attempt_count": 0,
            "average_score": None,
            "max_score_possible": None,
        }

    # Calculate basic stats (count, average) from graded attempts
    stats_query = select(
        sql_func.count(models.ExamAttempt.id),
        sql_func.avg(models.ExamAttempt.final_score),
    ).where(
        models.ExamAttempt.exam_id == exam_id,
        models.ExamAttempt.status == schemas_attempt.ExamAttemptStatusEnum.graded,
        models.ExamAttempt.final_score.is_not(None)
    )
    stats_res = await db.execute(stats_query)
    attempt_count, average_score = stats_res.first() or (0, None)

    # --- Calculate Max Possible Score based on Mode ---
    max_score_possible: Optional[float] = None
    if exam.paper_generation_mode in [schemas_exam.PaperGenerationModeEnum.manual,
                                      schemas_exam.PaperGenerationModeEnum.random_unified]:
        # Sum scores from the fixed paper definition in ExamQuestion
        max_score_query = select(sql_func.sum(models.ExamQuestion.score)).where(models.ExamQuestion.exam_id == exam_id)
        max_score_res = await db.execute(max_score_query)
        max_score_possible = max_score_res.scalar_one_or_none()
    elif exam.paper_generation_mode == schemas_exam.PaperGenerationModeEnum.random_individual:
        # Calculate sum from the stored random rules
        rules_data = getattr(exam, 'random_rules_json', None)
        if rules_data:
            try:
                # Validate and parse the rules from JSON
                rules_obj = schemas_exam.ExamPaperRandomInput.model_validate(rules_data)
                # Calculate total score: sum(rule.count * rule.score_per_question)
                total_score_from_rules = sum(
                    rule.count * rule.score_per_question for rule in rules_obj.rules
                )
                max_score_possible = total_score_from_rules
            except Exception as e:
                # Log error: Failed to parse or calculate from rules
                print(f"Error calculating max score from rules for exam {exam_id}: {e}")
                max_score_possible = None  # Indicate failure to calculate
        else:
            # Log warning: Rules missing for random_individual exam
            print(f"Warning: Random rules missing for individual exam {exam_id}, cannot calculate max score.")
            max_score_possible = None

    # Get total assigned participants
    participant_count = await crud_exam.get_participant_count(db=db, exam_id=exam_id)

    return {
        "participant_count": participant_count,
        "attempt_count": attempt_count or 0,
        "average_score": float(average_score) if average_score is not None else None,
        "max_score_possible": float(max_score_possible) if max_score_possible is not None else None,
    }


# Instantiate CRUD object
crud_exam_attempt = CRUDExamAttempt()
