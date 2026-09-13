"""
Migrate AfriSync remote server data from SQLite server.db to PostgreSQL.

Example:
    python migrate_server_sqlite_to_postgres.py --sqlite server.db --database-url "postgresql://afrisync_user:password@localhost:5432/afrisync"

You can also set:
    AFRISYNC_SERVER_DB=server.db
    AFRISYNC_DATABASE_URL=postgresql://...
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path
from typing import Iterable

try:
    import psycopg
except ImportError:
    print('Missing dependency: psycopg. Install with: pip install "psycopg[binary]"')
    sys.exit(1)


TABLES = [
    "users",
    "projects",
    "password_reset_tokens",
    "email_verification_codes",
    "project_notes",
    "project_attachments",
    "project_members",
    "admin_sessions",
    "admin_action_logs",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Migrate AfriSync SQLite server.db data to PostgreSQL.")
    parser.add_argument(
        "--sqlite",
        default=os.getenv("AFRISYNC_SERVER_DB", "server.db"),
        help="Path to AfriSync SQLite server.db file.",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("AFRISYNC_DATABASE_URL", ""),
        help="PostgreSQL URL, e.g. postgresql://user:password@localhost:5432/afrisync",
    )
    parser.add_argument(
        "--schema",
        default=str(Path(__file__).with_name("postgres_schema.sql")),
        help="Path to postgres_schema.sql.",
    )
    parser.add_argument(
        "--skip-schema",
        action="store_true",
        help="Do not run postgres_schema.sql before migration.",
    )
    return parser.parse_args()


def table_exists(sqlite_cursor, table_name: str) -> bool:
    sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table_name,))
    return sqlite_cursor.fetchone() is not None


def sqlite_columns(sqlite_cursor, table_name: str) -> list[str]:
    sqlite_cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in sqlite_cursor.fetchall()]


def run_schema(pg_connection, schema_path: Path):
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    sql = schema_path.read_text(encoding="utf-8")
    with pg_connection.cursor() as cursor:
        cursor.execute(sql)
    pg_connection.commit()


def fetch_sqlite_rows(sqlite_cursor, table_name: str, columns: list[str]) -> list[sqlite3.Row]:
    joined = ", ".join(columns)
    sqlite_cursor.execute(f"SELECT {joined} FROM {table_name}")
    return sqlite_cursor.fetchall()


def insert_rows(pg_connection, table_name: str, columns: list[str], rows: Iterable[sqlite3.Row]) -> int:
    rows = list(rows)
    if not rows:
        return 0

    quoted_columns = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))

    # Every AfriSync table has an integer primary key named id. Keeping it makes
    # reruns safe and avoids duplicated log/token records during migration tests.
    conflict_target = "id" if "id" in columns else columns[0]
    updatable_columns = [column for column in columns if column != conflict_target]
    update_clause = ", ".join([f"{column} = EXCLUDED.{column}" for column in updatable_columns])
    if update_clause:
        sql = (
            f"INSERT INTO {table_name} ({quoted_columns}) VALUES ({placeholders}) "
            f"ON CONFLICT ({conflict_target}) DO UPDATE SET {update_clause}"
        )
    else:
        sql = (
            f"INSERT INTO {table_name} ({quoted_columns}) VALUES ({placeholders}) "
            f"ON CONFLICT ({conflict_target}) DO NOTHING"
        )

    with pg_connection.cursor() as cursor:
        for row in rows:
            cursor.execute(sql, tuple(row[column] for column in columns))
    pg_connection.commit()
    return len(rows)


def reset_identity_sequence(pg_connection, table_name: str):
    with pg_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT pg_get_serial_sequence(%s, 'id')
            """,
            (table_name,),
        )
        sequence_row = cursor.fetchone()
        sequence_name = sequence_row[0] if sequence_row else None
        if sequence_name:
            cursor.execute(
                f"SELECT setval(%s, COALESCE((SELECT MAX(id) FROM {table_name}), 1), true)",
                (sequence_name,),
            )
    pg_connection.commit()


def main():
    args = parse_args()
    sqlite_path = Path(args.sqlite)
    if not sqlite_path.exists():
        print(f"SQLite database not found: {sqlite_path}")
        sys.exit(1)
    if not args.database_url:
        print("PostgreSQL database URL is required. Pass --database-url or set AFRISYNC_DATABASE_URL.")
        sys.exit(1)

    print("AfriSync SQLite → PostgreSQL migration")
    print(f"SQLite source: {sqlite_path}")
    print("PostgreSQL target: configured")

    sqlite_connection = sqlite3.connect(sqlite_path)
    sqlite_connection.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_connection.cursor()

    pg_connection = psycopg.connect(args.database_url)

    try:
        if not args.skip_schema:
            print("Creating/updating PostgreSQL schema...")
            run_schema(pg_connection, Path(args.schema))

        migrated_total = 0
        for table_name in TABLES:
            if not table_exists(sqlite_cursor, table_name):
                print(f"- {table_name}: skipped; not found in SQLite")
                continue
            columns = sqlite_columns(sqlite_cursor, table_name)
            rows = fetch_sqlite_rows(sqlite_cursor, table_name, columns)
            count = insert_rows(pg_connection, table_name, columns, rows)
            if "id" in columns:
                reset_identity_sequence(pg_connection, table_name)
            migrated_total += count
            print(f"- {table_name}: migrated {count} row(s)")

        print(f"Migration completed. Total rows migrated: {migrated_total}")
    finally:
        sqlite_connection.close()
        pg_connection.close()


if __name__ == "__main__":
    main()
