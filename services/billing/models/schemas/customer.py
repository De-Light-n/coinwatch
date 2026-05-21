import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr
from .base import SchemaBase

class CustomerBase(SchemaBase):
    stripe_customer_id: str
    email: EmailStr

class CustomerCreate(CustomerBase):
    pass

class CustomerOut(CustomerBase):
    user_id: uuid.UUID
    created_at: datetime
