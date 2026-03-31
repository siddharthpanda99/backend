"""
migrate_prompt_columns.py
Run once to add the three prompt-templating columns to agent_definitions.

Usage (from Backend Monorepo/Backend/):
    .venv\Scripts\python.exe migrate_prompt_columns.py
"""
import sys, os

# Pull settings via get_settings()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "Lib", "site-packages"))

from app.core.settings import get_settings
cfg = get_settings()

import psycopg2

print(f"Connecting to {cfg.POSTGRES_DB}@{cfg.POSTGRES_SERVER}:{cfg.POSTGRES_PORT} as {cfg.POSTGRES_USER}...")

conn = psycopg2.connect(
    host=cfg.POSTGRES_SERVER,
    port=cfg.POSTGRES_PORT,
    dbname=cfg.POSTGRES_DB,
    user=cfg.POSTGRES_USER,
    password=cfg.POSTGRES_PASSWORD,
)
conn.autocommit = True
cur = conn.cursor()

MIGRATIONS = [
    "ALTER TABLE agent_definitions ADD COLUMN IF NOT EXISTS prompt_template TEXT",
    "ALTER TABLE agent_definitions ADD COLUMN IF NOT EXISTS resolved_prompt TEXT",
    "ALTER TABLE agent_definitions ADD COLUMN IF NOT EXISTS prompt_resolved_at TIMESTAMPTZ",
]

for sql in MIGRATIONS:
    print(f"  Running: {sql}")
    cur.execute(sql)
    print("  OK")

# Verify
cur.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'agent_definitions'
      AND column_name IN ('prompt_template', 'resolved_prompt', 'prompt_resolved_at')
    ORDER BY column_name
""")
cols = [r[0] for r in cur.fetchall()]
print(f"\nVerified columns in DB: {cols}")
if len(cols) == 3:
    print("Migration complete - all 3 columns present.")
else:
    print(f"Only found {len(cols)}/3 expected columns!")
    sys.exit(1)

cur.close()
conn.close()
