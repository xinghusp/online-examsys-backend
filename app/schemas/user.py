from pydantic import BaseModel, Field, ConfigDict, field_validator, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
import enum

# Re-use or define the enum here as well for validation
class UserStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"

# Base properties shared by other schemas
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=100, description="Unique username for login")
    id_number: Optional[str] = Field(None, max_length=50, description="Optional ID number (unique if provided)")
    full_name: Optional[str] = Field(None, max_length=100, description="Optional full name")
    status: UserStatus = Field(UserStatus.active, description="User status")

    model_config = ConfigDict(
        from_attributes=True, # Allow creating schema from ORM model
        # Pydantic v2 uses 'json_schema_extra' for examples
        json_schema_extra={
            "example": {
                "username": "johndoe",
                "id_number": "S12345",
                "full_name": "John Doe",
                "status": "active",
            }
        }
    )

# Properties required for user creation
class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="User password (will be hashed)")

    @field_validator('username')
    @classmethod
    def username_alphanumeric(cls, v):
        assert v.isalnum(), 'Username must be alphanumeric'
        return v

    model_config = ConfigDict(
         json_schema_extra={
            "example": {
                "username": "newuser",
                "password": "SecurePassword123",
                "id_number": "EMP007",
                "full_name": "Jane Smith",
                "status": "active",
            }
        }
    )


# Properties required for user update
class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    password: Optional[str] = Field(None, min_length=8, description="New password (if changing)")
    id_number: Optional[str] = Field(None, max_length=50)
    full_name: Optional[str] = Field(None, max_length=100)
    status: Optional[UserStatus] = None

    model_config = ConfigDict(
         json_schema_extra={
            "example": {
                "full_name": "Johnathan Doe",
                "status": "disabled",
            }
        }
    )

# Properties stored in DB (used internally, not directly in API response unless needed)
class UserInDBBase(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

# Properties to return to client (omits password hash)
class User(UserInDBBase):
    pass # Inherits all from UserInDBBase for now

# Schema for user login
class UserLogin(BaseModel):
    username: str # Or potentially allow login via id_number + full_name later
    password: str

    model_config = ConfigDict(
         json_schema_extra={
            "example": {
                "username": "testuser",
                "password": "password123"
            }
        }
    )
# --- Schema for User record in Bulk Import ---
class UserImportRecord(BaseModel):
    username: str = Field(..., description="Username (must be unique)")
    id_number: Optional[str] = Field(None, description="ID Number (must be unique if provided)")
    fullname: Optional[str] = Field(None, max_length=255, description="User's full name")
    password: str = Field(..., description="User's initial password (will be hashed)")

# --- Schema for Bulk Import Response ---
class UserBulkImportResponse(BaseModel):
    success_count: int = 0
    failed_count: int = 0
    errors: List[Dict[str, Any]] = Field([], description="List of errors encountered (e.g., row number, error message)")