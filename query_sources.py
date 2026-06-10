import os
import sys
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../Python Libs/common_lib/src")))

def query_sqlite():
    print("Checking SQLite (test.db)...")
    try:
        sqlite_db = "test.db"
        if not os.path.exists(sqlite_db):
            print("SQLite test.db not found here.")
            return
        engine = create_engine(f"sqlite:///{sqlite_db}")
        with engine.connect() as conn:
            # Let's see what tables exist
            tables = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
            print("SQLite Tables:", [t[0] for t in tables])
            
            # Check if dip_ingestion_sources exists in any variation
            for t in tables:
                tname = t[0]
                if "ingest" in tname.lower() or "source" in tname.lower():
                    rows = conn.execute(text(f"SELECT * FROM {tname}")).fetchall()
                    print(f"Table {tname} rows:", rows)
    except Exception as e:
        print("SQLite error:", e)

def query_postgres():
    print("\nChecking PostgreSQL...")
    db_url = os.environ.get("DATABASE_URL", "postgresql://nexus:nexus_password@localhost:5432/nexus_db")
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # Get public tables
            tables = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")).fetchall()
            print("Postgres Tables:", [t[0] for t in tables])
            
            for t in tables:
                tname = t[0]
                if "ingest" in tname.lower() or "source" in tname.lower():
                    rows = conn.execute(text(f"SELECT id, name, type, status, enabled, platform FROM {tname}")).fetchall()
                    print(f"Table {tname} rows:")
                    for r in rows:
                        print(r)
    except Exception as e:
        print("Postgres error:", e)

if __name__ == "__main__":
    query_sqlite()
    query_postgres()
