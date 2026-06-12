import os
import sys
from sqlalchemy import create_engine, text

def main():
    db_url = os.environ.get("DATABASE_URL", "postgresql://nexus:nexus_password@localhost:5432/nexus_db")
    print(f"Connecting to database...")
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # 1. Query knowledge_source_types
            print("\n--- knowledge_source_types ---")
            types = conn.execute(text("SELECT id, name, category FROM knowledge_source_types")).fetchall()
            for t in types:
                print(t)
                
            # 2. Query knowledge_source_configs
            print("\n--- knowledge_source_configs ---")
            configs = conn.execute(text("SELECT id, name, source_type_id, status FROM knowledge_source_configs")).fetchall()
            for c in configs:
                print(c)
                
            # 3. Query dip_ingestion_sources
            print("\n--- dip_ingestion_sources ---")
            dip = conn.execute(text("SELECT id, name, type, status FROM dip_ingestion_sources")).fetchall()
            for d in dip:
                print(d)
                
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()
