import os
import sys
from pymongo import MongoClient

# Ensure common_lib is in path
sys.path.append(os.path.abspath("../Python Libs/common_lib/src"))

from common_lib.modules.db_provisioning.service import db_provisioner
import logging

logging.basicConfig(level=logging.INFO)

class DummyProject:
    def __init__(self, name):
        self.name = name

def run_test():
    print("=== E2E ETL Workflow Test (MongoDB) ===")
    project = DummyProject("Create MongoDB ETL")
    
    print("Provisioning MongoDB Database...")
    try:
        db_url = db_provisioner.provision_db(project.name, "mongo")
        print(f"Database URL: {db_url}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Failed to provision database: {e}")
        return
    
    print("\nConnecting to MongoDB...")
    import time
    time.sleep(15)  # Give mongo a second to be ready
    
    client = MongoClient(db_url)
    db = client.get_default_database()
    
    # Apply Schema/Seed data
    print("Seeding data...")
    collection = db["users"]
    res = collection.insert_many([
        {"email": "mongo1@example.com", "role": "admin"},
        {"email": "mongo2@example.com", "role": "user"}
    ])
    print(f"Seed result: Inserted {len(res.inserted_ids)} records")
    
    # Analytics
    print("\nRunning analytics query...")
    count = collection.count_documents({"role": "admin"})
    print(f"Analytics result: Found {count} admin users")
    print("=== Test Complete ===")

if __name__ == "__main__":
    run_test()
