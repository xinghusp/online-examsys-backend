from sqlalchemy import Column, Integer, String, TIMESTAMP, text, TEXT, Table, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.db.base_class import Base
from typing import List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from .user import User, user_roles_table

# Association table for role_permissions
role_permissions_table = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)

class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

    # Relationships
    users: Mapped[List["User"]] = relationship("User", secondary="user_roles", back_populates="roles") # Use table name string
    permissions: Mapped[List["Permission"]] = relationship("Permission", secondary=role_permissions_table, back_populates="roles")

    def __repr__(self):
        return f"<Role(id={self.id}, name='{self.name}')>"

class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(TEXT, nullable=True)

    # Relationships
    roles: Mapped[List["Role"]] = relationship("Role", secondary=role_permissions_table, back_populates="permissions")

    def __repr__(self):
        return f"<Permission(id={self.id}, code='{self.code}')>"
