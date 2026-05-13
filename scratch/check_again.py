import os
import sys
from pathlib import Path
from sqlalchemy import text

# Add project roots to path
repo_root = Path(r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo")
sys.path.append(str(repo_root / "Backend"))
sys.path.append(str(repo_root / "Python Libs" / "common_lib" / "src"))

from common_lib.modules.data_storage.database.connection import engine

def hotfix():
    try:
        with engine.connect() as conn:
            print("Setting lock timeout...")
            conn.execute(text("SET lock_timeout = '2s';"))
            print("Attempting to add 'metadata_json' column...")
            # We already know it exists in the DB according to list_columns.py!!
            # WAIT! Let me re-read the list_columns.py output.
            # Columns in ai_models: ['id', 'name', ..., 'metadata_json', ..., 'parameters']
            # IT IS ALREADY THERE!
            print("Column 'metadata_json' IS ALREADY IN THE DB.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    hotfix()
