from typing import List, Optional
from sqlmodel import Session, select
from app.modules.authorization.models.role import Role
from app.modules.authorization.models.permission import Permission
from app.modules.authorization.models.role_permission import RolePermission
from app.modules.authorization.schemas.role import RoleCreate, RoleUpdate

class RoleService:
    def __init__(self, session: Session):
        self.session = session

    def get_role(self, role_id: int) -> Optional[Role]:
        return self.session.get(Role, role_id)

    def get_role_by_name(self, name: str) -> Optional[Role]:
        return self.session.exec(select(Role).where(Role.name == name)).first()

    def list_roles(self, skip: int = 0, limit: int = 100) -> List[Role]:
        return self.session.exec(select(Role).offset(skip).limit(limit)).all()



    def create_role(self, role_in: RoleCreate) -> Role:
        if not role_in.permission_ids:
            raise ValueError("Role must have at least one permission")

        # Validate permissions exist
        # We can fetch all requested permissions to verify they exist
        existing_perms = self.session.exec(select(Permission).where(Permission.id.in_(role_in.permission_ids))).all()
        found_ids = {p.id for p in existing_perms}
        missing_ids = set(role_in.permission_ids) - found_ids
        
        if missing_ids:
            raise ValueError(f"Permissions not found: {missing_ids}")

        db_role = Role.model_validate(role_in)
        self.session.add(db_role)
        self.session.commit()
        self.session.refresh(db_role)
        
        # Link permissions
        for perm_id in role_in.permission_ids:
            link = RolePermission(role_id=db_role.id, permission_id=perm_id)
            self.session.add(link)
            
        self.session.commit()
        self.session.refresh(db_role)
        return db_role

    def update_role(self, role_id: int, role_in: RoleUpdate) -> Optional[Role]:
        db_role = self.get_role(role_id)
        if not db_role:
            return None
        
        role_data = role_in.model_dump(exclude_unset=True)
        for key, value in role_data.items():
            setattr(db_role, key, value)
            
        self.session.add(db_role)
        self.session.commit()
        self.session.refresh(db_role)
        return db_role

    def delete_role(self, role_id: int) -> bool:
        db_role = self.get_role(role_id)
        if not db_role:
            return False
        
        self.session.delete(db_role)
        self.session.commit()
        return True

class PermissionService:
    def __init__(self, session: Session):
        self.session = session

    def list_permissions(self, skip: int = 0, limit: int = 100) -> List[Permission]:
        return self.session.exec(select(Permission).offset(skip).limit(limit)).all()
