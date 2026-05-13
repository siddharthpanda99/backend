import os
import sys
from pathlib import Path
from sqlalchemy import text

# Add project roots to path
repo_root = Path(r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo")
sys.path.append(str(repo_root / "Backend"))
sys.path.append(str(repo_root / "Python Libs" / "common_lib" / "src"))

from common_lib.modules.data_storage.database.connection import engine

def check_column():
    try:
        with engine.connect() as conn:
            res = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='ai_models' AND column_name='metadata';
            """))
            exists = res.fetchone()
            print(f"Metadata column exists: {exists is not None}")
    except Exception as e:
        print(f"Error checking column: {e}")

if __name__ == "__main__":
    check_column()
