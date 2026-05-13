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
            print("Attempting to add 'metadata' column...")
            # Use a simpler ALTER TABLE
            conn.execute(text("ALTER TABLE ai_models ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';"))
            conn.commit()
            print("Done.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    hotfix()
