from pydantic import BaseModel, ConfigDict
from typing import Optional, Generic, TypeVar, Dict, Any

T = TypeVar("T")

class APIResponse(BaseModel, Generic[T]):
    """
    Standard API Response wrapper.
    """
    status: str = "success"
    message: Optional[str] = None
    data: Optional[T] = None
    meta: Optional[Dict[str, Any]] = None
    model_config = ConfigDict(from_attributes=True)
