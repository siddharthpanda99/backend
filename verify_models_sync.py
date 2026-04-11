import os
import sys
from pathlib import Path

# Override to SQLite for local verification
os.environ["DATABASE_URL"] = "sqlite:///test.db"

# Bootstrap sys.path
backend_dir = Path(__file__).parent.resolve()
common_lib_src = str(backend_dir.parent / "Python Libs" / "common_lib" / "src")
if common_lib_src not in sys.path:
    sys.path.insert(0, common_lib_src)

from app.core.common_lib_integration import sync_manager, common_memory
from sqlalchemy import text

def verify():
    # Force SQLite for local verification if Postgres is down
    db_url = "sqlite:///test.db"
    print(f"Connecting to DB: {db_url}")
    
    # Re-initialize common_memory if needed, but for the script we'll just use the engine directly
    from sqlalchemy import create_engine
    engine = create_engine(db_url)
    
    print("Triggering sync...")
    try:
        report = sync_manager.sync_all_from_files()
        print(f"Sync complete. Processed {report.entities_processed} entities.")
    except Exception as e:
        print(f"Sync failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    with common_memory.engine.connect() as conn:
        try:
            count = conn.execute(text('SELECT count(*) FROM model_definitions')).scalar()
            print(f"Model definitions in DB: {count}")
            
            if count > 0:
                models = conn.execute(text('SELECT id, name, minio_uri FROM model_definitions')).fetchall()
                for m in models:
                    print(f" - [{m[0]}] {m[1]} -> (MinIO: {m[2]})")
            else:
                print("!!! No models found in database.")
        except Exception as e:
            print(f"Database query failed: {e}")

if __name__ == "__main__":
    verify()
