from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Optional, List, Union, Dict, Any
from datetime import datetime
from app.schemas import question as schemas_question # Alias for clarity
import enum

from .attempt import ExamAttemptStatusEnum
# Import related schemas if needed (e.g., User, Group for participant responses)
# from .user import User
# from .group import Group
from .question import Question # For defining paper structure

# --- Enums (mirroring models) ---
class PaperGenerationModeEnum(str, enum.Enum):
    manual = "manual"
    random_unified = "random_unified"
    random_individual = "random_individual"

class ExamStatusEnum(str, enum.Enum):
    draft = "draft"
    published = "published"
    ongoing = "ongoing"
    finished = "finished"
    archived = "archived"

# --- Participant Schemas ---
# Input for assigning participants
class ParticipantAssignment(BaseModel):
    user_ids: List[int] = Field([], description="List of specific User IDs to assign")
    group_ids: List[int] = Field([], description="List of Group IDs whose members to assign")

# Output schema for listing participants (can be simple for now)
class ExamParticipantInfo(BaseModel):
    user_id: Optional[int] = None
    group_id: Optional[int] = None
    # Add user/group details if needed in specific responses
    # user: Optional[User] = None
    # group: Optional[Group] = None

    model_config = ConfigDict(from_attributes=True)


# --- Paper Definition Schemas ---
# For Manual Mode: Define specific questions and their scores
class ExamQuestionManualInput(BaseModel):
    question_id: int
    score: float = Field(..., gt=0)
    order_index: int = Field(..., ge=0)

# For Random Modes: Define parameters for question selection
class RandomQuestionParameter(BaseModel):
    # Define how to select questions, e.g., by chapter, type, count
    chapter_ids: List[int] = Field(..., description="Select questions from these chapters")
    question_type: Optional[schemas_question.QuestionTypeEnum] = Field(None, description="Filter by question type (optional)")
    count: int = Field(..., gt=0, description="Number of questions to select randomly")
    score_per_question: float = Field(..., gt=0, description="Score for each question selected by this rule")

class ExamPaperRandomInput(BaseModel):
    rules: List[RandomQuestionParameter] = Field(..., description="List of rules to randomly select questions")


# --- Exam Schemas ---
class ExamBase(BaseModel):
    name: str = Field(..., max_length=255, description="Name of the exam")
    start_time: datetime = Field(..., description="Scheduled start time (UTC recommended)")
    end_time: datetime = Field(..., description="Scheduled end time (UTC recommended)")
    duration_minutes: int = Field(..., gt=0, description="Duration of the exam in minutes")
    show_score_after_exam: bool = Field(True, description="Show score immediately after submission?")
    show_answers_after_exam: bool = Field(False, description="Show correct answers after submission/grading?")
    rules: Optional[str] = Field(None, description="Exam rules and instructions (rich text/HTML)")
    paper_generation_mode: PaperGenerationModeEnum

    @model_validator(mode='after')
    def check_times(self) -> 'ExamBase':
        if self.start_time >= self.end_time:
            raise ValueError("End time must be after start time.")
        # Consider adding validation that duration doesn't exceed start/end window, though not strictly required by schema
        return self

    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
    )

class ExamCreate(ExamBase):
    # Participants can be assigned during creation
    participants: Optional[ParticipantAssignment] = Field(None, description="Assign initial participants (users and/or groups)")
    # Paper definition depends on mode
    manual_questions: Optional[List[ExamQuestionManualInput]] = Field(None, description="List of questions and scores for 'manual' mode")
    random_rules: Optional[ExamPaperRandomInput] = Field(None, description="Rules for selecting questions for 'random_unified' or 'random_individual' modes")

    @model_validator(mode='after')
    def check_paper_definition(self) -> 'ExamCreate':
        mode = self.paper_generation_mode
        if mode == PaperGenerationModeEnum.manual and not self.manual_questions:
             raise ValueError("Manual questions must be provided for 'manual' paper generation mode.")
        if mode != PaperGenerationModeEnum.manual and self.manual_questions:
             raise ValueError("Manual questions should only be provided for 'manual' paper generation mode.")
        # Add similar check for random_rules if making it mandatory for random modes
        # if mode in [PaperGenerationModeEnum.random_unified, PaperGenerationModeEnum.random_individual] and not self.random_rules:
        #      raise ValueError("Random rules must be provided for random paper generation modes.")
        if mode == PaperGenerationModeEnum.manual and self.random_rules:
             raise ValueError("Random rules should not be provided for 'manual' paper generation mode.")
        return self

    model_config = ConfigDict(
         json_schema_extra={
            "example": {
                "name": "Midterm Exam - Calculus I",
                "start_time": "2025-10-20T09:00:00Z",
                "end_time": "2025-10-20T11:00:00Z",
                "duration_minutes": 90,
                "show_score_after_exam": True,
                "show_answers_after_exam": False,
                "rules": "<p>Closed book exam. Calculators allowed.</p>",
                "paper_generation_mode": "manual",
                "participants": {"user_ids": [1, 2, 5], "group_ids": [10]},
                "manual_questions": [
                    {"question_id": 101, "score": 5.0, "order_index": 0},
                    {"question_id": 105, "score": 5.0, "order_index": 1},
                    {"question_id": 210, "score": 10.0, "order_index": 2}
                ],
                "random_rules": None # Example for manual mode
            }
        }
    )

class ExamUpdate(BaseModel):
    # Allow updating fields, but maybe restrict some after exam starts?
    name: Optional[str] = Field(None, max_length=255)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, gt=0)
    show_score_after_exam: Optional[bool] = None
    show_answers_after_exam: Optional[bool] = None
    rules: Optional[str] = None
    # Disallow changing paper generation mode after creation? Or handle transition carefully.
    # paper_generation_mode: Optional[PaperGenerationModeEnum] = None
    status: Optional[ExamStatusEnum] = Field(None, description="Update exam status (e.g., publish, archive)")

    # Allow updating participants/paper definition (logic handled in endpoint/crud)
    participants: Optional[ParticipantAssignment] = None
    manual_questions: Optional[List[ExamQuestionManualInput]] = None
    random_rules: Optional[ExamPaperRandomInput] = None

    # Add validation if needed (e.g., start/end time consistency if both updated)

    model_config = ConfigDict(
         json_schema_extra={
            "example": {
                "name": "Midterm Exam - Calculus I (Revised)",
                "rules": "<p>Updated rules: Non-graphing calculators only.</p>",
                "status": "published"
            }
        }
    )

class ExamInDB(ExamBase):
    id: int
    status: ExamStatusEnum # Status is managed internally
    creator_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

# Response model for a single Exam
class Exam(ExamInDB):
    # Include participants and paper details in the response for a single exam GET
    participants: List[ExamParticipantInfo] = []
    # Include question details for manual/unified modes
    questions: List[schemas_question.Question] = [] # Or a simplified Question schema
    # Include random rules if applicable
    random_rules: Optional[ExamPaperRandomInput] = None # Store/retrieve rules if needed
    # Add counts?
    participant_count: int = 0
    question_count: int = 0

# Response model for listing Exams (less detail)
class ExamListed(ExamInDB):
    participant_count: int = 0
    question_count: int = 0
    # Exclude detailed participant/question lists for brevity

# --- Simplified Exam Schema for Student Listing ---
class ExamForStudent(BaseModel):
    """Schema for listing available/ongoing exams for a student."""
    id: int
    name: str
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    status: ExamStatusEnum # Show current status (published, ongoing)
    attempt_status: Optional[ExamAttemptStatusEnum] = None # Show student's attempt status if exists
    attempt_id: Optional[int] = None # Include attempt ID if ongoing/submitted

    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
    )
