$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Starting AfriSync Remote Server for phone testing..."
Write-Host "Host: 0.0.0.0"
Write-Host "Port: 8000"

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (!(Test-Path $python)) { $python = "python" }

& $python -m uvicorn server:app --host 0.0.0.0 --port 8000
