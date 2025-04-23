from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
import enum

# --- Enums ---
# Replicate enums from models for validation
class QuestionTypeEnum(str, enum.Enum):
    single_choice = "single_choice"
    multiple_choice = "multiple_choice"
    fill_in_blank = "fill_in_blank"
    short_answer = "short_answer"

# --- Grading Strategy Schemas (Example) ---
# These can be more complex based on actual needs
class GradingStrategyBase(BaseModel):
    pass # Base for potential future common fields

class GradingStrategyMultipleChoice(GradingStrategyBase):
    policy: str = Field("partial", description="Grading policy: 'exact' (all correct), 'partial' (score per correct option), 'all_or_nothing_specified_score' (get X points if not all correct but some are)")
    partial_score_percent: Optional[float] = Field(None, ge=0, le=100, description="Percentage score per correct option if policy is 'partial'")
    specified_score: Optional[float] = Field(None, ge=0, description="Score if not all correct but some are, for 'all_or_nothing_specified_score'")

class GradingStrategyFillInBlank(GradingStrategyBase):
    match_type: str = Field("exact", description="Matching type: 'exact' (case-sensitive exact match), 'contains' (substring match), 'case_insensitive'")
    # Could add points per blank if multiple blanks

# Union type for grading strategy based on question type
GradingStrategy = Union[GradingStrategyMultipleChoice, GradingStrategyFillInBlank, None] # Add more as needed

# --- Question Option Schema ---
class QuestionOption(BaseModel):
    id: str = Field(..., description="Option identifier (e.g., 'A', 'B')")
    text: str = Field(..., description="Option text (can be rich text/HTML)")

# --- Question Schemas ---
class QuestionBase(BaseModel):
    question_type: QuestionTypeEnum
    stem: str = Field(..., description="Question text/body (can contain HTML/rich text/formulas)")
    score: float = Field(..., gt=0, description="Default score value for this question")
    explanation: Optional[str] = Field(None, description="Optional explanation for the answer")

    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True # Ensure enums are serialized correctly
    )

class QuestionCreate(QuestionBase):
    chapter_id: int # Must belong to a chapter
    # Options required for choice questions
    options: Optional[List[QuestionOption]] = Field(None, description="List of options for single/multiple choice questions")
    # Answer format depends on question type
    answer: Any = Field(..., description="Correct answer(s). Format depends on type: List[str] for choices, List[str] for fill-in-blank (one per blank), str for short_answer")
    grading_strategy: Optional[Dict[str, Any]] = Field(None, description="Specific grading rules (JSON object)") # Use Dict for flexibility initially

    # Validation based on question type
    @model_validator(mode='after')
    def check_options_and_answer(self) -> 'QuestionCreate':
        qt = self.question_type
        options = self.options
        answer = self.answer

        if qt in [QuestionTypeEnum.single_choice, QuestionTypeEnum.multiple_choice]:
            if not options or len(options) < 2:
                raise ValueError("Choice questions must have at least 2 options.")
            if not answer or not isinstance(answer, list) or not all(isinstance(a, str) for a in answer):
                 raise ValueError("Answer for choice questions must be a list of option IDs (strings).")
            option_ids = {opt.id for opt in options}
            if not all(ans_id in option_ids for ans_id in answer):
                 raise ValueError("Answer IDs must match provided option IDs.")
            if qt == QuestionTypeEnum.single_choice and len(answer) != 1:
                 raise ValueError("Single choice questions must have exactly one answer.")

        elif qt == QuestionTypeEnum.fill_in_blank:
            if not answer or not isinstance(answer, list) or not all(isinstance(a, str) for a in answer):
                 raise ValueError("Answer for fill-in-blank questions must be a list of strings (one per blank).")
            # Options should be null/empty for fill-in-blank
            if options:
                 raise ValueError("Fill-in-blank questions should not have options.")

        elif qt == QuestionTypeEnum.short_answer:
            # Answer might be a model answer (string) or null if only manual grading
            if answer is not None and not isinstance(answer, str):
                 raise ValueError("Answer for short answer questions should be a string (model answer) or null.")
            # Options should be null/empty
            if options:
                 raise ValueError("Short answer questions should not have options.")

        return self

    model_config = ConfigDict(
         json_schema_extra={
            "example": {
                "chapter_id": 1,
                "question_type": "single_choice",
                "stem": "<p>What is the capital of France?</p>",
                "score": 2.0,
                "options": [
                    {"id": "A", "text": "Berlin"},
                    {"id": "B", "text": "Madrid"},
                    {"id": "C", "text": "Paris"},
                    {"id": "D", "text": "Rome"}
                ],
                "answer": ["C"],
                "explanation": "Paris is the capital and largest city of France.",
                "grading_strategy": None
            }
        }
    )


class QuestionUpdate(BaseModel):
    # Allow updating most fields, but not chapter_id directly (handle via move endpoint?)
    question_type: Optional[QuestionTypeEnum] = None
    stem: Optional[str] = None
    score: Optional[float] = Field(None, gt=0)
    options: Optional[List[QuestionOption]] = None
    answer: Optional[Any] = None
    explanation: Optional[str] = None
    grading_strategy: Optional[Dict[str, Any]] = None

    # Add validation similar to QuestionCreate if type changes
    # Or restrict type changes?

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "score": 2.5,
                "explanation": "Updated explanation: Paris is known for the Eiffel Tower."
            }
        }
    )

class QuestionInDB(QuestionBase):
    id: int
    chapter_id: int
    options: Optional[List[QuestionOption]] = None # Store as JSON, parse back
    answer: Optional[Any] = None # Store as JSON, parse back
    grading_strategy: Optional[Dict[str, Any]] = None # Store as JSON
    creator_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

class Question(QuestionInDB):
    pass # Simple response for now


# --- Chapter Schemas ---
class ChapterBase(BaseModel):
    name: str = Field(..., max_length=255, description="Name of the chapter")
    description: Optional[str] = Field(None, description="Description of the chapter")
    order_index: int = Field(0, description="Order within the question bank")

    model_config = ConfigDict(from_attributes=True)


class ChapterCreate(ChapterBase):
    question_lib_id: int # Must belong to a library

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question_lib_id": 1,
                "name": "Chapter 1: Introduction",
                "description": "Basic concepts.",
                "order_index": 1
            }
        }
    )

class ChapterUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None)
    order_index: Optional[int] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Chapter 1: Core Concepts",
                "order_index": 0
            }
        }
    )

class ChapterInDB(ChapterBase):
    id: int
    question_lib_id: int
    created_at: datetime
    updated_at: datetime

class Chapter(ChapterInDB):
    # Optionally include questions count or list in response
    question_count: int = Field(0, description="Number of questions in this chapter")
    # questions: List[Question] = [] # Avoid loading all questions by default


# --- Question Library Schemas ---
class QuestionLibBase(BaseModel):
    name: str = Field(..., max_length=255, description="Name of the question bank")
    description: Optional[str] = Field(None, description="Description of the question bank")

    model_config = ConfigDict(from_attributes=True)

class QuestionLibCreate(QuestionLibBase):
    pass

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "General Physics Questions",
                "description": "Questions covering mechanics, thermodynamics, and E&M."
            }
        }
    )

class QuestionLibUpdate(QuestionLibBase):
    name: Optional[str] = Field(None, max_length=255) # Allow name update
    description: Optional[str] = Field(None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Advanced Physics Questions"
            }
        }
    )


class QuestionLibInDB(QuestionLibBase):
    id: int
    question_count: int = 0 # Populated by DB/CRUD
    creator_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

class QuestionLib(QuestionLibInDB):
    # Optionally include chapters in response
    chapters: List[Chapter] = [] # Load chapters when returning a single library


# --- Bulk Import/Export Schemas (Placeholders) ---
class QuestionImportRow(BaseModel):
    # Define fields expected in each row of the Excel file
    chapter_name: str
    question_type: QuestionTypeEnum
    stem: str
    score: float
    option_a: Optional[str] = None
    option_b: Optional[str] = None
    option_c: Optional[str] = None
    option_d: Optional[str] = None
    option_e: Optional[str] = None # Add more if needed
    answer: str # e.g., "C", "A,B", "Keyword1;Keyword2"
    explanation: Optional[str] = None
    # Add grading strategy fields if needed

class QuestionImportResult(BaseModel):
    total_rows: int
    imported_count: int
    skipped_count: int
    errors: List[Dict[str, Any]] # List of row numbers and error messages

# --- Simplified Question Schema for Student ---
class QuestionForStudent(BaseModel):
    """Schema for presenting a question to a student during an exam."""
    id: int
    # chapter_id: int # Maybe not needed for student?
    question_type: QuestionTypeEnum
    stem: str
    score: float # Show score per question?
    options: Optional[List[QuestionOption]] = None # Show options for choice questions
    order_index: int # The order within this specific exam attempt/paper

    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
    )

# --- Answer Submission Schema ---
class AnswerSubmit(BaseModel):
    """Schema for submitting an answer during an attempt."""
    user_answer: Any # Format depends on question type (e.g., List[str] for choices, str for text)

    model_config = ConfigDict(
         json_schema_extra={
            "example": {
                "user_answer": ["A", "C"] # Example for multiple choice
                # "user_answer": "Photosynthesis requires sunlight." # Example for short answer
            }
        }
    )

# --- Answer Response Schema ---
class AnswerResponse(BaseModel):
    """Schema representing a saved/submitted answer."""
    attempt_id: int
    question_id: int
    user_answer: Optional[Any] = None # Show the saved answer
    # score: Optional[float] = None # Score might not be available immediately
    # is_correct: Optional[bool] = None # Correctness might not be available immediately
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
