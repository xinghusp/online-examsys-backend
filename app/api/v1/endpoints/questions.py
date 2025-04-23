from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Any, Optional

from starlette.responses import StreamingResponse

from app import crud, schemas
from app.db import models
from app.api import deps
# Import specific CRUD objects
from app.crud.crud_question import crud_question_lib, crud_chapter, crud_question
from app.utils import excel_processor

# Placeholder for Excel processing function
# from app.utils import excel_processor

router = APIRouter()

# --- Permission Dependency ---
# Define a dependency that checks for 'manage_questions' permission
# This assumes you have a Permission model and assigned it to roles
async def check_manage_questions_permission(
    current_user: models.User = Depends(deps.get_current_active_user)
) -> models.User:
    """Checks if the user has the 'manage_questions' permission."""
    # Adjust 'manage_questions' code if different
    required_permission_code = "manage_questions"
    has_permission = False
    # Ensure roles and permissions are loaded (get_current_user should handle roles)
    # Need to ensure permissions *within* roles are loaded if not already
    # This might require modifying get_current_user or adding another dependency layer
    # Simplified check assuming roles are loaded:
    for role in current_user.roles:
        # This check assumes role.permissions is loaded!
        # If not, you need to load them here or in the dependency chain.
        # Example: await db.refresh(role, attribute_names=['permissions']) # Needs db session
        if any(p.code == required_permission_code for p in getattr(role, "permissions", [])):
             has_permission = True
             break
    if not has_permission:
        print(f"Permission denied for user {current_user.username}. Missing '{required_permission_code}'.") # Debug/Log
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to manage questions.",
        )
    return current_user

# Apply the permission check dependency to relevant endpoints using Depends()

# --- Question Library Endpoints ---

@router.post("/libs/", response_model=schemas.QuestionLib, status_code=status.HTTP_201_CREATED, tags=["Question Libraries"])
async def create_question_lib(
    *,
    db: AsyncSession = Depends(deps.get_db),
    lib_in: schemas.QuestionLibCreate,
    current_user: models.User = Depends(check_manage_questions_permission) # Permission check
) -> Any:
    """
    Create a new question library. Requires 'manage_questions' permission.
    """
    library = await crud_question_lib.create(db=db, obj_in=lib_in, creator_id=current_user.id)
    # Manually add chapters list for response model if needed (empty for new lib)
    library.chapters = []
    return library

@router.get("/libs/", response_model=List[schemas.QuestionLib], tags=["Question Libraries"])
async def read_question_libs(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    # No permission check for listing usually, but could add if needed
    # current_user: models.User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Retrieve question libraries (basic info, no chapters/questions).
    """
    libraries = await crud_question_lib.get_multi(db, skip=skip, limit=limit)
    # Add empty chapters list to conform to response model
    # Or adjust response model to not require chapters for list view
    response_libs = []
    for lib in libraries:
        lib_data = schemas.QuestionLib.model_validate(lib).model_dump()
        lib_data["chapters"] = [] # Add empty list
        response_libs.append(lib_data)
    return response_libs


@router.get("/libs/{lib_id}", response_model=schemas.QuestionLib, tags=["Question Libraries"])
async def read_question_lib(
    lib_id: int,
    db: AsyncSession = Depends(deps.get_db),
    # No permission check for reading usually
    # current_user: models.User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Get a specific question library by ID, including its chapters (with question counts).
    """
    library = await crud_question_lib.get(db, id=lib_id)
    if not library:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question Library not found")

    # Fetch chapters and their counts separately if not loaded by CRUD get
    chapters_db = await crud_chapter.get_multi_by_lib(db=db, lib_id=lib_id, limit=1000) # Get all chapters for the lib
    chapters_response = []
    for chap_db in chapters_db:
         count = await crud_chapter.get_question_count(db=db, chapter_id=chap_db.id)
         chap_data = schemas.Chapter.model_validate(chap_db).model_dump()
         chap_data["question_count"] = count
         chapters_response.append(chap_data)

    # Construct the final response
    lib_data = schemas.QuestionLib.model_validate(library).model_dump()
    lib_data["chapters"] = chapters_response
    return lib_data


@router.put("/libs/{lib_id}", response_model=schemas.QuestionLib, tags=["Question Libraries"])
async def update_question_lib(
    *,
    db: AsyncSession = Depends(deps.get_db),
    lib_id: int,
    lib_in: schemas.QuestionLibUpdate,
    current_user: models.User = Depends(check_manage_questions_permission) # Permission check
) -> Any:
    """
    Update a question library. Requires 'manage_questions' permission.
    """
    library = await db.get(models.QuestionLib, lib_id) # Use simple get
    if not library:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question Library not found")
    # Add check: only creator or admin can update?
    # if library.creator_id != current_user.id and not is_admin(current_user):
    #    raise HTTPException(status_code=403, ...)
    updated_library = await crud_question_lib.update(db=db, db_obj=library, obj_in=lib_in)
    # Add empty chapters list for response model consistency
    updated_library.chapters = []
    return updated_library


@router.delete("/libs/{lib_id}", response_model=schemas.QuestionLib, tags=["Question Libraries"])
async def delete_question_lib(
    *,
    db: AsyncSession = Depends(deps.get_db),
    lib_id: int,
    current_user: models.User = Depends(check_manage_questions_permission) # Permission check
) -> Any:
    """
    Delete a question library and all its contents. Requires 'manage_questions' permission.
    (Note: Add check if library is used in active exams if needed).
    """
    deleted_library = await crud_question_lib.remove(db=db, id=lib_id)
    if not deleted_library:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question Library not found")
    # Add empty chapters list for response model consistency
    deleted_library.chapters = []
    return deleted_library

# --- Chapter Endpoints ---

@router.post("/chapters/", response_model=schemas.Chapter, status_code=status.HTTP_201_CREATED, tags=["Chapters"])
async def create_chapter(
    *,
    db: AsyncSession = Depends(deps.get_db),
    chapter_in: schemas.ChapterCreate,
    current_user: models.User = Depends(check_manage_questions_permission)
) -> Any:
    """
    Create a new chapter within a question library. Requires 'manage_questions' permission.
    """
    try:
        chapter = await crud_chapter.create(db=db, obj_in=chapter_in)
        chapter.question_count = 0 # New chapter has 0 questions
        return chapter
    except ValueError as e:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/chapters/by-lib/{lib_id}", response_model=List[schemas.Chapter], tags=["Chapters"])
async def read_chapters_by_lib(
    lib_id: int,
    db: AsyncSession = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    # current_user: models.User = Depends(deps.get_current_active_user) # No permission needed?
) -> Any:
    """
    Retrieve chapters for a specific question library, including question counts.
    """
    chapters_db = await crud_chapter.get_multi_by_lib(db=db, lib_id=lib_id, skip=skip, limit=limit)
    response_chapters = []
    for chap_db in chapters_db:
        count = await crud_chapter.get_question_count(db=db, chapter_id=chap_db.id)
        chap_data = schemas.Chapter.model_validate(chap_db).model_dump()
        chap_data["question_count"] = count
        response_chapters.append(chap_data)
    return response_chapters


@router.get("/chapters/{chapter_id}", response_model=schemas.Chapter, tags=["Chapters"])
async def read_chapter(
    chapter_id: int,
    db: AsyncSession = Depends(deps.get_db),
    # current_user: models.User = Depends(deps.get_current_active_user) # No permission needed?
) -> Any:
    """
    Get a specific chapter by ID, including its question count.
    """
    chapter = await crud_chapter.get(db, id=chapter_id)
    if not chapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")
    # Manually load count if not done in CRUD get
    count = await crud_chapter.get_question_count(db=db, chapter_id=chapter.id)
    chap_data = schemas.Chapter.model_validate(chapter).model_dump()
    chap_data["question_count"] = count
    return chap_data


@router.put("/chapters/{chapter_id}", response_model=schemas.Chapter, tags=["Chapters"])
async def update_chapter(
    *,
    db: AsyncSession = Depends(deps.get_db),
    chapter_id: int,
    chapter_in: schemas.ChapterUpdate,
    current_user: models.User = Depends(check_manage_questions_permission)
) -> Any:
    """
    Update a chapter. Requires 'manage_questions' permission.
    """
    chapter = await crud_chapter.get(db, id=chapter_id)
    if not chapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")
    updated_chapter = await crud_chapter.update(db=db, db_obj=chapter, obj_in=chapter_in)
    # Reload count for response
    count = await crud_chapter.get_question_count(db=db, chapter_id=updated_chapter.id)
    chap_data = schemas.Chapter.model_validate(updated_chapter).model_dump()
    chap_data["question_count"] = count
    return chap_data


@router.delete("/chapters/{chapter_id}", response_model=schemas.Chapter, tags=["Chapters"])
async def delete_chapter(
    *,
    db: AsyncSession = Depends(deps.get_db),
    chapter_id: int,
    current_user: models.User = Depends(check_manage_questions_permission)
) -> Any:
    """
    Delete a chapter and all its questions. Requires 'manage_questions' permission.
    Updates question count in the parent library.
    """
    deleted_chapter = await crud_chapter.remove(db=db, id=chapter_id)
    if not deleted_chapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")
    # Add question count (0 after deletion) for response model
    deleted_chapter.question_count = 0
    return deleted_chapter


# --- Question Endpoints ---

@router.post("/questions/", response_model=schemas.Question, status_code=status.HTTP_201_CREATED, tags=["Questions"])
async def create_question(
    *,
    db: AsyncSession = Depends(deps.get_db),
    question_in: schemas.QuestionCreate,
    current_user: models.User = Depends(check_manage_questions_permission)
) -> Any:
    """
    Create a new question within a chapter. Requires 'manage_questions' permission.
    Updates question count in the parent library.
    """
    try:
        question = await crud_question.create(db=db, obj_in=question_in, creator_id=current_user.id)
        return question
    except ValueError as e:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/questions/by-chapter/{chapter_id}", response_model=List[schemas.Question], tags=["Questions"])
async def read_questions_by_chapter(
    chapter_id: int,
    db: AsyncSession = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    # current_user: models.User = Depends(deps.get_current_active_user) # Permission needed?
) -> Any:
    """
    Retrieve questions for a specific chapter.
    """
    # Check if chapter exists first?
    chapter = await crud_chapter.get(db, id=chapter_id)
    if not chapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")
    questions = await crud_question.get_multi_by_chapter(db=db, chapter_id=chapter_id, skip=skip, limit=limit)
    return questions


@router.get("/questions/{question_id}", response_model=schemas.Question, tags=["Questions"])
async def read_question(
    question_id: int,
    db: AsyncSession = Depends(deps.get_db),
    # current_user: models.User = Depends(deps.get_current_active_user) # Permission needed?
) -> Any:
    """
    Get a specific question by ID.
    """
    question = await crud_question.get(db, id=question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return question


@router.put("/questions/{question_id}", response_model=schemas.Question, tags=["Questions"])
async def update_question(
    *,
    db: AsyncSession = Depends(deps.get_db),
    question_id: int,
    question_in: schemas.QuestionUpdate,
    current_user: models.User = Depends(check_manage_questions_permission)
) -> Any:
    """
    Update a question. Requires 'manage_questions' permission.
    """
    question = await crud_question.get(db, id=question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    # Add creator/admin check if needed
    updated_question = await crud_question.update(db=db, db_obj=question, obj_in=question_in)
    return updated_question


@router.delete("/questions/{question_id}", response_model=schemas.Question, tags=["Questions"])
async def delete_question(
    *,
    db: AsyncSession = Depends(deps.get_db),
    question_id: int,
    current_user: models.User = Depends(check_manage_questions_permission)
) -> Any:
    """
    Delete a question. Requires 'manage_questions' permission.
    Updates question count in the parent library.
    """
    deleted_question = await crud_question.remove(db=db, id=question_id)
    if not deleted_question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return deleted_question


# --- Bulk Import/Export Endpoints ---

@router.post("/questions/bulk-import/{lib_id}", response_model=schemas.question.QuestionImportResult, tags=["Questions", "Bulk Operations"])
async def bulk_import_questions(
    lib_id: int,
    *,
    db: AsyncSession = Depends(deps.get_db),
    file: UploadFile = File(..., description="Excel file (.xlsx) containing questions to import."),
    current_user: models.User = Depends(check_manage_questions_permission) # Permission check
):
    """
    Import questions from an Excel file (.xlsx) into a specific library.

    The Excel file should have the following columns in the first sheet:
    `Chapter Name`, `Question Type`, `Stem`, `Score`, `Option A`, `Option B`,
    `Option C`, `Option D`, `Option E`, `Answer`, `Explanation`,
    `Grading Policy (MC)`, `Partial Score % (MC)`, `Specified Score (MC)`, `Match Type (Fill)`.

    - **Answer format:**
        - Choice questions: Comma-separated option IDs (e.g., `A`, `B,D`)
        - Fill-in-blank: Semicolon-separated answers for each blank (e.g., `answer1; answer2`)
        - Short answer: Model answer text (or leave blank)
    - Chapters will be created if they don't exist in the library.
    - Rows with errors will be skipped.
    - Requires 'manage_questions' permission.
    """
    library = await crud_question_lib.get(db, id=lib_id) # Use simple get for existence check
    if not library:
        raise HTTPException(status_code=404, detail="Question Library not found")

    if not file.filename or not file.filename.endswith(".xlsx"):
         raise HTTPException(status_code=400, detail="Invalid file type. Please upload an .xlsx file.")

    content = await file.read()
    if not content:
         raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        # --- Call utility function to process Excel ---
        # This function adds questions to the session but does NOT commit
        result: schemas.question.QuestionImportResult = await excel_processor.process_import(
            db=db, file_content=content, lib_id=lib_id, creator_id=current_user.id
        )

        # --- Commit transaction and update count ---
        if result.imported_count > 0:
             # Recalculate count after import for robustness
             await crud_question_lib.recalculate_question_count(db=db, lib_id=lib_id)
             await db.commit() # Commit all imported questions and the count update
        else:
             # If nothing was imported, no need to commit or recalc count
             await db.rollback() # Rollback any potential chapter creations if no questions were added

        return result

    except ValueError as ve: # Catch specific errors like header mismatch
        await db.rollback() # Rollback any transaction changes
        raise HTTPException(status_code=400, detail=f"Import Error: {str(ve)}")
    except Exception as e:
        await db.rollback() # Rollback any transaction changes
        print(f"Unexpected error during bulk import: {e}") # Log the error
        # import traceback; traceback.print_exc() # More detailed logging if needed
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during import: {e}")
    finally:
        await file.close()


@router.get("/questions/bulk-export/{lib_id}", response_class=StreamingResponse, tags=["Questions", "Bulk Operations"])
async def bulk_export_questions(
    lib_id: int,
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(check_manage_questions_permission) # Or maybe just read permission?
):
    """
    Export all questions from a specific library to an Excel file (.xlsx).
    Requires 'manage_questions' permission (or specific export permission).
    """
    library = await db.get(models.QuestionLib, lib_id) # Check existence
    if not library:
        raise HTTPException(status_code=404, detail="Question Library not found")

    try:
        # --- Call utility function to generate Excel bytes ---
        file_content: bytes = await excel_processor.generate_export(db, lib_id)

        # --- Return as StreamingResponse ---
        filename = f"library_{library.name.replace(' ', '_')}_{lib_id}_export.xlsx"
        return StreamingResponse(
                io.BytesIO(file_content),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename=\"{filename}\""} # Ensure filename is quoted
            )
    except Exception as e:
         print(f"Unexpected error during bulk export: {e}") # Log the error
         # import traceback; traceback.print_exc()
         raise HTTPException(status_code=500, detail=f"An unexpected error occurred during export: {e}")
