$ErrorActionPreference = "Stop"

Write-Host "Starting AfriSync Remote Server in production-style mode..."

if (Test-Path ".\afrisync_production_config.ps1") {
    . ".\afrisync_production_config.ps1"
} elseif (Test-Path ".\afrisync_email_config.ps1") {
    . ".\afrisync_email_config.ps1"
}

if (Test-Path ".\afrisync_google_config.ps1") {
    . ".\afrisync_google_config.ps1"
}

if (-not $env:AFRISYNC_DATABASE_BACKEND) {
    $env:AFRISYNC_DATABASE_BACKEND = "sqlite"
}

Write-Host "Database backend: $env:AFRISYNC_DATABASE_BACKEND"
Write-Host "Server URL: http://127.0.0.1:8000"
Write-Host "Health check: http://127.0.0.1:8000/health"
Write-Host "Press CTRL + C to stop the server."

python start_afrisync.py --service remote --host 127.0.0.1 --port 8000
