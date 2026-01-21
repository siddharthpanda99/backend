from typing import Optional, Dict, List
from datetime import datetime
from sqlmodel import Field, Column, JSON, Relationship
from app.modules.common.models.index import BaseModel
from app.modules.authorization.models.user_role import UserRole

class User(BaseModel, table=True):
    __tablename__ = "users"

    # Profile Info
    username: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    full_name: Optional[str] = None
    bio: Optional[str] = None
    profile_picture_url: Optional[str] = None
    cover_picture_url: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    gender: Optional[str] = None

    # Contact & Address
    phone_number: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None

    # Socials
    social_handles: Optional[Dict[str, str]] = Field(default={}, sa_column=Column(JSON))

    # Status & Metadata
    is_active: bool = Field(default=True)
    last_login_at: Optional[datetime] = None

    roles: List["Role"] = Relationship(back_populates="users", link_model=UserRole)
    projects: List["Project"] = Relationship(back_populates="created_by")
