from sqlalchemy import Column, Integer, String, TIMESTAMP, text, TEXT, ForeignKey, Enum as SQLEnum, DECIMAL, JSON, DATETIME, BOOLEAN, BIGINT
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.db.base_class import Base
from typing import List, TYPE_CHECKING, Optional, Any, Union
from datetime import datetime
import enum

if TYPE_CHECKING:
    from .user import User
    from .group import Group
    from .question import Question

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

class ExamAttemptStatusEnum(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    submitted = "submitted"
    grading = "grading"
    graded = "graded"
    aborted = "aborted"

class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DATETIME, nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(DATETIME, nullable=False, index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    show_score_after_exam: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=True)
    show_answers_after_exam: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=False)
    rules: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    paper_generation_mode: Mapped[PaperGenerationModeEnum] = mapped_column(SQLEnum(PaperGenerationModeEnum, name="paper_mode_enum"), nullable=False)
    status: Mapped[ExamStatusEnum] = mapped_column(SQLEnum(ExamStatusEnum, name="exam_status_enum"), nullable=False, default=ExamStatusEnum.draft, index=True)
    creator_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

    # Relationships
    creator: Mapped[Union["User", None]] = relationship("User", back_populates="created_exams")
    questions: Mapped[List["ExamQuestion"]] = relationship("ExamQuestion", back_populates="exam", cascade="all, delete-orphan") # Fixed paper questions
    participants: Mapped[List["ExamParticipant"]] = relationship("ExamParticipant", back_populates="exam", cascade="all, delete-orphan")
    attempts: Mapped[List["ExamAttempt"]] = relationship("ExamAttempt", back_populates="exam", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Exam(id={self.id}, name='{self.name}', status='{self.status}')>"

class ExamQuestion(Base):
    __tablename__ = "exam_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(Integer, ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), index=True) # Consider RESTRICT
    score: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    exam: Mapped["Exam"] = relationship("Exam", back_populates="questions")
    question: Mapped["Question"] = relationship("Question", back_populates="exam_papers")

    # Add __table_args__ for unique constraints if needed, SQLAlchemy 2.0 prefers Mapped Columns approach
    # __table_args__ = (UniqueConstraint('exam_id', 'question_id', name='uk_exam_question'),
    #                   UniqueConstraint('exam_id', 'order_index', name='uk_exam_order'))

class ExamParticipant(Base):
    __tablename__ = "exam_participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(Integer, ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    group_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=True, index=True)

    # Relationships
    exam: Mapped["Exam"] = relationship("Exam", back_populates="participants")
    user: Mapped[Union["User", None]] = relationship("User") # No backpop needed here usually
    group: Mapped[Union["Group" , None]] = relationship("Group", back_populates="exam_participations") # Added backpop

    # __table_args__ = (UniqueConstraint('exam_id', 'user_id', name='uk_exam_user'),
    #                   UniqueConstraint('exam_id', 'group_id', name='uk_exam_group'),
    #                   CheckConstraint('user_id IS NOT NULL OR group_id IS NOT NULL'))

class ExamAttempt(Base):
    __tablename__ = "exam_attempts"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True) # Use BIGINT
    exam_id: Mapped[int] = mapped_column(Integer, ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    start_time: Mapped[datetime | None] = mapped_column(DATETIME, nullable=True)
    submit_time: Mapped[datetime | None] = mapped_column(DATETIME, nullable=True)
    calculated_end_time: Mapped[datetime | None] = mapped_column(DATETIME, nullable=True)
    status: Mapped[ExamAttemptStatusEnum] = mapped_column(SQLEnum(ExamAttemptStatusEnum, name="attempt_status_enum"), nullable=False, default=ExamAttemptStatusEnum.pending, index=True)
    final_score: Mapped[float | None] = mapped_column(DECIMAL(7, 2), nullable=True)
    last_heartbeat: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

    # Relationships
    exam: Mapped["Exam"] = relationship("Exam", back_populates="attempts")
    user: Mapped["User"] = relationship("User", back_populates="exam_attempts")
    attempt_paper: Mapped[List["ExamAttemptPaper"]] = relationship("ExamAttemptPaper", back_populates="attempt", cascade="all, delete-orphan") # Individual paper questions
    answers: Mapped[List["Answer"]] = relationship("Answer", back_populates="attempt", cascade="all, delete-orphan") # User's answers

    # __table_args__ = (UniqueConstraint('exam_id', 'user_id', name='uk_attempt_exam_user'),)

    def __repr__(self):
        return f"<ExamAttempt(id={self.id}, exam_id={self.exam_id}, user_id={self.user_id}, status='{self.status}')>"


class ExamAttemptPaper(Base):
    __tablename__ = "exam_attempt_papers"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True) # Use BIGINT
    attempt_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("exam_attempts.id", ondelete="CASCADE"), index=True) # Match type
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), index=True) # Consider RESTRICT
    score: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    attempt: Mapped["ExamAttempt"] = relationship("ExamAttempt", back_populates="attempt_paper")
    question: Mapped["Question"] = relationship("Question", back_populates="attempt_papers")

    # __table_args__ = (UniqueConstraint('attempt_id', 'question_id', name='uk_attempt_paper_question'),
    #                   UniqueConstraint('attempt_id', 'order_index', name='uk_attempt_paper_order'))

class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True) # Use BIGINT
    attempt_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("exam_attempts.id", ondelete="CASCADE"), index=True) # Match type
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), index=True) # Consider RESTRICT
    user_answer: Mapped[str | dict | list | None] = mapped_column(TEXT, nullable=True) # Use TEXT for flexibility, parse in app logic
    score: Mapped[float | None] = mapped_column(DECIMAL(5, 2), nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(BOOLEAN, nullable=True)
    grader_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    grading_comments: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    graded_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

    # Relationships
    attempt: Mapped["ExamAttempt"] = relationship("ExamAttempt", back_populates="answers")
    question: Mapped["Question"] = relationship("Question", back_populates="answers")
    grader: Mapped[Union["User", None]] = relationship("User", back_populates="graded_answers")

    # __table_args__ = (UniqueConstraint('attempt_id', 'question_id', name='uk_answer_attempt_question'),)

    def __repr__(self):
        return f"<Answer(id={self.id}, attempt_id={self.attempt_id}, question_id={self.question_id})>"
