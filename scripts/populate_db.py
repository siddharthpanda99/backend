"""
Database Population Script for Agentic Platform.
Ensures PostgreSQL schemas, tables, roles, permissions, users, and domain seed data are initialized.

Usage:
    python scripts/populate_db.py
"""

import sys
import os
from pathlib import Path

# Bootstrap sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
COMMON_LIB_SRC = BACKEND_DIR.parent / "Python Libs" / "common_lib" / "src"
if str(COMMON_LIB_SRC) not in sys.path:
    sys.path.insert(0, str(COMMON_LIB_SRC))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text
from sqlmodel import Session, select, SQLModel
from common_lib.modules.data_storage.database.connection import engine, init_db
from common_lib.modules.project_management.init_db import get_pm_metadata
from common_lib.modules.secrets_manager.init_db import get_sm_metadata
import common_lib.modules.memory.blueprint_models
import common_lib.modules.auth.users.models
from common_lib.modules.auth.users.models import User
from common_lib.modules.auth.security import get_password_hash
from common_lib.modules.rbac.models import Role, UserRole
from common_lib.modules.rbac.service import seed_roles

from scripts.seed_pm_data import seed_pm_data
from scripts.seed_schema_data import seed_schema_data
from scripts.seed_all_scenarios import seed as seed_all_scenarios


def ensure_schemas() -> None:
    schemas = [
        "public",
        "daw",
        "governance",
        "observability",
        "security",
        "memory",
        "auth",
        "system",
        "file_system",
        "super_graph",
        "document_vault",
    ]
    with engine.connect() as conn:
        for s in schemas:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {s};"))
        conn.commit()
    print("[1/5] Database schemas verified.")


def ensure_tables() -> None:
    get_pm_metadata()
    get_sm_metadata()
    init_db()
    SQLModel.metadata.create_all(engine)
    print("[2/5] SQLModel tables verified.")


def ensure_users_and_rbac() -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT setval(pg_get_serial_sequence('users', 'id'), COALESCE((SELECT MAX(id) FROM users), 0) + 1, false);"))
        conn.commit()

    with Session(engine) as session:
        # Seed RBAC roles & permissions
        seed_roles(session)
        admin_role = session.exec(select(Role).where(Role.name == "admin")).first()

        # Dev user
        dev_user = session.exec(select(User).where(User.username == "dev_user")).first()
        if not dev_user:
            dev_user = User(
                username="dev_user",
                email="dev@example.com",
                hashed_password=get_password_hash("dev_user"),
                full_name="Developer User",
                is_active=True,
                email_verified=True,
            )
            session.add(dev_user)
            session.commit()
            session.refresh(dev_user)

        # Admin user (admin@nexus.ai)
        admin_user = session.exec(select(User).where(User.username == "admin")).first()
        if not admin_user:
            admin_user = User(
                username="admin",
                email="admin@nexus.ai",
                hashed_password=get_password_hash("nexus_password"),
                full_name="Nexus Administrator",
                is_active=True,
                email_verified=True,
            )
            session.add(admin_user)
            session.commit()
            session.refresh(admin_user)

        # Assign admin role to dev_user and admin_user
        if admin_role:
            for u in [dev_user, admin_user]:
                if u and u.id is not None:
                    existing_link = session.exec(
                        select(UserRole).where(
                            UserRole.user_id == u.id,
                            UserRole.role_id == admin_role.id,
                        )
                    ).first()
                    if not existing_link:
                        session.add(UserRole(user_id=u.id, role_id=admin_role.id))
            session.commit()
    print("[3/5] Users and RBAC roles verified.")


def populate() -> None:
    print("=" * 60)
    print("STARTING PLATFORM DATABASE POPULATION")
    print("=" * 60)
    ensure_schemas()
    ensure_tables()
    ensure_users_and_rbac()

    print("[4/5] Seeding domain data...")
    print("  -> Seeding Project Management data...")
    try:
        seed_pm_data()
    except Exception as e:
        print(f"  Warning: PM data seeding error: {e}")

    print("  -> Seeding App Builder Schema data...")
    try:
        seed_schema_data()
    except Exception as e:
        print(f"  Warning: Schema data seeding error: {e}")

    print("  -> Seeding Memory Blueprints & Compositions...")
    try:
        seed_all_scenarios()
    except Exception as e:
        print(f"  Warning: Memory scenario seeding error: {e}")

    print("[5/5] Database population complete!")
    print("=" * 60)


if __name__ == "__main__":
    populate()
