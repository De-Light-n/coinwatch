from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str    

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