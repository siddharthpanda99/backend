import asyncio
import os
import sys

# Ensure common_lib is in path
sys.path.append(os.path.abspath("../Python Libs/common_lib/src"))

from common_lib.modules.ferment.scoping import ScopingLoop
from common_lib.modules.ferment.state import ContinuationPolicy
from common_lib.modules.db_provisioning.service import db_provisioner
from common_lib.templates.tools.data.database.operations import query, list_tables

async def run_test():
    print("=== E2E ETL Workflow Test ===")
    
    # 1. Scope project
    goal = "Create a user analytics ETL pipeline"
    print(f"Goal: {goal}")
    print("Scoping project...")
    loop = ScopingLoop(goal=goal, auto_approve=True, continuation=ContinuationPolicy.AUTOMATED)
    project = await loop.run()
    print(f"Project created: {project.name}")

    # 2. Provision DB
    print("Provisioning Postgres Database...")
    try:
        db_url = db_provisioner.provision_db(project.name, "postgres")
        print(f"Database URL: {db_url}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Failed to provision database: {e}")
        return
    
    # 3. Simulate Agent executing SQL schema (ETL phase 1)
    print("\nApplying schema...")
    create_schema = "CREATE TABLE IF NOT EXISTS test_users (id SERIAL PRIMARY KEY, name VARCHAR(50), role VARCHAR(20));"
    res1 = query(db_url, create_schema)
    print("Schema applied result:", res1)
    
    # 4. Check tables
    tables = list_tables(db_url)
    print("Current tables:", tables)
    
    # 5. Simulate Agent seeding data (ETL phase 2)
    print("\nSeeding data...")
    seed_sql = "INSERT INTO test_users (name, role) VALUES ('Alice', 'Admin'), ('Bob', 'User') RETURNING id;"
    res2 = query(db_url, seed_sql)
    print("Seed result:", res2)
    
    # 6. Simulate Agent running analytics query (ETL phase 3)
    print("\nRunning analytics query...")
    analytics_sql = "SELECT role, COUNT(*) as count FROM test_users GROUP BY role;"
    res3 = query(db_url, analytics_sql)
    print("Analytics result:", res3)
    
    print("=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(run_test())
