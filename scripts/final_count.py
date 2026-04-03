from sqlalchemy import create_engine, text
import sys

tables = [
    "agent_definitions",
    "skill_definitions", 
    "workflow_definitions",
    "prompt_definitions",
    "tool_definitions",
    "template_definitions",
    "knowledgebase_entries",
    "memory_definitions"
]

engine = create_engine('postgresql://nexus:nexus_password@localhost:5432/nexus_db')
try:
    with engine.connect() as conn:
        print("\n--- FINAL DB COUNTS ---")
        total = 0
        for table in tables:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table};"))
            count = result.scalar()
            print(f"{table}: {count}")
            total += count
        print(f"\nTOTAL ENTITIES: {total}")
        
        # Check for modular agents explicitly
        result = conn.execute(text("SELECT name FROM agent_definitions ORDER BY name;"))
        print("\n--- AGENTS IN DB ---")
        for row in result:
            print(f"- {row[0]}")
            
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
