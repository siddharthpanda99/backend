import os
import sys

# Try common_lib to setup
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../Python Libs/common_lib/src")))

try:
    from sqlalchemy import create_engine, text
    import json
    
    db_url = os.environ.get("DATABASE_URL", "postgresql://nexus:nexus_password@localhost:5432/nexus_db")
    print(f"Connecting to {db_url}")
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, name FROM ai_models WHERE id LIKE '%audio%' OR id LIKE '%cosy%' OR id LIKE '%fish%' OR id LIKE '%index%'"))
        rows = result.fetchall()
        print("\n--- Audio Models in Postgres DB (ai_models table) ---")
        for r in rows:
            print(r)
except Exception as e:
    print(f"Error querying DB directly: {e}")
