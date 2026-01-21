from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class BaseEntity(BaseModel):
    """
    Base model for all domain entities.
    Example: ID, created_at, updated_at
    """
    model_config = ConfigDict(from_attributes=True)

class APIResponse(BaseModel):
    """
    Standard API Response wrapper.
    """
    status: str = "success"
    data: Optional[dict] = None
    message: Optional[str] = None
