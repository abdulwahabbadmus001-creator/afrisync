import sqlite3

connection = sqlite3.connect("server.db")
cursor = connection.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    location TEXT,
    progress INTEGER DEFAULT 0,
    sync_status TEXT DEFAULT 'SYNCED'
)
""")

connection.commit()
connection.close()

print("Server database created successfully.")