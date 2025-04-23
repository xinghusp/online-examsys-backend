from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

from .question import QuestionTypeEnum # Import QuestionTypeEnum if needed
from .attempt import ExamAttemptStatusEnum

# --- Input for Manual Grading ---
class ManualGradeInput(BaseModel):
    score: float = Field(..., description="Score assigned by the grader for this answer.")
    is_correct: Optional[bool] = Field(None, description="Optional flag indicating if the answer is deemed correct (useful for non-scored items or overrides).")
    comments: Optional[str] = Field(None, description="Grader's comments.")

    model_config = ConfigDict(
         json_schema_extra={
            "example": {
                "score": 4.5,
                "is_correct": None,
                "comments": "Good explanation, but missed one key point."
            }
        }
    )

# --- Schema for item needing manual grading ---
class AnswerForGrading(BaseModel):
    # Information needed by the grader
    answer_id: int
    attempt_id: int
    question_id: int
    user_id: int # ID of the student
    # Include question details
    question_stem: str
    question_type: QuestionTypeEnum
    question_max_score: float # Max possible score for context
    model_answer: Optional[Any] = None # Display model answer if available
    # Include user's answer
    user_answer: Optional[Any]
    # Existing grading info (if any)
    current_score: Optional[float] = None
    current_comments: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


# --- Schema for Viewing Attempt Results (Student) ---
class AttemptResultStudent(BaseModel):
    attempt_id: int
    exam_id: int
    exam_name: str
    start_time: Optional[datetime]
    submit_time: Optional[datetime]
    status: ExamAttemptStatusEnum
    final_score: Optional[float] = None
    total_possible_score: Optional[float] = None # Calculate and add this

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

# --- Schema for Viewing Detailed Attempt Results (Student/Admin) ---
class AnswerResultDetail(BaseModel):
    question_id: int
    order_index: int
    question_stem: str
    question_type: QuestionTypeEnum
    max_score: float # Score allocated in this exam paper
    user_answer: Optional[Any]
    is_correct: Optional[bool] = None
    score: Optional[float] = None # Achieved score
    correct_answer: Optional[Any] = None # Actual correct answer (shown based on exam settings)
    explanation: Optional[str] = None # Question explanation (shown based on exam settings)
    grading_comments: Optional[str] = None # Grader comments

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

class AttemptResultDetail(AttemptResultStudent): # Inherits fields from student result
    # Add detailed answer breakdown
    answers: List[AnswerResultDetail] = []
    # Add exam settings for showing answers/explanations
    show_answers_after_exam: bool = False


# --- Schema for Admin Results Overview ---
class ExamResultOverviewAdmin(BaseModel):
    # Overall exam stats
    exam_id: int
    exam_name: str
    participant_count: int # Total assigned
    attempt_count: int # Total submitted/graded attempts
    average_score: Optional[float] = None
    max_score_possible: Optional[float] = None
    # Potentially add score distribution histogram data?

# --- Schema for Admin Listing Individual Attempts ---
class AttemptResultAdmin(AttemptResultStudent): # Similar to student view, but maybe add user info
    user_id: int
    user_username: Optional[str] = None # Include username/email for identification
    user_fullname: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# --- Schema for Export ---
# Define fields for the export file (can be flat)
class ResultExportRow(BaseModel):
    attempt_id: int
    exam_id: int
    exam_name: str
    user_id: int
    username: str
    fullname: Optional[str] = None
    start_time: Optional[datetime]
    submit_time: Optional[datetime]
    duration_taken_seconds: Optional[int] = None
    status: ExamAttemptStatusEnum
    final_score: Optional[float]
    max_possible_score: Optional[float]
    # Optionally add scores per question Q1_Score, Q2_Score... (complex to generate)
