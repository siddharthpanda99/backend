from sqlmodel import Session, select, SQLModel
from app.modules.database.service.connection import engine
from app.core.security import get_password_hash
from app.modules.users.models.user import User
from app.modules.authorization.models.role import Role
from app.modules.authorization.models.permission import Permission
from app.modules.authorization.models.role_permission import RolePermission
from app.modules.authorization.models.role_permission import RolePermission
from app.modules.authorization.models.user_role import UserRole
from app.modules.projects.models.project import Project # Ensure Project is registered

def seed_db():
    print("Initialize DB Tables...")
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        # 1. Create Permissions
        print("Seeding Permissions...")
        permissions_data = [
            {"name": "manage_users", "resource": "users", "action": "manage", "description": "Full access to users"},
            {"name": "read_users", "resource": "users", "action": "read", "description": "Read access to users"},
            {"name": "manage_projects", "resource": "projects", "action": "manage", "description": "Full access to projects"},
            {"name": "manage_roles", "resource": "roles", "action": "manage", "description": "Full access to roles"},
        ]
        
        db_permissions = {}
        for perm_data in permissions_data:
            existing = session.exec(select(Permission).where(Permission.name == perm_data["name"])).first()
            if not existing:
                perm = Permission(**perm_data)
                session.add(perm)
                db_permissions[perm_data["name"]] = perm
            else:
                db_permissions[perm_data["name"]] = existing
        session.commit()

        # 2. Create Roles
        print("Seeding Roles...")
        roles_data = [
            {"name": "admin", "description": "Administrator with full access"},
            {"name": "user", "description": "Standard user access"},
        ]
        
        db_roles = {}
        for role_data in roles_data:
            existing = session.exec(select(Role).where(Role.name == role_data["name"])).first()
            if not existing:
                role = Role(**role_data)
                session.add(role)
                db_roles[role_data["name"]] = role
            else:
                db_roles[role_data["name"]] = existing
        session.commit()

        # 3. Assign Permissions to Roles
        print("Assigning Permissions to Roles...")
        # Admin gets everything
        admin_role = db_roles["admin"]
        for perm_name, perm in db_permissions.items():
            # Check if link exists
            link = session.exec(select(RolePermission).where(
                RolePermission.role_id == admin_role.id,
                RolePermission.permission_id == perm.id
            )).first()
            if not link:
                session.add(RolePermission(role_id=admin_role.id, permission_id=perm.id))
        
        # User gets read_users (example)
        user_role = db_roles["user"]
        read_users_perm = db_permissions.get("read_users")
        if read_users_perm:
             link = session.exec(select(RolePermission).where(
                RolePermission.role_id == user_role.id,
                RolePermission.permission_id == read_users_perm.id
            )).first()
             if not link:
                 session.add(RolePermission(role_id=user_role.id, permission_id=read_users_perm.id))
        
        session.commit()

        # 4. Create Admin User
        print("Creating Admin User...")
        admin_email = "admin@nexus.ai"
        existing_admin = session.exec(select(User).where(User.email == admin_email)).first()
        
        if not existing_admin:
            admin_user = User(
                email=admin_email,
                username="admin_nexus",
                hashed_password=get_password_hash("admin123"),
                full_name="System Administrator",
                is_active=True
            )
            session.add(admin_user)
            session.commit()
            session.refresh(admin_user)
            
            # Assign Admin Role
            session.add(UserRole(user_id=admin_user.id, role_id=admin_role.id))
            session.commit()
            print(f"Admin User created: {admin_email} / admin123")
        else:
            print("Admin User already exists. Resetting password to admin123...")
            existing_admin.hashed_password = get_password_hash("admin123")
            session.add(existing_admin)
            session.commit()
            print("Admin User password reset.")

    print("Seeding Complete!")

if __name__ == "__main__":
    seed_db()
