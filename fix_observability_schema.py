import sys
import os
from sqlalchemy import text

# Add common_lib to path if needed (if not in venv)
# But since we are running with .venv\Scripts\python.exe, it should be fine.

from common_lib.modules.data_storage.database.connection import engine

def fix_schema():
    print("Connecting to database...")
    with engine.connect() as conn:
        print("Checking for missing column 'state_snapshot' in 'observability.workflow_executions'...")
        try:
            # Check if column exists
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'observability' 
                  AND table_name = 'workflow_executions' 
                  AND column_name = 'state_snapshot'
            """))
            if not result.fetchone():
                print("Adding missing column 'state_snapshot'...")
                # Note: SQLModel JSON type maps to JSONB in Postgres
                conn.execute(text("ALTER TABLE observability.workflow_executions ADD COLUMN state_snapshot JSONB DEFAULT '{}'"))
                conn.commit()
                print("Column 'state_snapshot' added successfully.")
            else:
                print("Column 'state_snapshot' already exists.")
        except Exception as e:
            print(f"Error adding column to workflow_executions: {e}")

        print("Checking workflow_events table columns...")
        # Check node_config and node_output (added recently for observability)
        try:
            for col in ['node_config', 'node_output']:
                result = conn.execute(text(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'observability' 
                      AND table_name = 'workflow_events' 
                      AND column_name = '{col}'
                """))
                if not result.fetchone():
                    print(f"Adding missing column '{col}' to workflow_events...")
                    conn.execute(text(f"ALTER TABLE observability.workflow_events ADD COLUMN {col} JSONB"))
                    conn.commit()
                    print(f"Column '{col}' added successfully.")
        except Exception as e:
            print(f"Error checking workflow_events: {e}")

if __name__ == "__main__":
    fix_schema()
