$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$env:AFRISYNC_DEVICE_NAME = "Device A"
$env:AFRISYNC_LOCAL_DB = "afrisync_device_a.db"
$env:AFRISYNC_UPLOAD_ROOT = "uploads_device_a"
$env:AFRISYNC_SESSION_COOKIE = "afrisync_device_a_session"
$env:AFRISYNC_REMOTE_URL = "http://127.0.0.1:8000"

Write-Host "Starting AfriSync Device A for phone testing..."
Write-Host "Host: 0.0.0.0"
Write-Host "Port: 8001"

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (!(Test-Path $python)) { $python = "python" }

& $python -m uvicorn local_app:app --host 0.0.0.0 --port 8001
