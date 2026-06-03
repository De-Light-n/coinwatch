from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address
from typing import List

from app.schemas.auth import UserRegister, UserLogin, RefreshRequest, TokenResponse
from app.schemas.user import UserResponse, UserUpdate, ChangePassword, AdminUserUpdate
from app.services.auth_service import (
    register_user, login_user, refresh_tokens, logout_user,
    update_me, change_user_password, soft_delete_user,
    get_all_users, get_user_by_id, update_user_by_admin
)
from app.services.security import get_current_user_id, get_current_user, get_admin_user
from app.db import get_db
from app.models.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    await register_user(db, user_data)
    return {"message": "User created"}

@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    return await login_user(db, user_data.email, user_data.password)

@router.post("/swagger-login", include_in_schema=False)
async def swagger_login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    return await login_user(db, form_data.username, form_data.password)

@router.post("/refresh", response_model=TokenResponse)
async def refresh(refresh_data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    return await refresh_tokens(db, refresh_data.refresh_token)

@router.post("/logout")
async def logout(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    await logout_user(db, user_id)
    return {"message": "Successfully logged out"}

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.patch("/me", response_model=UserResponse)
async def update_user_me(update_data: UserUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await update_me(db, current_user, update_data)

@router.post("/me/change-password")
async def change_password_me(passwords: ChangePassword, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await change_user_password(db, current_user, passwords)
    return {"message": "Password updated"}

@router.delete("/me")
async def delete_user_me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await soft_delete_user(db, current_user)
    return {"message": "User deleted"}

@router.get("/users", response_model=List[UserResponse])
async def read_users(skip: int = 0, limit: int = 10, search: str | None = None, admin_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    return await get_all_users(db, skip, limit, search)

@router.get("/users/{user_id}", response_model=UserResponse)
async def read_user_by_id(user_id: str, admin_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    return await get_user_by_id(db, user_id)

@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user_admin(user_id: str, update_data: AdminUserUpdate, admin_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    return await update_user_by_admin(db, user_id, update_data)