from sqlalchemy import create_engine, text
import sys

engine = create_engine('postgresql://agent_user:agent_password@localhost:5433/agentic_data')
try:
    with engine.connect() as conn:
        # 1. Count by Type
        result = conn.execute(text("SELECT type, COUNT(*) FROM orchestration_entities GROUP BY type ORDER BY type;"))
        print("\n--- DB COUNTS BY TYPE ---")
        for row in result:
            print(f"{row[0]}: {row[1]}")
        
        # 2. List Agents (Sample)
        result = conn.execute(text("SELECT id FROM orchestration_entities WHERE type = 'agent' ORDER BY id;"))
        agents = [row[0] for row in result]
        print(f"\n--- REGISTERED AGENTS ({len(agents)}) ---")
        for agent in agents[:25]: # Show first 25
            print(f" - {agent}")
        if len(agents) > 25:
            print(f" ... and {len(agents)-25} more")

except Exception as e:
    print(f"Error connecting to DB: {e}")
    sys.exit(1)
