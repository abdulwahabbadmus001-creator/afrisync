import sqlite3

connection = sqlite3.connect("afrisync.db")
cursor = connection.cursor()

try:
    cursor.execute("""
        ALTER TABLE projects
        ADD COLUMN last_synced_at TEXT
    """)

    print("Column last_synced_at added successfully.")

except sqlite3.OperationalError as error:

    if "duplicate column name" in str(error).lower():
        print("Column already exists: last_synced_at")
    else:
        print(f"Migration error: {error}")

connection.commit()
connection.close()

print("Last synced migration completed.")