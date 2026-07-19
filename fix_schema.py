import os
from sqlmodel import create_engine, text
from sqlalchemy import inspect

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///test.db")
engine = create_engine(DATABASE_URL)
inspector = inspect(engine)

existing = set(inspector.get_table_names())

tables = {
    "uds_connections": """
        CREATE TABLE IF NOT EXISTS uds_connections (
            id VARCHAR(64) PRIMARY KEY,
            name VARCHAR(256) NOT NULL,
            db_type VARCHAR(32) NOT NULL,
            host VARCHAR(256) DEFAULT 'localhost',
            port INTEGER,
            database VARCHAR(256) DEFAULT '',
            username VARCHAR(128) DEFAULT '',
            encrypted_password TEXT,
            ssl BOOLEAN DEFAULT 0,
            ssh_enabled BOOLEAN DEFAULT 0,
            ssh_host VARCHAR(256),
            ssh_port INTEGER,
            ssh_username VARCHAR(128),
            ssh_password TEXT,
            ssh_auth_type VARCHAR(32),
            extra_params JSON DEFAULT '{}',
            status VARCHAR(32) DEFAULT 'disconnected',
            last_tested TIMESTAMP,
            environment VARCHAR(32) DEFAULT 'development',
            workspace_id VARCHAR(64),
            config_profile_id VARCHAR(128),
            folder_id VARCHAR(64),
            is_favorite BOOLEAN DEFAULT 0,
            is_archived BOOLEAN DEFAULT 0,
            metadata_json JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "uds_workspaces": """
        CREATE TABLE IF NOT EXISTS uds_workspaces (
            id VARCHAR(64) PRIMARY KEY,
            name VARCHAR(256) NOT NULL,
            description TEXT,
            color VARCHAR(16) DEFAULT '#6b7280',
            environment VARCHAR(32) DEFAULT 'development',
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "uds_folders": """
        CREATE TABLE IF NOT EXISTS uds_folders (
            id VARCHAR(64) PRIMARY KEY,
            name VARCHAR(256) NOT NULL,
            workspace_id VARCHAR(64) NOT NULL,
            parent_folder_id VARCHAR(64),
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "uds_tags": """
        CREATE TABLE IF NOT EXISTS uds_tags (
            id VARCHAR(64) PRIMARY KEY,
            name VARCHAR(64) UNIQUE NOT NULL,
            color VARCHAR(16) DEFAULT '#6b7280'
        )
    """,
    "connection_tags": """
        CREATE TABLE IF NOT EXISTS connection_tags (
            connection_id VARCHAR(64) NOT NULL,
            tag_id VARCHAR(64) NOT NULL,
            PRIMARY KEY (connection_id, tag_id)
        )
    """,
}

for name, ddl in tables.items():
    if name not in existing:
        with engine.begin() as conn:
            conn.execute(text(ddl))
        print(f"Created {name}")
    else:
        cols = [c["name"] for c in inspector.get_columns(name)]
        if "config_profile_id" not in cols and name == "uds_connections":
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE uds_connections ADD COLUMN config_profile_id VARCHAR(128)"
                    )
                )
            print("Added config_profile_id to uds_connections")
        print(f"{name} OK ({len(cols)} cols)")

inspector = inspect(engine)
cols = [c["name"] for c in inspector.get_columns("uds_connections")]
print(f"\nFinal uds_connections columns: {cols}")
print(f"config_profile_id present: {'config_profile_id' in cols}")
