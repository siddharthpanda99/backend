import os
import sys
import json
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql+psycopg2://nexus:nexus_password@localhost:5432/nexus_db"
engine = create_engine(DATABASE_URL)

def verify_senior_dev():
    query = text("SELECT definition FROM agent_definitions WHERE id = 'senior_dev'")
    with engine.connect() as conn:
        result = conn.execute(query).fetchone()
        if result:
            definition = result[0]
            print(f"VERIFICATION: senior_dev found.")
            print(f"Planning Config: {json.dumps(definition.get('planning_config'), indent=2)}")
            print(f"Memory Config: {json.dumps(definition.get('memory_config'), indent=2)}")
            print(f"Prompt IDs: {definition.get('prompt_ids')}")
        else:
            print("VERIFICATION FAILED: senior_dev not found in DB.")

if __name__ == "__main__":
    verify_senior_dev()
