from pydantic import EmailStr, field_validator
from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel
from app.modules.users.models.user import User

class UserBase(SQLModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True

class UserCreate(UserBase):
    password: str

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v

class UserUpdate(SQLModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

class UserRead(UserBase):
    id: int
    last_login_at: Optional[datetime] = None
