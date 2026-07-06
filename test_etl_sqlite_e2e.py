import os
import sys

# Ensure common_lib is in path
sys.path.append(os.path.abspath("../Python Libs/common_lib/src"))

from common_lib.modules.db_provisioning.service import db_provisioner
from common_lib.templates.tools.data.database.operations import query, list_tables
import logging

logging.basicConfig(level=logging.INFO)

class DummyProject:
    def __init__(self, name):
        self.name = name

def run_test():
    print("=== E2E ETL Workflow Test (SQLite) ===")
    project = DummyProject("Create SQLite ETL")
    
    print("Provisioning SQLite Database...")
    try:
        db_url = db_provisioner.provision_db(project.name, "sqlite")
        print(f"Database URL: {db_url}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Failed to provision database: {e}")
        return
    
    # Apply Schema
    print("\nApplying schema...")
    schema_sql = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    res = query(db_url, schema_sql)
    print(f"Schema applied result: {res}")
    
    tables = list_tables(db_url)
    print(f"Current tables: {tables}")
    
    # Seed data
    print("\nSeeding data...")
    seed_sql = """
    INSERT OR IGNORE INTO users (email) VALUES 
    ('sqlite1@example.com'), 
    ('sqlite2@example.com');
    """
    res = query(db_url, seed_sql)
    print(f"Seed result: {res}")
    
    # Analytics
    print("\nRunning analytics query...")
    analytics_sql = """
    SELECT COUNT(*) as user_count FROM users;
    """
    res = query(db_url, analytics_sql)
    print(f"Analytics result: {res}")
    print("=== Test Complete ===")

if __name__ == "__main__":
    run_test()
