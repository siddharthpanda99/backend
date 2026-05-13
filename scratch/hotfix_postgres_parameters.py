import os
import sys
from pathlib import Path
from sqlalchemy import text

# Add project roots to path
repo_root = Path(r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo")
sys.path.append(str(repo_root / "Backend"))
sys.path.append(str(repo_root / "Python Libs" / "common_lib" / "src"))

from common_lib.modules.data_storage.database.connection import engine

def hotfix_postgres():
    try:
        with engine.connect() as conn:
            print("Checking for 'parameters' column in 'ai_models' table...")
            # Check if column exists (Postgres specific)
            res = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='ai_models' AND column_name='parameters';
            """))
            exists = res.fetchone()
            
            if not exists:
                print("Adding 'parameters' column to 'ai_models' table...")
                conn.execute(text("ALTER TABLE ai_models ADD COLUMN parameters VARCHAR(50);"))
                conn.commit()
                print("Column added successfully.")
            else:
                print("'parameters' column already exists.")
                
    except Exception as e:
        print(f"Error during hotfix: {e}")

if __name__ == "__main__":
    hotfix_postgres()
