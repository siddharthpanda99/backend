import os
import sys
from pathlib import Path

# Setup paths
REPO_ROOT = Path(__file__).parent.parent.parent.resolve()
BACKEND_DIR = REPO_ROOT / "Backend Monorepo" / "Backend"
sys.path.insert(0, str(BACKEND_DIR))
COMMON_LIB_SRC = REPO_ROOT / "Backend Monorepo" / "Python Libs" / "common_lib" / "src"
sys.path.insert(0, str(COMMON_LIB_SRC))

from common_lib.modules.data_storage.database.connection import get_db_settings, get_engine, get_session
from sqlmodel import select, text
from common_lib.modules.knowledge_hub.models import SourceConfigRecord

def main():
    settings = get_db_settings()
    print("Database URI:", settings.SQLALCHEMY_DATABASE_URI)
    
    # Try querying via SQLModel
    engine = get_engine()
    print("Engine URL:", engine.url)
    
    with next(get_session()) as session:
        configs = session.exec(select(SourceConfigRecord)).all()
        print(f"SQLModel session returned {len(configs)} configs:")
        for c in configs:
            print(f" - {c.id}: {c.name}")

if __name__ == "__main__":
    main()
