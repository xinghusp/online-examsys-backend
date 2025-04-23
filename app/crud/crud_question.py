from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import func, update as sql_update, delete as sql_delete
from typing import List, Optional, Any, Dict

from app.db import models
from app.schemas import question as schemas # Use alias for clarity

class CRUDQuestionLib:
    async def get(self, db: AsyncSession, *, id: int) -> Optional[models.QuestionLib]:
        """Get a question library by ID, loading its chapters and their question counts."""
        result = await db.execute(
            select(models.QuestionLib)
            .options(
                selectinload(models.QuestionLib.chapters).options(
                    # joinedload(models.Chapter.questions) # Avoid loading all questions
                    # Instead, we'll query counts separately or rely on a trigger
                )
            )
            .filter(models.QuestionLib.id == id)
        )
        lib = result.scalars().first()
        # Manually load question counts for chapters if not using triggers/denormalization
        # This can be slow if there are many chapters
        # if lib:
        #     for chapter in lib.chapters:
        #         count_res = await db.execute(select(func.count(models.Question.id)).filter(models.Question.chapter_id == chapter.id))
        #         chapter.question_count = count_res.scalar_one()
        return lib

    async def get_multi(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[models.QuestionLib]:
        """Get multiple question libraries with pagination."""
        # Does not load chapters by default for performance
        result = await db.execute(
            select(models.QuestionLib)
            .offset(skip)
            .limit(limit)
            .order_by(models.QuestionLib.name)
        )
        return result.scalars().all()

    async def create(self, db: AsyncSession, *, obj_in: schemas.QuestionLibCreate, creator_id: Optional[int] = None) -> models.QuestionLib:
        """Create a new question library."""
        db_obj = models.QuestionLib(**obj_in.model_dump(), creator_id=creator_id)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self, db: AsyncSession, *, db_obj: models.QuestionLib, obj_in: schemas.QuestionLibUpdate
    ) -> models.QuestionLib:
        """Update a question library."""
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def remove(self, db: AsyncSession, *, id: int) -> Optional[models.QuestionLib]:
        """Delete a question library and its chapters/questions."""
        # Cascade delete should handle chapters and questions due to model relationships
        obj = await db.get(models.QuestionLib, id) # Use db.get for simple PK lookup
        if obj:
            await db.delete(obj)
            await db.commit()
        return obj

    async def increment_question_count(self, db: AsyncSession, *, lib_id: int, count: int = 1):
         """Increment the question count for a library."""
         stmt = (
             sql_update(models.QuestionLib)
             .where(models.QuestionLib.id == lib_id)
             .values(question_count=models.QuestionLib.question_count + count)
             .execution_options(synchronize_session="fetch") # Important for SQLAlchemy < 2.0 or specific scenarios
         )
         await db.execute(stmt)
         # No commit needed here if called within a transaction that will commit later

    async def decrement_question_count(self, db: AsyncSession, *, lib_id: int, count: int = 1):
         """Decrement the question count for a library."""
         stmt = (
             sql_update(models.QuestionLib)
             .where(models.QuestionLib.id == lib_id, models.QuestionLib.question_count >= count) # Prevent going below zero
             .values(question_count=models.QuestionLib.question_count - count)
             .execution_options(synchronize_session="fetch")
         )
         await db.execute(stmt)

    async def recalculate_question_count(self, db: AsyncSession, *, lib_id: int):
        """Recalculate the total question count for a library (more robust)."""
        count_query = select(func.count(models.Question.id))\
            .join(models.Chapter)\
            .where(models.Chapter.question_lib_id == lib_id)
        total_count_res = await db.execute(count_query)
        total_count = total_count_res.scalar_one()

        stmt = sql_update(models.QuestionLib)\
            .where(models.QuestionLib.id == lib_id)\
            .values(question_count=total_count)\
            .execution_options(synchronize_session="fetch")
        await db.execute(stmt)
        # No commit needed here if called within a transaction that will commit later
        return total_count


class CRUDChapter:
    async def get(self, db: AsyncSession, *, id: int) -> Optional[models.Chapter]:
        """Get a chapter by ID."""
        # Avoid loading all questions by default
        result = await db.execute(select(models.Chapter).filter(models.Chapter.id == id))
        chapter = result.scalars().first()
        # if chapter: # Manually load count if needed
        #     count_res = await db.execute(select(func.count(models.Question.id)).filter(models.Question.chapter_id == chapter.id))
        #     chapter.question_count = count_res.scalar_one()
        return chapter

    async def get_multi_by_lib(
        self, db: AsyncSession, *, lib_id: int, skip: int = 0, limit: int = 100
    ) -> List[models.Chapter]:
        """Get multiple chapters for a specific library."""
        result = await db.execute(
            select(models.Chapter)
            .filter(models.Chapter.question_lib_id == lib_id)
            .order_by(models.Chapter.order_index, models.Chapter.name)
            .offset(skip)
            .limit(limit)
        )
        chapters = result.scalars().all()
        # Manually load counts if needed
        # for chapter in chapters:
        #      count_res = await db.execute(select(func.count(models.Question.id)).filter(models.Question.chapter_id == chapter.id))
        #      chapter.question_count = count_res.scalar_one()
        return chapters

    async def create(self, db: AsyncSession, *, obj_in: schemas.ChapterCreate) -> models.Chapter:
        """Create a new chapter."""
        # Check if lib exists
        lib = await db.get(models.QuestionLib, obj_in.question_lib_id)
        if not lib:
            raise ValueError(f"Question Library with ID {obj_in.question_lib_id} not found.")
        db_obj = models.Chapter(**obj_in.model_dump())
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self, db: AsyncSession, *, db_obj: models.Chapter, obj_in: schemas.ChapterUpdate
    ) -> models.Chapter:
        """Update a chapter."""
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def remove(self, db: AsyncSession, *, id: int) -> Optional[models.Chapter]:
        """Delete a chapter and its questions."""
        # Need to update question count in the parent library
        chapter = await db.get(models.Chapter, id, options=[joinedload(models.Chapter.questions)]) # Load questions to count them
        if chapter:
            lib_id = chapter.question_lib_id
            num_questions = len(chapter.questions)

            await db.delete(chapter) # Cascade delete should handle questions in DB

            # Decrement count in library (do this before commit if possible)
            if num_questions > 0:
                await crud_question_lib.decrement_question_count(db=db, lib_id=lib_id, count=num_questions)

            await db.commit() # Commit deletion and count update together
            return chapter
        return None

    async def get_question_count(self, db: AsyncSession, *, chapter_id: int) -> int:
         """Get the number of questions in a chapter."""
         count_query = select(func.count(models.Question.id)).filter(models.Question.chapter_id == chapter_id)
         result = await db.execute(count_query)
         count = result.scalar_one_or_none()
         return count if count is not None else 0


class CRUDQuestion:
    async def get(self, db: AsyncSession, *, id: int) -> Optional[models.Question]:
        """Get a question by ID."""
        result = await db.execute(select(models.Question).filter(models.Question.id == id))
        return result.scalars().first()

    async def get_multi_by_chapter(
        self, db: AsyncSession, *, chapter_id: int, skip: int = 0, limit: int = 100
    ) -> List[models.Question]:
        """Get multiple questions for a specific chapter."""
        result = await db.execute(
            select(models.Question)
            .filter(models.Question.chapter_id == chapter_id)
            .order_by(models.Question.id) # Or some other logical order
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def create(self, db: AsyncSession, *, obj_in: schemas.QuestionCreate, creator_id: Optional[int] = None) -> models.Question:
        """Create a new question."""
        # Check if chapter exists and get its library ID
        chapter = await db.get(models.Chapter, obj_in.chapter_id)
        if not chapter:
            raise ValueError(f"Chapter with ID {obj_in.chapter_id} not found.")
        lib_id = chapter.question_lib_id

        # Prepare data, potentially serializing options/answer/strategy to JSON strings if model uses JSON type
        # SQLAlchemy 2.0 handles JSON types better, so direct assignment might work
        db_obj_data = obj_in.model_dump()
        db_obj_data["creator_id"] = creator_id

        # Ensure complex types are handled correctly for the model (SQLAlchemy handles dict->JSON)
        db_obj = models.Question(**db_obj_data)
        db.add(db_obj)

        # Increment count in library (do this before commit)
        await crud_question_lib.increment_question_count(db=db, lib_id=lib_id)

        await db.commit() # Commit new question and count update
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self, db: AsyncSession, *, db_obj: models.Question, obj_in: schemas.QuestionUpdate
    ) -> models.Question:
        """Update a question."""
        # Validate update data if needed (e.g., if type changes, options/answer must match)
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def remove(self, db: AsyncSession, *, id: int) -> Optional[models.Question]:
        """Delete a question."""
        # Need to update question count in the parent library
        question = await db.get(models.Question, id, options=[joinedload(models.Question.chapter)]) # Load chapter to get lib_id
        if question:
            lib_id = question.chapter.question_lib_id

            await db.delete(question)

            # Decrement count in library (before commit)
            await crud_question_lib.decrement_question_count(db=db, lib_id=lib_id)

            await db.commit() # Commit deletion and count update
            return question
        return None

# Instantiate CRUD objects
crud_question_lib = CRUDQuestionLib()
crud_chapter = CRUDChapter()
crud_question = CRUDQuestion()