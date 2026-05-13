import os
import sys
from pathlib import Path
from sqlalchemy import text

# Add project roots to path
repo_root = Path(r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo")
sys.path.append(str(repo_root / "Backend"))
sys.path.append(str(repo_root / "Python Libs" / "common_lib" / "src"))

from common_lib.modules.data_storage.database.connection import engine

def list_columns():
    try:
        with engine.connect() as conn:
            res = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='ai_models';
            """))
            columns = [r[0] for r in res.fetchall()]
            print(f"Columns in ai_models: {columns}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_columns()
