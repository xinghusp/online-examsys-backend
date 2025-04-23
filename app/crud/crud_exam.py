from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import delete as sql_delete, func
from sqlalchemy import insert as sql_insert
from typing import List, Optional, Sequence, Set, Tuple, Dict

from app.db import models
from app.schemas import exam as schemas_exam # Alias
from app.schemas import question as schemas_question
from app.crud.crud_question import crud_question # Need this for fetching questions


# --- Helper to resolve users from participants ---
async def _resolve_participant_user_ids(db: AsyncSession, exam_id: int) -> Set[int]:
    """Gets the set of all individual user IDs assigned to an exam (directly or via groups)."""
    participant_rows = await db.execute(
        select(models.ExamParticipant.user_id, models.ExamParticipant.group_id)
        .filter_by(exam_id=exam_id)
    )
    user_ids: Set[int] = set()
    group_ids: List[int] = []
    for p_user_id, p_group_id in participant_rows.all():
        if p_user_id:
            user_ids.add(p_user_id)
        if p_group_id:
            group_ids.append(p_group_id)

    if group_ids:
        # Fetch users belonging to these groups
        # Ensure User.groups relationship is usable or use the association table directly
        group_members_query = (
            select(models.user_groups_table.c.user_id)
            .where(models.user_groups_table.c.group_id.in_(group_ids))
            .distinct()
        )
        group_members_res = await db.execute(group_members_query)
        user_ids.update(group_members_res.scalars().all())

    return user_ids

class CRUDExam:
    async def get(self, db: AsyncSession, *, id: int) -> Optional[models.Exam]:
        """Get an exam by ID, optionally loading relations."""
        # Decide which relations to load by default for a single GET
        # Loading participants and questions might be heavy. Load them separately?
        # For now, load participants but not detailed questions.
        result = await db.execute(
            select(models.Exam)
            .options(
                selectinload(models.Exam.participants), # Load participant links
                # selectinload(models.Exam.questions).joinedload(models.ExamQuestion.question) # Load full questions (maybe too much)
                selectinload(models.Exam.questions) # Load just the ExamQuestion links
            )
            .filter(models.Exam.id == id)
        )
        return result.scalars().first()

    async def get_multi(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100, status: Optional[schemas_exam.ExamStatusEnum] = None
    ) -> Sequence[models.Exam]:
        """Get multiple exams with pagination and optional status filter."""
        query = select(models.Exam)
        if status:
            query = query.filter(models.Exam.status == status)
        query = query.order_by(models.Exam.start_time.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        # Does not load relations for list view
        return result.scalars().all()
    async def create(self, db: AsyncSession, *, obj_in: schemas_exam.ExamCreate, creator_id: int) -> models.Exam:
        """Create a new exam. Saves rules/manual Qs. Paper generation happens on publish."""
        exam_data = obj_in.model_dump(exclude={"participants", "manual_questions", "random_rules"})
        db_obj = models.Exam(**exam_data, creator_id=creator_id, status=schemas_exam.ExamStatusEnum.draft)

        if obj_in.random_rules and obj_in.paper_generation_mode != schemas_exam.PaperGenerationModeEnum.manual:
             # Assuming Exam model has 'random_rules_json' field
            setattr(db_obj, 'random_rules_json', obj_in.random_rules.model_dump())

        db.add(db_obj)
        await db.flush([db_obj]) # Flush to get ID

        # Add participants and manual questions to session
        if obj_in.participants:
            await self._sync_participants(db, exam=db_obj, assignment=obj_in.participants, commit=False, handle_paper_delta=False) # No delta handling on create
        if obj_in.paper_generation_mode == schemas_exam.PaperGenerationModeEnum.manual and obj_in.manual_questions:
             await self._sync_manual_questions(db, exam=db_obj, questions_in=obj_in.manual_questions, commit=False)

        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self, db: AsyncSession, *, db_obj: models.Exam, obj_in: schemas_exam.ExamUpdate
    ) -> models.Exam:
        """Update an exam. Triggers ALL paper generation on publish."""
        original_status = db_obj.status
        update_data = obj_in.model_dump(exclude_unset=True, exclude={"participants", "manual_questions", "random_rules"})
        new_status = update_data.get("status")

        # --- Status/Mode Change Restrictions ---
        if original_status not in [schemas_exam.ExamStatusEnum.draft]:
             # More restrictive: cannot change key fields after publishing
             immutable_fields = {"start_time", "end_time", "duration_minutes", "paper_generation_mode", "manual_questions", "random_rules"}
             update_data_keys = set(update_data.keys()) | \
                                ({ "manual_questions" } if obj_in.manual_questions is not None else set()) | \
                                ({ "random_rules" } if obj_in.random_rules is not None else set())
             if any(field in update_data_keys for field in immutable_fields):
                  raise ValueError(f"Cannot modify fields {immutable_fields} after exam is published.")
        elif 'paper_generation_mode' in update_data and db_obj.paper_generation_mode != update_data['paper_generation_mode']:
             # Allow changing mode only if draft
             pass # Allowed if draft

        # --- Store updated rules if draft ---
        if obj_in.random_rules is not None and db_obj.paper_generation_mode != schemas_exam.PaperGenerationModeEnum.manual:
             if original_status != schemas_exam.ExamStatusEnum.draft:
                  raise ValueError("Cannot change random rules after exam is published.")
             setattr(db_obj, 'random_rules_json', obj_in.random_rules.model_dump())

        # --- Handle Participant Updates (triggers delta paper generation if published) ---
        participant_changes = None
        if obj_in.participants is not None:
            participant_changes = await self._sync_participants(
                db,
                exam=db_obj,
                assignment=obj_in.participants,
                commit=False,
                handle_paper_delta=(original_status == schemas_exam.ExamStatusEnum.published) # Only handle delta if already published
            )

        # --- Handle Manual Question Updates (only if draft) ---
        if obj_in.manual_questions is not None and db_obj.paper_generation_mode == schemas_exam.PaperGenerationModeEnum.manual:
            if original_status != schemas_exam.ExamStatusEnum.draft:
                 raise ValueError("Cannot change manual questions after exam is published.")
            await self._sync_manual_questions(db, exam=db_obj, questions_in=obj_in.manual_questions, commit=False)

        # --- Update Basic Fields ---
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        # --- Trigger Full Paper Generation on Publish ---
        if (new_status == schemas_exam.ExamStatusEnum.published and
            original_status == schemas_exam.ExamStatusEnum.draft):
            try:
                 await self._generate_all_papers(db=db, exam=db_obj, commit=False)
            except Exception as e:
                 await db.rollback() # Rollback changes if paper generation fails
                 raise ValueError(f"Failed to generate exam paper(s): {e}")

        db.add(db_obj)
        await db.commit() # Commit all updates
        await db.refresh(db_obj)
        # Refresh relations if they were modified
        await db.refresh(db_obj, attribute_names=['participants', 'questions'])
        return db_obj

    async def _generate_all_papers(self, db: AsyncSession, *, exam: models.Exam, commit: bool = True):
        """Generates paper(s) based on exam mode (Unified or Individual). Called on Publish."""
        print(f"Generating paper(s) for Exam {exam.id} (Mode: {exam.paper_generation_mode.value})")
        # Clear any previously generated papers for this exam (e.g., if re-publishing a draft)
        if exam.paper_generation_mode == schemas_exam.PaperGenerationModeEnum.random_individual:
             await db.execute(sql_delete(models.PreGeneratedPaper).filter_by(exam_id=exam.id))
        else: # Manual or Unified
             await db.execute(sql_delete(models.ExamQuestion).filter_by(exam_id=exam.id))

        if exam.paper_generation_mode == schemas_exam.PaperGenerationModeEnum.random_unified:
            rules_data = getattr(exam, 'random_rules_json', None)
            if not rules_data: raise ValueError("Missing random rules for unified generation.")
            rules_obj = schemas_exam.ExamPaperRandomInput.model_validate(rules_data)
            await self.generate_unified_paper(db=db, exam=exam, rules=rules_obj.rules, commit=commit) # Saves to ExamQuestion

        elif exam.paper_generation_mode == schemas_exam.PaperGenerationModeEnum.random_individual:
            rules_data = getattr(exam, 'random_rules_json', None)
            if not rules_data: raise ValueError("Missing random rules for individual generation.")
            rules_obj = schemas_exam.ExamPaperRandomInput.model_validate(rules_data)
            await self._generate_individual_papers_for_all_users(db=db, exam=exam, rules=rules_obj.rules, commit=commit) # Saves to PreGeneratedPaper

        elif exam.paper_generation_mode == schemas_exam.PaperGenerationModeEnum.manual:
             # Manual questions should have been synced already during create/update draft.
             # Verify they exist?
             count_q = await db.scalar(select(func.count(models.ExamQuestion.id)).filter_by(exam_id=exam.id))
             if count_q == 0:
                  raise ValueError("Manual exam has no questions defined.")
             print(f"Manual paper verified for Exam {exam.id} with {count_q} questions.")


    async def _generate_individual_papers_for_all_users(self, db: AsyncSession, *, exam: models.Exam, rules: List[schemas_exam.RandomQuestionParameter], commit: bool = True):
        """Generates unique papers for all assigned users and saves to PreGeneratedPaper."""
        user_ids = await _resolve_participant_user_ids(db, exam.id)
        if not user_ids:
            print(f"Warning: No participants assigned to exam {exam.id}. Skipping individual paper generation.")
            return

        print(f"Generating individual papers for {len(user_ids)} users for exam {exam.id}...")
        all_paper_data = []
        # Consider running generation in parallel for performance?
        # For simplicity, run sequentially for now.
        for user_id in user_ids:
             try:
                 paper_questions = await self._generate_single_individual_paper(db, rules=rules) # Pass db if needed for selection
                 for q_data in paper_questions:
                      all_paper_data.append({
                          "exam_id": exam.id,
                          "user_id": user_id,
                          **q_data # question_id, score, order_index
                      })
             except Exception as e:
                 # Log error for specific user, but continue for others? Or fail fast?
                 print(f"Error generating paper for user {user_id}, exam {exam.id}: {e}")
                 # Decide if we should raise the error or just log and skip user

        if all_paper_data:
            # Use bulk insert for performance
            # For SQLAlchemy Core (faster):
            await db.execute(sql_insert(models.PreGeneratedPaper), all_paper_data)
            # For SQLAlchemy ORM (might be slightly slower but uses ORM events if any):
            # db.add_all([models.PreGeneratedPaper(**data) for data in all_paper_data])
            print(f"Bulk inserting {len(all_paper_data)} rows into PreGeneratedPaper for exam {exam.id}")
        else:
             # This might happen if _generate_single_individual_paper fails for all users or returns empty
             raise ValueError(f"Failed to generate any individual paper questions for exam {exam.id}.")


        if commit:
            await db.commit()

    async def _generate_single_individual_paper(self, db: AsyncSession, *, rules: List[schemas_exam.RandomQuestionParameter]) -> List[Dict]:
        """Generates a single random paper based on rules. Returns list of dicts."""
        selected_questions_output = []
        order_idx = 0
        question_ids_selected = set()

        for rule in rules:
            query = select(models.Question.id).join(models.Chapter).filter(
                models.Chapter.id.in_(rule.chapter_ids),
                models.Question.id.notin_(question_ids_selected)
            )
            if rule.question_type:
                 query = query.filter(models.Question.question_type == rule.question_type)

            query = query.order_by(func.rand()).limit(rule.count)

            result = await db.execute(query) # Execute query to fetch IDs
            q_ids = result.scalars().all()

            if len(q_ids) < rule.count:
                 print(f"Warning: Not enough unique questions found for rule {rule}. Found {len(q_ids)}, needed {rule.count}")

            for q_id in q_ids:
                 selected_questions_output.append({
                     "question_id": q_id,
                     "score": rule.score_per_question,
                     "order_index": order_idx
                 })
                 question_ids_selected.add(q_id)
                 order_idx += 1

        if not selected_questions_output:
             raise ValueError("No questions could be selected based on the provided rules.")

        return selected_questions_output


    async def _sync_participants(
        self, db: AsyncSession, *, exam: models.Exam, assignment: schemas_exam.ParticipantAssignment, commit: bool = True, handle_paper_delta: bool = False
    ) -> Optional[Tuple[Set[int], Set[int]]]:
        """Helper to replace participants. If handle_paper_delta is True, generates/removes individual papers."""

        current_users = set()
        if handle_paper_delta: # Only fetch current users if we need to calculate delta
             current_users = await _resolve_participant_user_ids(db, exam.id)

        # 1. Clear existing participants for this exam
        await db.execute(sql_delete(models.ExamParticipant).where(models.ExamParticipant.exam_id == exam.id))

        # 2. Add new participants
        new_participants_db = []
        new_user_ids_direct = set(assignment.user_ids)
        new_group_ids = set(assignment.group_ids)

        if new_user_ids_direct:
            new_participants_db.extend([models.ExamParticipant(exam_id=exam.id, user_id=uid) for uid in new_user_ids_direct])
        if new_group_ids:
            new_participants_db.extend([models.ExamParticipant(exam_id=exam.id, group_id=gid) for gid in new_group_ids])

        if new_participants_db:
            db.add_all(new_participants_db)

        # 3. Handle paper delta if needed (after participant changes are in session/DB)
        added_users = set()
        removed_users = set()
        if handle_paper_delta and exam.paper_generation_mode == schemas_exam.PaperGenerationModeEnum.random_individual:
             # Must flush participant changes before resolving new user list
             await db.flush(new_participants_db)
             new_users = await _resolve_participant_user_ids(db, exam.id) # Resolve again after changes

             added_users = new_users - current_users
             removed_users = current_users - new_users

             if added_users:
                 print(f"Handling added users for exam {exam.id}: {added_users}")
                 # Fetch rules
                 rules_data = getattr(exam, 'random_rules_json', None)
                 if not rules_data: raise ValueError("Missing random rules for delta generation.")
                 rules_obj = schemas_exam.ExamPaperRandomInput.model_validate(rules_data)
                 # Generate papers for added users
                 added_paper_data = []
                 for user_id in added_users:
                     try:
                         paper_questions = await self._generate_single_individual_paper(db, rules=rules_obj.rules)
                         for q_data in paper_questions:
                             added_paper_data.append({"exam_id": exam.id, "user_id": user_id, **q_data})
                     except Exception as e:
                         print(f"Error generating delta paper for added user {user_id}, exam {exam.id}: {e}")
                 if added_paper_data:
                     await db.execute(sql_insert(models.PreGeneratedPaper), added_paper_data)

             if removed_users:
                 print(f"Handling removed users for exam {exam.id}: {removed_users}")
                 # Delete pre-generated papers for removed users (where attempt hasn't started)
                 # We assume if attempt started, user shouldn't be removed, or attempt needs special handling.
                 await db.execute(
                     sql_delete(models.PreGeneratedPaper)
                     .where(
                         models.PreGeneratedPaper.exam_id == exam.id,
                         models.PreGeneratedPaper.user_id.in_(removed_users)
                     )
                 )

        if commit:
            await db.commit()

        return added_users, removed_users # Return delta for info if needed


    # ... (generate_unified_paper - slightly modified to fit _generate_all_papers flow) ...
    async def generate_unified_paper(self, db: AsyncSession, *, exam: models.Exam, rules: List[schemas_exam.RandomQuestionParameter], commit: bool = True):
        """Generates the single, fixed paper for a random_unified exam and saves to ExamQuestion."""
        # No need to check existence here, _generate_all_papers clears first
        selected_questions = []
        order_idx = 0
        question_ids_selected = set()
        # ... (selection logic remains the same) ...
        for rule in rules:
            # ... (query logic) ...
            query = select(models.Question.id).join(models.Chapter).filter(
                models.Chapter.id.in_(rule.chapter_ids),
                models.Question.id.notin_(question_ids_selected)
            )
            if rule.question_type: query = query.filter(models.Question.question_type == rule.question_type)
            query = query.order_by(func.rand()).limit(rule.count)
            result = await db.execute(query)
            q_ids = result.scalars().all()
            if len(q_ids) < rule.count: print(f"Warning: Not enough unique questions...")
            for q_id in q_ids:
                 selected_questions.append({"question_id": q_id, "score": rule.score_per_question, "order_index": order_idx})
                 question_ids_selected.add(q_id)
                 order_idx += 1

        if not selected_questions: raise ValueError(f"No questions selected for unified exam {exam.id}.")

        paper_entries = [models.ExamQuestion(exam_id=exam.id, **q_data) for q_data in selected_questions]
        db.add_all(paper_entries)
        print(f"Generated unified paper with {len(selected_questions)} questions for exam {exam.id}")
        if commit: await db.commit()

    async def _sync_manual_questions(self, db: AsyncSession, *, exam: models.Exam, questions_in: List[schemas_exam.ExamQuestionManualInput], commit: bool = True):
        """Helper to replace manual questions for an exam."""
         # 1. Validate question IDs exist and belong to valid chapters/libs? (Optional but recommended)
        q_ids = [q.question_id for q in questions_in]
        valid_questions = await db.execute(select(models.Question.id).filter(models.Question.id.in_(q_ids)))
        valid_q_ids = set(valid_questions.scalars().all())
        if len(valid_q_ids) != len(q_ids):
             missing_ids = set(q_ids) - valid_q_ids
             raise ValueError(f"Invalid or non-existent question IDs provided: {missing_ids}")

        # 2. Clear existing questions for this exam
        await db.execute(sql_delete(models.ExamQuestion).where(models.ExamQuestion.exam_id == exam.id))

        # 3. Add new questions
        new_exam_questions = [
            models.ExamQuestion(
                exam_id=exam.id,
                question_id=q.question_id,
                score=q.score,
                order_index=q.order_index
            ) for q in questions_in
        ]
        if new_exam_questions:
            db.add_all(new_exam_questions)

        if commit:
            await db.commit()
        # Note: exam.questions relationship won't be updated until refresh/reload

    async def get_participant_count(self, db: AsyncSession, *, exam_id: int) -> int:
        """Get count of distinct users assigned (directly or via group)."""
        # This is complex because groups need expansion.
        # Simplistic count of participant rows:
        # count_res = await db.execute(select(func.count(models.ExamParticipant.id)).filter_by(exam_id=exam_id))
        # return count_res.scalar_one()
        # A more accurate count requires joining users/groups - potentially slow. Return row count for now.
        # TODO: Implement accurate distinct user count if needed.
        count_res = await db.execute(select(func.count(models.ExamParticipant.id)).filter_by(exam_id=exam_id))
        return count_res.scalar_one_or_none() or 0


    async def get_question_count(self, db: AsyncSession, *, exam_id: int) -> int:
        """Get count of questions for manual/unified modes."""
        count_res = await db.execute(select(func.count(models.ExamQuestion.id)).filter_by(exam_id=exam_id))
        return count_res.scalar_one_or_none() or 0

    async def get_exam_questions(self, db: AsyncSession, *, exam_id: int) -> Sequence[models.Question]:
        """Get the actual question objects for an exam (manual/unified)."""
        stmt = (
            select(models.Question)
            .join(models.ExamQuestion, models.Question.id == models.ExamQuestion.question_id)
            .filter(models.ExamQuestion.exam_id == exam_id)
            .order_by(models.ExamQuestion.order_index)
        )
        result = await db.execute(stmt)
        return result.scalars().all()

# Instantiate CRUD object
crud_exam = CRUDExam()
