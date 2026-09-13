"""Check AfriSync PostgreSQL tables and row counts."""

from __future__ import annotations

import os
import sys

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


def main():
    database_url = os.getenv("AFRISYNC_DATABASE_URL", "").strip()
    if not database_url:
        print("AFRISYNC_DATABASE_URL is not set.")
        sys.exit(1)
    connection = psycopg.connect(database_url)
    try:
        with connection.cursor() as cursor:
            print("AfriSync PostgreSQL status")
            for table in TABLES:
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = %s
                    )
                    """,
                    (table,),
                )
                exists = cursor.fetchone()[0]
                if not exists:
                    print(f"- {table}: missing")
                    continue
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"- {table}: {count} row(s)")
        print("PostgreSQL check completed.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
