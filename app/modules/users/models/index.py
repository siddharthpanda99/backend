from typing import Optional
from sqlmodel import Field
from app.modules.common.models.index import BaseModel

class User(BaseModel, table=True):
    """
    User database entity.
    """
    username: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    full_name: Optional[str] = None
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
