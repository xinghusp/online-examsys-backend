from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

# Shared properties
class PermissionBase(BaseModel):
    code: str = Field(..., max_length=100, description="Unique permission code (e.g., manage_users)")
    description: Optional[str] = Field(None, description="Detailed description of the permission")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "code": "manage_exams",
                "description": "Allows creating, editing, and publishing exams."
            }
        }
    )

# Properties to receive on item creation (usually same as base for permissions)
class PermissionCreate(PermissionBase):
    pass

# Properties to receive on item update (maybe only description is updatable)
class PermissionUpdate(BaseModel):
    description: Optional[str] = Field(None, description="Updated description")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "description": "Allows full management of examination process."
            }
        }
    )

# Properties stored in DB
class PermissionInDB(PermissionBase):
    id: int

# Properties to return to client
class Permission(PermissionInDB):
    pass # Inherit all from PermissionInDB