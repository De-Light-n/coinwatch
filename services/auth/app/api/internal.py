import json
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as redis

from app.config import settings
from app.db import get_db
from app.models.models import User
from app.schemas.internal import QuotaResponse, VerifyTokenRequest, VerifyTokenResponse
from app.services.internal_service import get_plan_limits
from app.services.security import get_current_user_id

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

async def verify_service_token(x_service_token: str = Header(...)):
    if x_service_token != settings.INTERNAL_SERVICE_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service token")
    
router = APIRouter(prefix="/internal", tags=["internal"], dependencies=[Depends(verify_service_token)])

@router.get("/users/{user_id}/quota", response_model=QuotaResponse)
async def get_user_quota(user_id: str, db: AsyncSession = Depends(get_db)):
    cache_key = f"quota:{user_id}"
    
    cached_quota = await redis_client.get(cache_key)
    if cached_quota:
        return json.loads(cached_quota)

    try:
        query = select(User).where(User.id == UUID(user_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")
        
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found or inactive")

    plan = getattr(user, 'plan', 'free')
    limits = get_plan_limits(plan)
    
    quota = QuotaResponse(
        user_id=str(user.id),
        plan=plan,
        limits=limits,
        valid_until=None
    )

    await redis_client.setex(cache_key, 300, quota.model_dump_json())
    
    return quota

@router.post("/auth/verify-token", response_model=VerifyTokenResponse)
async def verify_token(req: VerifyTokenRequest, db: AsyncSession = Depends(get_db)):
    try:
        user_id = get_current_user_id(req.access_token)
        query = select(User).where(User.id == UUID(user_id))
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Invalid credentials")
            
        return VerifyTokenResponse(
            user_id=str(user.id),
            role=str(user.role).replace("userrole.", ""), 
            plan=getattr(user, 'plan', 'free'),
            is_active=user.is_active
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")