import os
import sys
import redis

# Ensure common_lib is in path
sys.path.append(os.path.abspath("../Python Libs/common_lib/src"))

from common_lib.modules.db_provisioning.service import db_provisioner
import logging

logging.basicConfig(level=logging.INFO)

class DummyProject:
    def __init__(self, name):
        self.name = name

def run_test():
    print("=== E2E ETL Workflow Test (Redis) ===")
    project = DummyProject("Create Redis ETL")
    
    print("Provisioning Redis Database...")
    try:
        db_url = db_provisioner.provision_db(project.name, "redis")
        print(f"Database URL: {db_url}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Failed to provision database: {e}")
        return
    
    print("\nConnecting to Redis...")
    import time
    time.sleep(2)
    
    r = redis.Redis.from_url(db_url)
    
    # Apply Schema/Seed data
    print("Seeding data...")
    r.set('user:1:email', 'redis1@example.com')
    r.set('user:2:email', 'redis2@example.com')
    print("Seed result: Added 2 users")
    
    # Analytics
    print("\nRunning analytics query...")
    keys = r.keys('user:*:email')
    print(f"Analytics result: Found {len(keys)} users")
    print("=== Test Complete ===")

if __name__ == "__main__":
    run_test()
