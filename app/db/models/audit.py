from sqlalchemy import Column, Integer, String, TIMESTAMP, text, TEXT, ForeignKey, Enum as SQLEnum, DECIMAL, JSON, DATETIME, BOOLEAN, BIGINT
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.db.base_class import Base
from typing import List, TYPE_CHECKING, Optional, Any, Union
from datetime import datetime

if TYPE_CHECKING:
    from .user import User

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True) # Use BIGINT
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    action: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    target_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True) # Keep as string if IDs can be non-numeric
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"), index=True)

    # Relationships
    user: Mapped[Union["User", None]] = relationship("User", back_populates="audit_logs")

    def __repr__(self):
        user_info = f"user_id={self.user_id}" if self.user_id else "system"
        return f"<AuditLog(id={self.id}, action='{self.action}', {user_info})>"
