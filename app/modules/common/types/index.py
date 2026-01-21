from pydantic import BaseModel, ConfigDict
from typing import Optional, Generic, TypeVar

T = TypeVar("T")

class APIResponse(BaseModel, Generic[T]):
    """
    Standard API Response wrapper.
    """
    status: str = "success"
    message: Optional[str] = None
    data: Optional[T] = None
    model_config = ConfigDict(from_attributes=True)
