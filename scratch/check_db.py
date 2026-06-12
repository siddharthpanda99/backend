import os
from sqlalchemy import create_engine, text

def main():
    db_file = "test.db"
    if not os.path.exists(db_file):
        print("test.db does not exist")
        return
    engine = create_engine(f"sqlite:///{db_file}")
    with engine.connect() as conn:
        tables = [row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()]
        print("Tables in SQLite:", tables)
        for table in ["knowledge_source_configs", "dip_ingestion_sources"]:
            if table in tables:
                rows = conn.execute(text(f"SELECT * FROM {table}")).fetchall()
                print(f"Rows in {table}:", rows)
            else:
                print(f"Table {table} does not exist in SQLite")

if __name__ == "__main__":
    main()
