import sqlite3
import os

db_path = r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Backend\test.db"

def hotfix_db():
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Checking if 'parameters' column exists in 'ai_models' table...")
        cursor.execute("PRAGMA table_info(ai_models)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "parameters" not in columns:
            print("Adding 'parameters' column to 'ai_models' table...")
            cursor.execute("ALTER TABLE ai_models ADD COLUMN parameters VARCHAR(50)")
            conn.commit()
            print("Column added successfully.")
        else:
            print("'parameters' column already exists.")
            
    except Exception as e:
        print(f"Error during hotfix: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    hotfix_db()
