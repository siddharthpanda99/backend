from typing import Optional
from sqlmodel import Field, SQLModel

class RolePermission(SQLModel, table=True):
    __tablename__ = "role_permissions"
    
    role_id: Optional[int] = Field(default=None, foreign_key="roles.id", primary_key=True)
    permission_id: Optional[int] = Field(default=None, foreign_key="permissions.id", primary_key=True)
