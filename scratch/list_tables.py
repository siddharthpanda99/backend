import sqlite3
import os

db_path = r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Backend\test.db"

def list_tables():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables in database:")
    for table in tables:
        print(f"- {table[0]}")
    conn.close()

if __name__ == "__main__":
    list_tables()
