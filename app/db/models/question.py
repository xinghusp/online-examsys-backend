from sqlalchemy import Column, Integer, String, TIMESTAMP, text, TEXT, ForeignKey, Enum as SQLEnum, DECIMAL, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.db.base_class import Base
from typing import List, TYPE_CHECKING, Any, Union
from datetime import datetime
import enum

if TYPE_CHECKING:
    from .user import User
    from .exam import ExamQuestion, ExamAttemptPaper, Answer

class QuestionTypeEnum(str, enum.Enum):
    single_choice = "single_choice"
    multiple_choice = "multiple_choice"
    fill_in_blank = "fill_in_blank"
    short_answer = "short_answer"

class QuestionLib(Base):
    __tablename__ = "question_libs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Union[str, None]] = mapped_column(TEXT, nullable=True)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    creator_id: Mapped[Union[int, None]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

    # Relationships
    creator: Mapped[Union["User", None]] = relationship("User", back_populates="created_question_libs")
    chapters: Mapped[List["Chapter"]] = relationship("Chapter", back_populates="question_lib", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<QuestionLib(id={self.id}, name='{self.name}')>"

class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_lib_id: Mapped[int] = mapped_column(Integer, ForeignKey("question_libs.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Union[str, None]] = mapped_column(TEXT, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

    # Relationships
    question_lib: Mapped["QuestionLib"] = relationship("QuestionLib", back_populates="chapters")
    questions: Mapped[List["Question"]] = relationship("Question", back_populates="chapter", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Chapter(id={self.id}, name='{self.name}', lib_id={self.question_lib_id})>"

class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(Integer, ForeignKey("chapters.id", ondelete="CASCADE"), index=True)
    question_type: Mapped[QuestionTypeEnum] = mapped_column(SQLEnum(QuestionTypeEnum, name="question_type_enum"), nullable=False, index=True)
    stem: Mapped[str] = mapped_column(TEXT, nullable=False)
    score: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=False, default=1.00)
    options: Mapped[Union[dict, list, None]] = mapped_column(JSON, nullable=True) # Flexible options storage
    answer: Mapped[Union[dict, list, str, None]] = mapped_column(JSON, nullable=True) # Flexible answer storage
    grading_strategy: Mapped[Union[dict, None]] = mapped_column(JSON, nullable=True)
    explanation: Mapped[Union[str, None]] = mapped_column(TEXT, nullable=True)
    creator_id: Mapped[Union[int, None]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

    # Relationships
    chapter: Mapped["Chapter"] = relationship("Chapter", back_populates="questions")
    creator: Mapped[Union["User", None]] = relationship("User", back_populates="created_questions")
    exam_papers: Mapped[List["ExamQuestion"]] = relationship("ExamQuestion", back_populates="question") # Used in fixed papers
    attempt_papers: Mapped[List["ExamAttemptPaper"]] = relationship("ExamAttemptPaper", back_populates="question") # Used in individual random papers
    answers: Mapped[List["Answer"]] = relationship("Answer", back_populates="question") # User answers to this question

    def __repr__(self):
        return f"<Question(id={self.id}, type='{self.question_type}', chapter_id={self.chapter_id})>"
