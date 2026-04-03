import psycopg2
from psycopg2 import sql

def fix_schema():
    conn = None
    try:
        # Connect to your postgres database
        conn = psycopg2.connect(
            host="localhost",
            database="nexus_db",
            user="nexus",
            password="nexus_password",
            port=5432
        )
        cur = conn.cursor()

        # List of columns to check and add if missing
        columns_to_add = [
            ("dtype", "VARCHAR(255)"),
            ("kv_cache_dtype", "VARCHAR(255)"),
            ("gpu_memory_utilization", "DOUBLE PRECISION"),
            ("max_model_len", "INTEGER"),
            ("trust_remote_code", "BOOLEAN DEFAULT FALSE")
        ]

        for col_name, col_type in columns_to_add:
            print(f"Checking column: {col_name}...")
            cur.execute(sql.SQL("""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name='model_requirements' AND column_name=%s) THEN
                        ALTER TABLE model_requirements ADD COLUMN {} {};
                    END IF;
                END
                $$;
            """).format(sql.Identifier(col_name), sql.SQL(col_type)), [col_name])
            print(f"  Processed {col_name}")

        conn.commit()
        print("Schema update completed successfully.")
        cur.close()
    except Exception as e:
        print(f"Error updating schema: {e}")
    finally:
        if conn is not None:
            conn.close()

if __name__ == "__main__":
    fix_schema()
