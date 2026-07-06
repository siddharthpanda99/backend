import os
import sys
from pydantic import BaseModel

# Ensure common_lib is in path
sys.path.append(os.path.abspath("../Python Libs/common_lib/src"))

from common_lib.modules.ferment.scoping import ScopingLoop
from common_lib.modules.ferment.state import ContinuationPolicy
from common_lib.modules.db_provisioning.service import db_provisioner
from common_lib.templates.tools.data.database.operations import query, list_tables
import logging

logging.basicConfig(level=logging.INFO)

class DummyProject:
    def __init__(self, name):
        self.name = name
        self.scoping = {}
        self.goal = ""
        self.files = []
        self.steps = []

def run_test():
    print("=== E2E ETL Workflow Test (MySQL) ===")
    project = DummyProject("Create MySQL ETL")
    
    print("Provisioning MySQL Database...")
    try:
        db_url = db_provisioner.provision_db(project.name, "mysql")
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
        id INT AUTO_INCREMENT PRIMARY KEY,
        email VARCHAR(255) UNIQUE NOT NULL,
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
    INSERT IGNORE INTO users (email) VALUES 
    ('test1@example.com'), 
    ('test2@example.com');
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
