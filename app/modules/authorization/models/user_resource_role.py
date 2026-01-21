from typing import Optional
from sqlmodel import Field, SQLModel

class UserResourceRole(SQLModel, table=True):
    __tablename__ = "user_resource_roles"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    user_id: int = Field(foreign_key="users.id", index=True)
    role_id: int = Field(foreign_key="roles.id", index=True)
    
    resource_type: str = Field(index=True) # e.g. "project", "team"
    resource_id: str = Field(index=True)   # ID of the resource instance
