from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "afrisync_email_config.ps1"

DEFAULTS = {
    "AFRISYNC_SMTP_HOST": "smtp.gmail.com",
    "AFRISYNC_SMTP_PORT": "587",
    "AFRISYNC_SMTP_USE_SSL": "0",
    "AFRISYNC_SMTP_FROM_NAME": "AfriSync",
    "AFRISYNC_EMAIL_REQUIRE_SMTP": "1",
    "AFRISYNC_EMAIL_ALLOW_DEVELOPMENT_CODE": "0",
}

for key, value in DEFAULTS.items():
    os.environ[key] = value

if CONFIG.exists():
    text = CONFIG.read_text(encoding="utf-8", errors="ignore")
    for key in ("AFRISYNC_SMTP_USERNAME", "AFRISYNC_SMTP_FROM_EMAIL", "AFRISYNC_SMTP_PASSWORD"):
        match = re.search(rf'{re.escape(key)}\s*=\s*"([^"]*)"', text)
        if match:
            os.environ[key] = match.group(1)

print("AfriSync backend launcher")
print("- Host: 0.0.0.0")
print("- Port: 8000")
print("- SMTP configured:", bool(os.environ.get("AFRISYNC_SMTP_USERNAME") and os.environ.get("AFRISYNC_SMTP_PASSWORD")))
print("")

python = ROOT / ".venv" / "Scripts" / "python.exe"
if not python.exists():
    python = Path(sys.executable)

raise SystemExit(subprocess.call([
    str(python), "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"
], cwd=ROOT, env=os.environ.copy()))
