import sqlite3


DATABASES = [
    "afrisync.db",
    "server.db",
]


def column_exists(cursor, table_name, column_name):
    cursor.execute(
        f"PRAGMA table_info({table_name})"
    )

    columns = cursor.fetchall()

    return any(
        column[1] == column_name
        for column in columns
    )


def migrate_database(database_name):
    print()
    print(f"Migrating: {database_name}")

    connection = sqlite3.connect(
        database_name
    )

    cursor = connection.cursor()

    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'projects'
    """)

    projects_table = cursor.fetchone()

    if not projects_table:
        print(
            "Projects table does not exist."
        )

        connection.close()
        return

    if not column_exists(
        cursor,
        "projects",
        "is_deleted"
    ):
        cursor.execute("""
            ALTER TABLE projects
            ADD COLUMN is_deleted INTEGER DEFAULT 0
        """)

        print(
            "Added column: is_deleted"
        )

    else:
        print(
            "Column already exists: is_deleted"
        )

    if not column_exists(
        cursor,
        "projects",
        "deleted_at"
    ):
        cursor.execute("""
            ALTER TABLE projects
            ADD COLUMN deleted_at TEXT
        """)

        print(
            "Added column: deleted_at"
        )

    else:
        print(
            "Column already exists: deleted_at"
        )

    cursor.execute("""
        UPDATE projects
        SET is_deleted = 0
        WHERE is_deleted IS NULL
    """)

    connection.commit()
    connection.close()

    print(
        f"Migration completed: {database_name}"
    )


def main():
    print(
        "AfriSync Tombstone Migration"
    )

    for database in DATABASES:
        migrate_database(
            database
        )

    print()
    print(
        "Tombstone migration completed."
    )


if __name__ == "__main__":
    main()