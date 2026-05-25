import httpx
from pydantic import BaseModel
from fastapi import HTTPException, status
from types import SimpleNamespace
from app.config import settings

class UserQuotaResponse(BaseModel):
    
    user_id: str
    plan: str
    limits: dict

    @property
    def max_watches(self) -> int:
        
        return self.limits.get("max_watches", 5)

    @property
    def check_interval_seconds(self) -> int:
        return self.limits.get("check_interval_seconds", 60)


class AuthClient:
    def __init__(self):
        
        self.base_url = settings.AUTH_SERVICE_URL
        self.service_token = settings.INTERNAL_SERVICE_TOKEN 

    async def get_current_user(self, user_jwt_token: str) -> SimpleNamespace:
        if not user_jwt_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Missing token"
            )
            
        headers = {
            "x-service-token": self.service_token
        }
        
        
        json_body = {
            "access_token": user_jwt_token
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/internal/auth/verify-token",
                    headers=headers,
                    json=json_body  
                )
                
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid token or unauthorized"
                    )
                
                user_data = response.json()
                
                
                return SimpleNamespace(
                    id=user_data.get("user_id"),
                    role=user_data.get("role"),
                    plan=user_data.get("plan"),
                    username="user"  
                )
                
            except httpx.RequestError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Auth service connection error: {exc}"
                )

    async def get_user_quota(self, user_id: str) -> UserQuotaResponse:
        headers = {
            "x-service-token": self.service_token,
        }
        
        async with httpx.AsyncClient() as client:
            try:
                
                response = await client.get(
                    f"{self.base_url}/internal/users/{user_id}/quota",
                    headers=headers
                )
                
                if response.status_code == 404:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND, 
                        detail="User quota settings not found"
                    )
                elif response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to fetch user quota"
                    )
                
                return UserQuotaResponse(**response.json())
                
            except httpx.RequestError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Auth service connection error: {exc}"
                )