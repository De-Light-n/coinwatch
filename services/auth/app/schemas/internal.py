from pydantic import BaseModel
from typing import List
from datetime import datetime

class Limits(BaseModel):
    max_watches: int
    check_interval_seconds: int
    allowed_channels: List[str]

class QuotaResponse(BaseModel):
    user_id: str
    plan: str
    limits: Limits
    valid_until: datetime | None = None

class VerifyTokenRequest(BaseModel):
    access_token: str

class VerifyTokenResponse(BaseModel):
    user_id: str
    role: str
    plan: str
    is_active: bool