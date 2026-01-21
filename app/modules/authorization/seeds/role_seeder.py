from sqlmodel import Session, select
from app.modules.database.service.seeder_base import BaseSeeder
import yaml
import os
from app.modules.authorization.models.role import Role
from app.modules.authorization.models.permission import Permission
from app.modules.authorization.models.role_permission import RolePermission

class AuthorizationSeeder(BaseSeeder):
    key = "auth"
    dependencies = []

    def seed(self, session: Session):
        fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "roles.yaml")
        if not os.path.exists(fixture_path):
            print(f"Warning: Fixture file not found: {fixture_path}")
            return

        with open(fixture_path, "r") as f:
            data = yaml.safe_load(f)
            
        roles_data = data.get("roles", [])
        
        for r_data in roles_data:
            role_name = r_data["name"]
            role = session.exec(select(Role).where(Role.name == role_name)).first()
            if not role:
                role = Role(
                    name=role_name,
                    description=r_data.get("description")
                )
                session.add(role)
                session.commit()
                session.refresh(role)
            
            # Seed permissions
            perms = r_data.get("permissions", [])
            for p_data in perms:
                resource = p_data["resource"]
                action = p_data["action"]
                perm_name = p_data.get("name", f"{resource}:{action}")
                
                perm = session.exec(select(Permission).where(Permission.name == perm_name)).first()
                if not perm:
                    perm = Permission(
                        name=perm_name,
                        description=p_data.get("description", f"Can {action} {resource}"),
                        resource=resource,
                        action=action
                    )
                    session.add(perm)
                    session.commit()
                    session.refresh(perm)
                
                # Link Role -> Permission
                link = session.exec(select(RolePermission).where(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_id == perm.id
                )).first()
                
                if not link:
                    link = RolePermission(role_id=role.id, permission_id=perm.id)
                    session.add(link)
        
        session.commit()
