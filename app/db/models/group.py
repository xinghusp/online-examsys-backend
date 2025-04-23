from sqlalchemy import Column, Integer, String, TIMESTAMP, text, TEXT
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.db.base_class import Base
from typing import List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from .user import User, user_groups_table
    from .exam import ExamParticipant # Added for relationship

class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

    # Relationships
    users: Mapped[List["User"]] = relationship("User", secondary="user_groups", back_populates="groups") # Use table name string here
    exam_participations: Mapped[List["ExamParticipant"]] = relationship("ExamParticipant", back_populates="group") # Added relationship

    def __repr__(self):
        return f"<Group(id={self.id}, name='{self.name}')>"
