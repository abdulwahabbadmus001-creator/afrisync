import sqlite3


connection = sqlite3.connect("afrisync.db")
cursor = connection.cursor()


columns = [
    ("sync_attempts", "INTEGER DEFAULT 0"),
    ("last_sync_attempt", "TEXT"),
    ("last_sync_error", "TEXT")
]


for column_name, column_type in columns:

    try:

        cursor.execute(
            f"""
            ALTER TABLE projects
            ADD COLUMN {column_name} {column_type}
            """
        )

        print(f"Added column: {column_name}")

    except sqlite3.OperationalError:

        print(f"Column already exists: {column_name}")


connection.commit()
connection.close()

print("Sync queue migration completed.")