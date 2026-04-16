import sqlite3
import json
import os

db_path = "c:/Users/91797/Documents/Dev/JS/Monorepo/Backend Monorepo/Backend/test.db"

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("SELECT id, name, nodes_list FROM plugin_definitions")
    rows = cursor.fetchall()
    print(f"Found {len(rows)} plugins in DB:")
    for row in rows:
        nodes = json.loads(row[2]) if row[2] else []
        print(f"- {row[0]} ({row[1]}): {len(nodes)} nodes. Content: {nodes}")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
