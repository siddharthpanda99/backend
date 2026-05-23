import sqlite3
import glob
import os

for db_path in glob.glob("*.db"):
    print(f"\n--- Checking {db_path} ---")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor.fetchall()]
        print(f"Tables: {tables}")
        
        for table in tables:
            if 'model' in table.lower() or 'entit' in table.lower() or 'registry' in table.lower():
                print(f"Found potential table: {table}")
                cursor.execute(f"SELECT * FROM {table} WHERE id LIKE '%audio%' OR id LIKE '%cosy%' OR id LIKE '%fish%' OR id LIKE '%index%' LIMIT 10;")
                rows = cursor.fetchall()
                if rows:
                    print(f"Match found in {table}:")
                    for row in rows:
                        print(row)
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
