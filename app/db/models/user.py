# (Content from previous response, slightly updated with all relationships)
from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP, text, ForeignKey, Table, Enum as SQLEnum
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.db.base_class import Base
import enum
from typing import List, TYPE_CHECKING
from datetime import datetime

# Type checking imports to avoid circular dependencies
if TYPE_CHECKING:
    from .question import QuestionLib, Question
    from .exam import Exam, ExamAttempt, Answer, AuditLog
    from .role import Role, Permission # Assuming Role and Permission are in role.py
    from .group import Group # Assuming Group is in group.py

# Define Enum for status
class UserStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"

# Association table for many-to-many relationship between users and groups
user_groups_table = Table(
    "user_groups",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", Integer, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
)

# Association table for many-to-many relationship between users and roles
user_roles_table = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    id_number: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[UserStatus] = mapped_column(SQLEnum(UserStatus, name="user_status_enum"), nullable=False, default=UserStatus.active, server_default=UserStatus.active.value)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

    # Relationships
    groups: Mapped[List["Group"]] = relationship("Group", secondary=user_groups_table, back_populates="users")
    roles: Mapped[List["Role"]] = relationship("Role", secondary=user_roles_table, back_populates="users")

    # Relationships to items created/managed by the user
    created_question_libs: Mapped[List["QuestionLib"]] = relationship("QuestionLib", back_populates="creator")
    created_questions: Mapped[List["Question"]] = relationship("Question", back_populates="creator")
    created_exams: Mapped[List["Exam"]] = relationship("Exam", back_populates="creator")
    exam_attempts: Mapped[List["ExamAttempt"]] = relationship("ExamAttempt", back_populates="user")
    graded_answers: Mapped[List["Answer"]] = relationship("Answer", back_populates="grader") # Answers graded by this user
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"
