import sqlite3
from datetime import datetime

DATABASES = ["afrisync.db", "server.db"]


def now():
    return datetime.now().isoformat()


def column_exists(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return any(row[1] == column_name for row in cursor.fetchall())


def migrate_database(database_name):
    print(f"\nMigrating: {database_name}")
    connection = sqlite3.connect(database_name)
    cursor = connection.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'")
    if not cursor.fetchone():
        print("Projects table does not exist.")
        connection.close()
        return

    additions = [
        ("version", "INTEGER DEFAULT 1"),
        ("updated_at", "TEXT"),
    ]

    # conflict_data is only used locally, but adding it to both DBs is harmless
    # and keeps schema migration simple.
    additions.append(("conflict_data", "TEXT"))

    for column_name, definition in additions:
        if not column_exists(cursor, "projects", column_name):
            cursor.execute(f"ALTER TABLE projects ADD COLUMN {column_name} {definition}")
            print(f"Added column: {column_name}")
        else:
            print(f"Column already exists: {column_name}")

    cursor.execute("UPDATE projects SET version = 1 WHERE version IS NULL OR version < 1")
    timestamp = now()
    cursor.execute("UPDATE projects SET updated_at = ? WHERE updated_at IS NULL", (timestamp,))

    connection.commit()
    connection.close()
    print(f"Migration completed: {database_name}")


def main():
    print("AfriSync Conflict-Versioning Migration")
    for database in DATABASES:
        migrate_database(database)
    print("\nVersioning migration completed.")


if __name__ == "__main__":
    main()
