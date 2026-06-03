import uuid
import structlog
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from fastapi import HTTPException, status
from uuid import UUID

from app.models.models import User, RefreshToken
from app.services.security import verify_password, get_password_hash, create_access_token
from app.schemas.user import UserUpdate, ChangePassword, AdminUserUpdate

logger = structlog.get_logger()

async def register_user(db: AsyncSession, user_data):
    query = select(User).where(User.email == user_data.email)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        password_hash=hashed_password,
        full_name=user_data.full_name,
        role="USER",
        is_active=True
    )
    db.add(new_user)
    await db.commit()
    return new_user

async def login_user(db: AsyncSession, email: str, password: str):
    query = select(User).where(User.email == email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash) or not user.is_active:
        logger.warning("Failed login attempt", email=email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    logger.info("Successful login", email=email)

    access_token = create_access_token(data={"sub": str(user.id), "role": user.role, "plan": "free"})
    refresh_token_value = uuid.uuid4().hex
    expires = datetime.now(timezone.utc) + timedelta(days=30)
    
    db_token = RefreshToken(
        user_id=user.id,
        token_hash=refresh_token_value,
        revoked=False,
        expires_at=expires
    )
    db.add(db_token)
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_value,
        "token_type": "bearer"
    }

async def refresh_tokens(db: AsyncSession, refresh_token: str):
    query = select(RefreshToken).where(
        RefreshToken.token_hash == refresh_token,
        RefreshToken.revoked == False
    )
    result = await db.execute(query)
    db_token = result.scalar_one_or_none()

    if not db_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if db_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        db_token.revoked = True
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    db_token.revoked = True

    query_user = select(User).where(User.id == db_token.user_id)
    result_user = await db.execute(query_user)
    user = result_user.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = create_access_token(data={"sub": str(user.id), "role": user.role, "plan": "free"})
    new_refresh_token_value = uuid.uuid4().hex
    expires = datetime.now(timezone.utc) + timedelta(days=30)

    new_db_token = RefreshToken(
        user_id=user.id,
        token_hash=new_refresh_token_value,
        revoked=False,
        expires_at=expires
    )
    db.add(new_db_token)
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token_value,
        "token_type": "bearer"
    }

async def logout_user(db: AsyncSession, user_id: str):
    stmt = update(RefreshToken).where(
        RefreshToken.user_id == UUID(user_id),
        RefreshToken.revoked == False
    ).values(revoked=True)
    
    await db.execute(stmt)
    await db.commit()

async def update_me(db: AsyncSession, user: User, update_data: UserUpdate):
    if update_data.full_name is not None:
        user.full_name = update_data.full_name
    await db.commit()
    await db.refresh(user)
    return user

async def change_user_password(db: AsyncSession, user: User, passwords: ChangePassword):
    if not verify_password(passwords.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    user.password_hash = get_password_hash(passwords.new_password)
    await db.commit()

async def soft_delete_user(db: AsyncSession, user: User):
    user.is_active = False
    stmt = update(RefreshToken).where(
        RefreshToken.user_id == user.id,
        RefreshToken.revoked == False
    ).values(revoked=True)
    await db.execute(stmt)
    await db.commit()

async def get_all_users(db: AsyncSession, skip: int, limit: int, search: str | None):
    query = select(User)
    if search:
        query = query.where(User.email.ilike(f"%{search}%"))
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

async def get_user_by_id(db: AsyncSession, user_id: str):
    try:
        query = select(User).where(User.id == UUID(user_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
        
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

async def update_user_by_admin(db: AsyncSession, user_id: str, update_data: AdminUserUpdate):
    user = await get_user_by_id(db, user_id)
    if update_data.role is not None:
        user.role = update_data.role
    if update_data.is_active is not None:
        user.is_active = update_data.is_active
    await db.commit()
    await db.refresh(user)
    return user