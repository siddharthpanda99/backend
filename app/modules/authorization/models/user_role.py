from typing import Optional
from sqlmodel import Field, SQLModel

class UserRole(SQLModel, table=True):
    __tablename__ = "user_roles"
    
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", primary_key=True)
    role_id: Optional[int] = Field(default=None, foreign_key="roles.id", primary_key=True)
