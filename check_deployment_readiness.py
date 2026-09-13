"""AfriSync deployment readiness checker.

Run:
    python check_deployment_readiness.py

This does not modify your database. It checks files, environment variables,
security settings, and optional PostgreSQL connectivity.
"""

from __future__ import annotations

import importlib.util
import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REQUIRED_FILES = [
    "server.py",
    "admin_app.py",
    "local_app.py",
    "background_sync.py",
    "pull_sync.py",
    "network.py",
    "app/database.py",
    "app/sync_engine.py",
    "templates/dashboard.html",
    "afrisync_db.py",
    "start_afrisync.py",
    "requirements.txt",
    "requirements_production.txt",
]


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def is_truthy(name: str, default: str = "0") -> bool:
    return env(name, default).lower() in {"1", "true", "yes", "on"}


def print_line(kind: str, message: str) -> None:
    labels = {
        "ok": "[OK]",
        "warn": "[WARN]",
        "fail": "[FAIL]",
        "info": "[INFO]",
    }
    print(f"{labels.get(kind, '[INFO]')} {message}")


def can_import(package_name: str) -> bool:
    return importlib.util.find_spec(package_name) is not None


def check_files(results: list[tuple[str, str]]) -> None:
    for relative in REQUIRED_FILES:
        path = ROOT / relative
        if path.exists():
            results.append(("ok", f"Found {relative}"))
        else:
            results.append(("fail", f"Missing {relative}"))


def check_python_packages(results: list[tuple[str, str]]) -> None:
    packages = ["fastapi", "uvicorn", "pydantic", "requests"]
    for package in packages:
        if can_import(package):
            results.append(("ok", f"Python package available: {package}"))
        else:
            results.append(("fail", f"Missing Python package: {package}"))

    if env("AFRISYNC_DATABASE_BACKEND", "sqlite").lower() in {"postgres", "postgresql", "pg"}:
        if can_import("psycopg"):
            results.append(("ok", "PostgreSQL driver available: psycopg"))
        else:
            results.append(("fail", "PostgreSQL backend selected but psycopg is not installed."))


def check_environment(results: list[tuple[str, str]]) -> None:
    backend = env("AFRISYNC_DATABASE_BACKEND", "sqlite").lower()
    results.append(("info", f"Database backend: {backend}"))

    if backend in {"postgres", "postgresql", "pg"}:
        if env("AFRISYNC_DATABASE_URL"):
            results.append(("ok", "AFRISYNC_DATABASE_URL is set."))
        else:
            results.append(("fail", "AFRISYNC_DATABASE_URL is required for PostgreSQL deployment."))
    else:
        results.append(("warn", "Using SQLite. Good for local testing, not ideal for public production deployment."))

    admin_password = env("AFRISYNC_ADMIN_PASSWORD")
    if not admin_password:
        results.append(("warn", "AFRISYNC_ADMIN_PASSWORD is not set. Admin dashboard may use local default."))
    elif admin_password == "admin12345" or "replace-this" in admin_password.lower():
        results.append(("fail", "Change the default admin password before deployment."))
    elif len(admin_password) < 12:
        results.append(("warn", "Admin password is set but should be at least 12 characters."))
    else:
        results.append(("ok", "Admin password is set."))

    if env("AFRISYNC_GOOGLE_CLIENT_ID"):
        results.append(("ok", "Google OAuth Client ID is set."))
    else:
        results.append(("warn", "AFRISYNC_GOOGLE_CLIENT_ID is not set. Continue with Google will not work."))

    smtp_required = is_truthy("AFRISYNC_EMAIL_REQUIRE_SMTP", "1")
    smtp_values = [
        env("AFRISYNC_SMTP_HOST"),
        env("AFRISYNC_SMTP_PORT"),
        env("AFRISYNC_SMTP_USERNAME"),
        env("AFRISYNC_SMTP_PASSWORD"),
        env("AFRISYNC_SMTP_FROM_EMAIL"),
    ]
    if all(smtp_values):
        results.append(("ok", "SMTP email delivery variables are set."))
    elif smtp_required:
        results.append(("fail", "SMTP is required but one or more SMTP variables are missing."))
    else:
        results.append(("warn", "SMTP is not fully configured. Development code fallback may be used."))

    if is_truthy("AFRISYNC_EMAIL_ALLOW_DEVELOPMENT_CODE", "0"):
        results.append(("fail", "Disable AFRISYNC_EMAIL_ALLOW_DEVELOPMENT_CODE before public deployment."))
    else:
        results.append(("ok", "Development verification-code display is disabled."))


def check_postgres_connection(results: list[tuple[str, str]]) -> None:
    backend = env("AFRISYNC_DATABASE_BACKEND", "sqlite").lower()
    if backend not in {"postgres", "postgresql", "pg"}:
        return
    if not env("AFRISYNC_DATABASE_URL") or not can_import("psycopg"):
        return
    try:
        import psycopg
        with psycopg.connect(env("AFRISYNC_DATABASE_URL"), connect_timeout=5) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        results.append(("ok", "PostgreSQL connection succeeded."))
    except Exception as error:
        results.append(("fail", f"PostgreSQL connection failed: {error}"))


def main() -> int:
    results: list[tuple[str, str]] = []
    print("AfriSync Deployment Readiness Check")
    print("=" * 42)

    check_files(results)
    check_python_packages(results)
    check_environment(results)
    check_postgres_connection(results)

    print()
    for kind, message in results:
        print_line(kind, message)

    fail_count = sum(1 for kind, _ in results if kind == "fail")
    warn_count = sum(1 for kind, _ in results if kind == "warn")

    print()
    print("Summary")
    print("-" * 20)
    print(f"Failures: {fail_count}")
    print(f"Warnings: {warn_count}")

    if fail_count:
        print("Result: NOT READY. Fix the failures above first.")
        return 1
    if warn_count:
        print("Result: ALMOST READY. Review warnings before public deployment.")
        return 0
    print("Result: READY.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
