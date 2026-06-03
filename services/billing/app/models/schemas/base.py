from pydantic import BaseModel

class SchemaBase(BaseModel):
    class Config:
        from_attributes = True
