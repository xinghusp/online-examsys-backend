from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
import enum

# Import related schemas
# from .exam import ExamStatusEnum # Need Exam status for checks
from .question import AnswerResponse, QuestionForStudent

# --- Enums (mirroring models) ---
class ExamAttemptStatusEnum(str, enum.Enum):
    pending = "pending" # Should not really be exposed, internal state before start
    in_progress = "in_progress"
    submitted = "submitted"
    grading = "grading" # Internal state after submission before score calculation
    graded = "graded" # Final state with score
    aborted = "aborted" # If automatically submitted due to timeout/heartbeat loss

# --- Attempt Schemas ---
class ExamAttemptBase(BaseModel):
    exam_id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)

# Schema returned when starting/getting attempt status
class ExamAttempt(ExamAttemptBase):
    id: int
    start_time: Optional[datetime] = None
    submit_time: Optional[datetime] = None
    calculated_end_time: Optional[datetime] = None # The absolute deadline
    status: ExamAttemptStatusEnum
    final_score: Optional[float] = None # Show score if graded
    last_heartbeat: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(use_enum_values=True)

# Schema for the response when fetching questions during an attempt
class ExamAttemptQuestionsResponse(BaseModel):
    attempt_status: ExamAttemptStatusEnum
    questions: List[QuestionForStudent]
    # Include timing info?
    server_time: datetime = Field(default_factory=lambda: datetime.now(datetime.timezone.utc))
    calculated_end_time: Optional[datetime] = None
    # Include saved answers? Maybe fetch separately or include here?
    # saved_answers: Dict[int, AnswerResponse] = {} # Map question_id to saved answer

# Schema for submitting the attempt
class ExamAttemptSubmit(BaseModel):
    confirm: bool # Require explicit confirmation

# Schema for heartbeat response
class HeartbeatResponse(BaseModel):
    status: str = "received"
    server_time: datetime = Field(default_factory=lambda: datetime.now(datetime.timezone.utc))
