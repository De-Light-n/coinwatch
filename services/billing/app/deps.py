from typing import Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db import get_db
from fastapi import Depends, HTTPException, status
from fastapi.security.http import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import httpx
import structlog

logger = structlog.get_logger()
security = HTTPBearer()


class User:
    """User object extracted from JWT"""
    def __init__(self, user_id: uuid.UUID, email: str):
        self.id = user_id
        self.email = email
        self.stripe_customer_id: Optional[str] = None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Extract and validate JWT token to get current user.
    
    Expected JWT payload:
    {
        "sub": "user_uuid",
        "email": "user@example.com"
    }
    """
    token = credentials.credentials
    
    try:
        # In development, we can decode without verification
        # In production, you should verify the signature with your auth service's public key
        payload = jwt.decode(
            token, 
            options={"verify_signature": False}  # ← For now, just decode
        )
        
        user_id = payload.get("sub")
        email = payload.get("email")
        
        if not user_id or not email:
            logger.warning("invalid_token_payload", token=token[:20])
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        # Convert string UUID to UUID object
        try:
            user_id = uuid.UUID(user_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user ID format"
            )
        
        user = User(user_id=user_id, email=email)
        
        # Optionally fetch user's Stripe customer ID from database
        from app.models import Customer
        result = await db.execute(
            select(Customer).where(Customer.user_id == user_id)
        )
        customer = result.scalar_one_or_none()
        if customer:
            user.stripe_customer_id = customer.stripe_customer_id
        
        logger.info("user_authenticated", user_id=str(user_id))
        return user
        
    except jwt.DecodeError as e:
        logger.warning("token_decode_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("auth_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )