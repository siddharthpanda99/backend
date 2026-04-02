"""
Standalone migration — removes legacy 'skill_yaml' and 'fs_artifact' columns from all entity tables.
Run from: Backend Monorepo/Backend/
  cmd /c ".venv\\Scripts\\python.exe migrate_entity_hardening.py"
"""
import sys, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")

import psycopg2

DB = dict(host="localhost", port=5432, dbname="nexus_db", user="nexus", password="nexus_password")

# Try to read from app settings if available
try:
    from app.core.settings import get_settings
    cfg = get_settings()
    DB = dict(host=cfg.POSTGRES_SERVER, port=cfg.POSTGRES_PORT,
              dbname=cfg.POSTGRES_DB, user=cfg.POSTGRES_USER,
              password=cfg.POSTGRES_PASSWORD)
except Exception as e:
    print(f"[warn] Could not load settings ({e}), using defaults")

print(f"Connecting to {DB['dbname']}@{DB['host']}:{DB['port']} ...")
conn = psycopg2.connect(**DB)
conn.autocommit = True
cur = conn.cursor()

MIGRATIONS = [
    # Skill Definition Hardening
    "ALTER TABLE skill_definitions DROP COLUMN IF EXISTS skill_yaml",
    "ALTER TABLE skill_definitions DROP COLUMN IF EXISTS fs_artifact",
    
    # Agent Definition Hardening
    "ALTER TABLE agent_definitions DROP COLUMN IF EXISTS agent_yaml",
    "ALTER TABLE agent_definitions DROP COLUMN IF EXISTS fs_artifact",
    
    # Workflow Definition Hardening
    "ALTER TABLE workflow_definitions DROP COLUMN IF EXISTS fs_artifact",
    
    # Tool Definition Hardening
    "ALTER TABLE tool_definitions DROP COLUMN IF EXISTS fs_artifact",
    
    # Prompt Definition Hardening
    "ALTER TABLE prompt_definitions DROP COLUMN IF EXISTS fs_artifact",
]

print("\n--- Starting Entity Registry Hardening Migration ---")

for sql in MIGRATIONS:
    print(f"Executing: {sql}")
    try:
        cur.execute(sql)
        print("  -> OK")
    except Exception as e:
        print(f"  -> FAILED: {e}")

# Verification
TABLES_TO_CHECK = [
    'skill_definitions', 
    'agent_definitions', 
    'workflow_definitions', 
    'tool_definitions', 
    'prompt_definitions'
]

print("\n--- Verification ---")
for table in TABLES_TO_CHECK:
    cur.execute(f"""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = '{table}'
          AND column_name IN ('skill_yaml', 'agent_yaml', 'fs_artifact')
    """)
    remaining = [r[0] for r in cur.fetchall()]
    if not remaining:
        print(f"Table '{table}': Clean (No redundant columns found)")
    else:
        print(f"Table '{table}': FAILED (Found {remaining})")

cur.close()
conn.close()
print("\n--- Migration Complete ---")
