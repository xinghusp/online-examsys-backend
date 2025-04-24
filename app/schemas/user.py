from pydantic import BaseModel, EmailStr, ConfigDict, field_validator
from typing import Optional, List
from datetime import datetime

# Assuming schemas.role.Role and schemas.permission.Permission are defined elsewhere
# and have the necessary 'from_attributes=True' config
from .role import Role

# Base properties - align with DB columns where possible
class UserBase(BaseModel):
    username: str
    full_name: Optional[str] = None # DB uses full_name, handle mapping if needed
    id_number: Optional[str] = None
    status: Optional[str] = 'active' # Use status string, default to 'active'

# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str
    role_ids: Optional[List[int]] = []
    # Map fullname if API receives it but DB expects full_name
    # fullname: Optional[str] = Field(None, alias='full_name')

# Properties to receive via API on update
class UserUpdate(UserBase):
    password: Optional[str] = None
    role_ids: Optional[List[int]] = None
    # Map fullname if API receives it but DB expects full_name
    # fullname: Optional[str] = Field(None, alias='full_name')

# Schema for user import row data
class UserImportRecord(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = None # Use fullname here as it matches excel_processor
    role_names: Optional[List[str]] = []
    group_names: Optional[List[str]] = []

    @field_validator('username', 'password', check_fields=False) # Pydantic v1 syntax
    def required_fields_not_empty(cls, v: str):
        if not v or not v.strip():
            raise ValueError('Username and Password cannot be empty')
        return v.strip()

    @field_validator('email', 'fullname', check_fields=False) # Pydantic v1 syntax
    def strip_optional_strings(cls, v: Optional[str]):
        return v.strip() if v else None

# Properties shared by models stored in DB - base for response
class UserInDBBase(UserBase):
    id: int
    # Use full_name if that's what the ORM model attribute is named
    full_name: Optional[str] = None # Align with DB column name used by ORM
    status: str # Status is NOT NULL in DB

    # Pydantic v2 config
    model_config = ConfigDict(from_attributes=True)
    # Pydantic v1 config (use one or the other)
    # class Config:
    #     orm_mode = True

# Properties to return to client (response_model)
class User(UserInDBBase):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    roles: Optional[List[Role]] = [] # Role schema needs permissions loaded

    # Config inherited or add explicitly

# Properties stored in DB (including sensitive fields)
class UserInDB(UserInDBBase):
    password_hash: str # Align with DB column name used by ORM

# Bulk import response schema
class BulkImportResponse(BaseModel):
    success_count: int
    failed_count: int
    errors: Optional[List[dict]] = None
