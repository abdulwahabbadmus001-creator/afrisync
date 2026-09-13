"""
Production startup entrypoint for AfriSync.

Usage:
    python start_afrisync.py

Environment:
    AFRISYNC_SERVICE=remote   -> starts server:app
    AFRISYNC_SERVICE=admin    -> starts admin_app:app
    PORT=8000                 -> platform-provided port
    HOST=0.0.0.0              -> production default
"""

from __future__ import annotations

import os
import sys

import uvicorn


def bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    service = os.getenv("AFRISYNC_SERVICE", "remote").strip().lower()
    if service in {"remote", "server", "api"}:
        app_target = "server:app"
        default_port = 8000
        service_name = "Remote Server"
    elif service in {"admin", "admin-dashboard", "dashboard"}:
        app_target = "admin_app:app"
        default_port = 8010
        service_name = "Admin Dashboard"
    else:
        print("Invalid AFRISYNC_SERVICE. Use 'remote' or 'admin'.", file=sys.stderr)
        sys.exit(1)

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", str(default_port)))
    reload = bool_env("AFRISYNC_RELOAD", False)

    print(f"Starting AfriSync {service_name}")
    print(f"App: {app_target}")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Reload: {reload}")

    uvicorn.run(app_target, host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
