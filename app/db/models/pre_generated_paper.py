from sqlalchemy import Column, Integer, ForeignKey, DECIMAL, UniqueConstraint, BIGINT
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.db.base_class import Base
from typing import TYPE_CHECKING

# No direct relationships needed back from Question/User/Exam usually

class PreGeneratedPaper(Base):
    __tablename__ = "pre_generated_papers"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(Integer, ForeignKey("exams.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False) # Cascade ok? Or restrict?
    score: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Add constraints
    __table_args__ = (
        UniqueConstraint('exam_id', 'user_id', 'question_id', name='uq_pregen_exam_user_question'),
        UniqueConstraint('exam_id', 'user_id', 'order_index', name='uq_pregen_exam_user_order'),
        # Index for faster lookups when starting an attempt
        # Index('ix_pregen_exam_user', 'exam_id', 'user_id'), # Handled by unique constraints implicitly? Check DB.
    )

    def __repr__(self):
        return f"<PreGeneratedPaper(exam={self.exam_id}, user={self.user_id}, q={self.question_id})>"
