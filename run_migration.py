"""
Standalone migration — adds the 3 prompt-template columns.
Run from:  Backend Monorepo/Backend/
  cmd /c ".venv\Scripts\python.exe run_migration.py"
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
    "ALTER TABLE agent_definitions ADD COLUMN IF NOT EXISTS prompt_template TEXT",
    "ALTER TABLE agent_definitions ADD COLUMN IF NOT EXISTS resolved_prompt TEXT",
    "ALTER TABLE agent_definitions ADD COLUMN IF NOT EXISTS prompt_resolved_at TIMESTAMPTZ",
]

for sql in MIGRATIONS:
    print(f"  {sql}")
    try:
        cur.execute(sql)
        print("  -> OK")
    except Exception as e:
        print(f"  -> FAILED: {e}")

cur.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'agent_definitions'
      AND column_name IN ('prompt_template', 'resolved_prompt', 'prompt_resolved_at')
    ORDER BY column_name
""")
cols = [r[0] for r in cur.fetchall()]
print(f"\nVerified columns: {cols}")
if len(cols) == 3:
    print("SUCCESS — all 3 columns present in DB.")
else:
    print(f"PARTIAL — only {len(cols)}/3 found: {cols}")
    sys.exit(1)

cur.close()
conn.close()
