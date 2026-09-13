$ErrorActionPreference = "Stop"

Write-Host "Starting AfriSync Admin Dashboard in production-style mode..."

if (Test-Path ".\afrisync_production_config.ps1") {
    . ".\afrisync_production_config.ps1"
}

if (-not $env:AFRISYNC_DATABASE_BACKEND) {
    $env:AFRISYNC_DATABASE_BACKEND = "sqlite"
}

Write-Host "Database backend: $env:AFRISYNC_DATABASE_BACKEND"
Write-Host "Admin URL: http://127.0.0.1:8010/admin"
Write-Host "Health check: http://127.0.0.1:8010/health"
Write-Host "Press CTRL + C to stop the admin dashboard."

python start_afrisync.py --service admin --host 127.0.0.1 --port 8010
