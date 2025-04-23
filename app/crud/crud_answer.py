from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.dialects.mysql import insert as mysql_insert # Example for MySQL upsert
# from sqlalchemy.dialects.postgresql import insert as postgres_insert # Example for PostgreSQL upsert
from typing import List, Optional, Any, Sequence

from sqlalchemy.orm import selectinload

from app.db import models
from app.schemas import question as schemas_question, ManualGradeInput, ExamAttemptStatusEnum


class CRUDAnswer:
    async def get(self, db: AsyncSession, *, attempt_id: int, question_id: int) -> Optional[models.Answer]:
        """Get a specific answer for an attempt and question."""
        result = await db.execute(
            select(models.Answer).filter_by(attempt_id=attempt_id, question_id=question_id)
        )
        return result.scalars().first()

    async def get_all_for_attempt(self, db: AsyncSession, *, attempt_id: int) -> List[models.Answer]:
        """Get all answers submitted for a given attempt."""
        result = await db.execute(
            select(models.Answer).filter_by(attempt_id=attempt_id)
        )
        return result.scalars().all()

    async def save_answer(
        self, db: AsyncSession, *, attempt_id: int, question_id: int, user_answer: Any
    ) -> models.Answer:
        """Saves or updates an answer for a specific question in an attempt (Upsert)."""
        # Ensure attempt is still in progress (add check if needed)
        # attempt = await db.get(models.ExamAttempt, attempt_id)
        # if not attempt or attempt.status != schemas_attempt.ExamAttemptStatusEnum.in_progress:
        #     raise ValueError("Cannot save answer for non-active attempt.")

        # Convert complex answers (like lists) to appropriate storage format if needed (e.g., JSON string)
        # SQLAlchemy's JSON type handles Python dicts/lists automatically.
        values = {
            "attempt_id": attempt_id,
            "question_id": question_id,
            "user_answer": user_answer,
            # Reset grading fields on new answer submission? Or keep old grade until regraded? Resetting seems safer.
            "score": None,
            "is_correct": None,
            "grader_id": None,
            "grading_comments": None,
            "graded_at": None,
        }

        # --- Upsert Logic ---
        # This depends heavily on the database dialect.

        # Example for MySQL using ON DUPLICATE KEY UPDATE:
        stmt = mysql_insert(models.Answer).values(**values)
        stmt = stmt.on_duplicate_key_update(
            user_answer=stmt.inserted.user_answer,
            score=None, # Reset score on update
            is_correct=None,
            grader_id=None,
            grading_comments=None,
            graded_at=None,
            # updated_at will be handled by DB default ON UPDATE CURRENT_TIMESTAMP
        )

        # Example for PostgreSQL using ON CONFLICT DO UPDATE:
        # stmt = postgres_insert(models.Answer).values(**values)
        # stmt = stmt.on_conflict_do_update(
        #     index_elements=[models.Answer.attempt_id, models.Answer.question_id], # Constraint name or columns
        #     set_=dict(
        #         user_answer=stmt.excluded.user_answer,
        #         score=None,
        #         is_correct=None,
        #         grader_id=None,
        #         grading_comments=None,
        #         graded_at=None,
        #         # updated_at handled by DB default
        #     )
        # )

        await db.execute(stmt)
        await db.commit()

        # Re-fetch the saved answer to return it
        saved_answer = await self.get(db, attempt_id=attempt_id, question_id=question_id)
        # Should not be None after upsert unless something went very wrong
        if saved_answer is None:
             raise RuntimeError("Failed to retrieve answer after save operation.")
        return saved_answer

    async def apply_manual_grade(
            self, db: AsyncSession, *, answer_id: int, grade_in: ManualGradeInput, grader_id: int
    ) -> Optional[models.Answer]:
        """Applies manual score and comments to a specific answer."""
        answer = await db.get(models.Answer, answer_id)
        if not answer:
            return None

        answer.score = grade_in.score
        answer.is_correct = grade_in.is_correct
        answer.grading_comments = grade_in.comments
        answer.grader_id = grader_id
        answer.graded_at = datetime.now(timezone.utc)

        db.add(answer)
        await db.commit()
        await db.refresh(answer)

        # TODO: After grading an answer, recalculate the attempt's total score?
        # This might be better done in a separate step or background task after all manual grading for an attempt is done.

        return answer

    async def get_answers_needing_manual_grade(
            self, db: AsyncSession, *, exam_id: Optional[int] = None, limit: int = 100, offset: int = 0
    ) -> Sequence[models.Answer]:
        """
        Finds answers that likely require manual grading.
        Criteria:
        - Belongs to a submitted attempt.
        - Question type is short_answer (or others needing manual review).
        - Has not been graded yet (grader_id is null).
        """
        query = (
            select(models.Answer)
            .join(models.ExamAttempt, models.Answer.attempt_id == models.ExamAttempt.id)
            .join(models.Question, models.Answer.question_id == models.Question.id)
            .where(
                models.ExamAttempt.status.in_([
                    ExamAttemptStatusEnum.submitted,
                    ExamAttemptStatusEnum.grading  # Include if grading is multi-stage
                ]),
                models.Question.question_type == schemas_question.QuestionTypeEnum.short_answer,
                # Add other types if needed
                models.Answer.grader_id.is_(None)  # Not yet graded manually
            )
            .options(
                selectinload(models.Answer.attempt).selectinload(models.ExamAttempt.user),  # Load user info
                selectinload(models.Answer.question)  # Load question info
            )
            .order_by(models.Answer.created_at)  # Or by attempt_id, question_id
            .limit(limit)
            .offset(offset)
        )
        if exam_id:
            query = query.where(models.ExamAttempt.exam_id == exam_id)

        result = await db.execute(query)
        return result.scalars().all()


# Instantiate CRUD object
crud_answer = CRUDAnswer()