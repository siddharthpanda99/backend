from typing import Optional, List
from app.modules.authorization.models.role import Role
from app.modules.authorization.schemas.permission import PermissionRead
from sqlmodel import SQLModel

class RoleBase(SQLModel):
    name: str
    description: Optional[str] = None

class RoleCreate(RoleBase):
    permission_ids: List[int]

class RoleUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None

class RoleRead(RoleBase):
    id: int
    permissions: List[PermissionRead] = []
