from __future__ import annotations

import importlib.util
import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REQUIRED_FILES = [
    "server.py",
    "local_app.py",
    "admin_app.py",
    "templates/dashboard.html",
    "desktop_launcher.py",
]

PORTS = {
    "Remote Server": 8000,
    "Device A": 8001,
    "Device B": 8002,
    "Admin Dashboard": 8010,
}


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.25):
            return True
    except OSError:
        return False


def check_file(path: str) -> bool:
    return (ROOT / path).exists()


def main() -> int:
    print("AfriSync Desktop Launcher Requirements Check")
    print(f"Project folder: {ROOT}")
    print("")

    ok = True

    print("Required files:")
    for file in REQUIRED_FILES:
        exists = check_file(file)
        print(f"  {'PASS' if exists else 'FAIL'}  {file}")
        ok = ok and exists

    print("")
    print("Python packages:")
    uvicorn_ok = importlib.util.find_spec("uvicorn") is not None
    fastapi_ok = importlib.util.find_spec("fastapi") is not None
    print(f"  {'PASS' if uvicorn_ok else 'FAIL'}  uvicorn")
    print(f"  {'PASS' if fastapi_ok else 'FAIL'}  fastapi")
    ok = ok and uvicorn_ok and fastapi_ok

    print("")
    print("Ports currently in use:")
    for name, port in PORTS.items():
        used = port_open(port)
        print(f"  {'OPEN' if used else 'FREE'}  {name}: {port}")

    print("")
    if ok:
        print("RESULT: Launcher requirements look good.")
        return 0
    print("RESULT: Some requirements are missing. Fix the FAIL items above.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
