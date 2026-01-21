from typing import List, Optional
from sqlmodel import Field, Relationship
from app.modules.common.models.index import BaseModel
from .permission import Permission
from .role_permission import RolePermission
from .user_role import UserRole

class Role(BaseModel, table=True):
    __tablename__ = "roles"
    
    name: str = Field(unique=True, index=True)
    description: Optional[str] = None
    
    permissions: List["Permission"] = Relationship(link_model=RolePermission)
    users: List["User"] = Relationship(back_populates="roles", link_model=UserRole)
