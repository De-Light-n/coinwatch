from pydantic import BaseModel, EmailStr
from datetime import datetime
from uuid import UUID

class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class UserUpdate(BaseModel):
    full_name: str | None = None

class ChangePassword(BaseModel):
    old_password: str
    new_password: str

class AdminUserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None