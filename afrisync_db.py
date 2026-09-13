"""
AfriSync database backend adapter.

Default behavior remains SQLite, so the existing local development setup keeps working.
Set AFRISYNC_DATABASE_BACKEND=postgres and AFRISYNC_DATABASE_URL to run the remote
server/admin dashboard on PostgreSQL.

Required PostgreSQL package:
    pip install "psycopg[binary]"
"""

from __future__ import annotations

import os
import re
import sqlite3
from typing import Any, Iterable, Optional


SQLITE_BACKEND_NAMES = {"", "sqlite", "sqlite3", "local"}
POSTGRES_BACKEND_NAMES = {"postgres", "postgresql", "pg"}


def get_database_backend() -> str:
    raw = os.getenv("AFRISYNC_DATABASE_BACKEND", "sqlite").strip().lower()
    if raw in SQLITE_BACKEND_NAMES:
        return "sqlite"
    if raw in POSTGRES_BACKEND_NAMES:
        return "postgres"
    raise RuntimeError(
        "Invalid AFRISYNC_DATABASE_BACKEND. Use 'sqlite' or 'postgres'."
    )


def get_database_url() -> str:
    return os.getenv("AFRISYNC_DATABASE_URL", "").strip()


def is_postgres_enabled() -> bool:
    return get_database_backend() == "postgres"


class SQLiteStyleRow:
    """Small row object that behaves like sqlite3.Row for AfriSync code."""

    def __init__(self, columns: list[str], values: Iterable[Any]):
        self._columns = list(columns)
        self._values = list(values)
        self._index = {name: idx for idx, name in enumerate(self._columns)}

    def __getitem__(self, key: int | str) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return self._values[self._index[key]]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def keys(self):
        return list(self._columns)

    def items(self):
        return [(key, self[key]) for key in self._columns]

    def get(self, key: str, default: Any = None) -> Any:
        return self[key] if key in self._index else default


class PostgresCursorAdapter:
    def __init__(self, cursor):
        self._cursor = cursor
        self._last_columns: list[str] = []

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def execute(self, sql: str, params: Optional[Iterable[Any]] = None):
        translated = translate_sqlite_sql_to_postgres(sql)
        self._cursor.execute(translated, tuple(params or ()))
        self._last_columns = [desc.name for desc in self._cursor.description] if self._cursor.description else []
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return SQLiteStyleRow(self._last_columns, row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [SQLiteStyleRow(self._last_columns, row) for row in rows]

    def close(self):
        self._cursor.close()


class PostgresConnectionAdapter:
    backend = "postgres"

    def __init__(self, connection):
        self._connection = connection

    def cursor(self):
        return PostgresCursorAdapter(self._connection.cursor())

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()


class SQLiteConnectionAdapter:
    backend = "sqlite"

    def __init__(self, connection):
        self._connection = connection

    def cursor(self):
        return self._connection.cursor()

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()


def connect_sqlite(database_path: str):
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return SQLiteConnectionAdapter(connection)


def connect_postgres(database_url: str):
    if not database_url:
        raise RuntimeError(
            "AFRISYNC_DATABASE_URL is required when AFRISYNC_DATABASE_BACKEND=postgres."
        )
    try:
        import psycopg
    except ImportError as error:
        raise RuntimeError(
            "PostgreSQL backend requires psycopg. Install it with: pip install \"psycopg[binary]\""
        ) from error
    return PostgresConnectionAdapter(psycopg.connect(database_url))


def get_afrisync_connection(sqlite_path: str = "server.db"):
    if is_postgres_enabled():
        return connect_postgres(get_database_url())
    return connect_sqlite(sqlite_path)


def replace_qmark_placeholders(sql: str) -> str:
    """Convert SQLite ? placeholders to psycopg %s placeholders, ignoring quoted strings."""
    output: list[str] = []
    in_single = False
    in_double = False
    index = 0
    while index < len(sql):
        char = sql[index]
        if char == "'" and not in_double:
            output.append(char)
            # SQLite/PostgreSQL escaped quote inside single string: ''
            if in_single and index + 1 < len(sql) and sql[index + 1] == "'":
                output.append(sql[index + 1])
                index += 2
                continue
            in_single = not in_single
        elif char == '"' and not in_single:
            output.append(char)
            in_double = not in_double
        elif char == "?" and not in_single and not in_double:
            output.append("%s")
        else:
            output.append(char)
        index += 1
    return "".join(output)


def translate_sqlite_sql_to_postgres(sql: str) -> str:
    translated = sql
    translated = translated.replace(
        "INTEGER PRIMARY KEY AUTOINCREMENT",
        "INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY",
    )
    translated = translated.replace(
        "integer primary key autoincrement",
        "INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY",
    )
    translated = re.sub(r"\bAUTOINCREMENT\b", "", translated, flags=re.IGNORECASE)
    translated = replace_qmark_placeholders(translated)
    return translated


def table_exists(cursor, table_name: str) -> bool:
    if is_postgres_enabled():
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = ?
            """,
            (table_name,),
        )
        return cursor.fetchone() is not None
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def column_exists(cursor, table_name: str, column_name: str) -> bool:
    if is_postgres_enabled():
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = ? AND column_name = ?
            """,
            (table_name, column_name),
        )
        return cursor.fetchone() is not None
    cursor.execute(f"PRAGMA table_info({table_name})")
    return any(row[1] == column_name for row in cursor.fetchall())
