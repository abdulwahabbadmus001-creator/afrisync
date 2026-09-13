import sqlite3
from pathlib import Path

DATABASES = [
    ("Server", "server.db"),
    ("Device A", "afrisync_device_a.db"),
    ("Device B", "afrisync_device_b.db"),
    ("Default Local", "afrisync.db"),
]

TABLES = [
    "users",
    "projects",
    "project_notes",
    "project_attachments",
    "activity_logs",
    "sync_history",
    "remote_sync_tokens",
    "local_users",
    "local_sessions",
]


def table_exists(cursor, table_name):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def count_rows(cursor, table_name):
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    return int(cursor.fetchone()[0] or 0)


def count_pending(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = {row[1] for row in cursor.fetchall()}
    if "sync_status" not in columns:
        return None
    cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE sync_status = 'PENDING'")
    return int(cursor.fetchone()[0] or 0)


def main():
    print("\nAFRISYNC MULTI-DEVICE STATUS")
    print("=" * 36)

    for label, db_path in DATABASES:
        path = Path(db_path)
        print(f"\n{label}: {db_path}")
        print("-" * (len(label) + len(db_path) + 2))

        if not path.exists():
            print("Database not found yet.")
            continue

        connection = sqlite3.connect(path)
        cursor = connection.cursor()

        for table in TABLES:
            if not table_exists(cursor, table):
                continue
            total = count_rows(cursor, table)
            pending = count_pending(cursor, table)
            if pending is None:
                print(f"{table}: {total}")
            else:
                print(f"{table}: {total} total, {pending} pending")

        connection.close()

    print("\nDone. Use this after creating/syncing data on Device A and Device B.")


if __name__ == "__main__":
    main()
