from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData

# Optional: Define naming conventions for constraints
# Helps maintain consistency in database schema naming
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Create metadata with the naming convention
metadata = MetaData(naming_convention=convention)

class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""
    metadata = metadata
    # You could add common columns here like id, created_at, updated_at if desired
    # e.g., id: Mapped[int] = mapped_column(primary_key=True, index=True)