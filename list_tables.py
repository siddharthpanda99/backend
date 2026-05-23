import psycopg2
conn = psycopg2.connect("postgresql://nexus:nexus_password@localhost:5432/nexus_db")
cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
for row in cur.fetchall():
    print(row[0])
