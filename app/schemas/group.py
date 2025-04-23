from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

# Shared properties
class GroupBase(BaseModel):
    name: str = Field(..., max_length=100, description="Unique group name (e.g., Class A, Department B)")
    description: Optional[str] = Field(None, description="Group description")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "name": "Spring 2025 Cohort",
                "description": "Students enrolled in the Spring 2025 semester."
            }
        }
    )

# Properties to receive on item creation
class GroupCreate(GroupBase):
    user_ids: List[int] = Field([], description="List of user IDs to add to the group initially")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Beta Testers",
                "description": "Users participating in beta testing.",
                "user_ids": [101, 105, 210]
            }
        }
    )

# Properties to receive on item update
class GroupUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None)
    user_ids: Optional[List[int]] = Field(None, description="Replace existing users in the group with this list of IDs")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Beta Testers (Active)",
                "user_ids": [101, 210, 305] # Updated list
            }
        }
    )


# Properties stored in DB
class GroupInDB(GroupBase):
    id: int
    created_at: datetime
    updated_at: datetime
    # We might not load all users by default for performance, maybe just count or specific queries
    # users: List[User] = [] # Define User schema if needed here

# Properties to return to client
class Group(GroupInDB):
    # Add user_count or other relevant fields if needed for responses
    user_count: int = Field(0, description="Number of users in the group") # Example derived field

# Schema for assigning users to a group (similar to GroupUpdate but explicit)
class GroupAssignUsers(BaseModel):
    user_ids: List[int] = Field(..., description="List of User IDs to set for this group (replaces existing users)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_ids": [1, 5, 10, 25]
            }
        }
    )