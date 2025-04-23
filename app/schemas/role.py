from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

# Import Permission schema for nesting
from .permission import Permission

# Shared properties
class RoleBase(BaseModel):
    name: str = Field(..., max_length=100, description="Unique role name (e.g., Admin, Examiner)")
    description: Optional[str] = Field(None, description="Detailed description of the role")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "name": "Exam Proctor",
                "description": "Can monitor ongoing exams and manage participants."
            }
        }
    )

# Properties to receive on item creation
class RoleCreate(RoleBase):
    permission_ids: List[int] = Field([], description="List of permission IDs to assign initially")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Grader",
                "description": "Can grade short answer questions.",
                "permission_ids": [5, 6] # Example IDs
            }
        }
    )


# Properties to receive on item update
class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None)
    permission_ids: Optional[List[int]] = Field(None, description="Replace existing permissions with this list of IDs")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "description": "Can grade short answer questions and view results.",
                "permission_ids": [5, 6, 7] # Example IDs
            }
        }
    )

# Properties stored in DB
class RoleInDB(RoleBase):
    id: int
    created_at: datetime
    updated_at: datetime
    permissions: List[Permission] = [] # Include permissions when loading from DB

# Properties to return to client
class Role(RoleInDB):
    pass # Inherit all, including permissions list

# Schema for assigning roles to a user
class UserAssignRoles(BaseModel):
    role_ids: List[int] = Field(..., description="List of Role IDs to assign to the user (replaces existing roles)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "role_ids": [1, 3]
            }
        }
    )