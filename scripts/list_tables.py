from sqlalchemy import create_engine, text
import sys

engine = create_engine('postgresql://agent_user:agent_password@localhost:5433/agentic_data')
try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public' ORDER BY tablename;"))
        print("\n--- DB TABLES ---")
        for row in result:
            print(f"- {row[0]}")
            
except Exception as e:
    print(f"Error connecting to DB: {e}")
    sys.exit(1)
