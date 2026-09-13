$ErrorActionPreference = "Stop"

Write-Host "Starting AfriSync Remote Server with PostgreSQL..."

if (Test-Path ".\afrisync_postgres_config.ps1") {
    . ".\afrisync_postgres_config.ps1"
} else {
    Write-Host "Missing afrisync_postgres_config.ps1"
    Write-Host "Copy afrisync_postgres_config.example.ps1 to afrisync_postgres_config.ps1 and edit AFRISYNC_DATABASE_URL."
    exit 1
}

if (-not $env:AFRISYNC_DATABASE_BACKEND) {
    $env:AFRISYNC_DATABASE_BACKEND = "postgres"
}

if (-not $env:AFRISYNC_DATABASE_URL) {
    Write-Host "AFRISYNC_DATABASE_URL is not set."
    Write-Host "Example: postgresql://postgres:YOUR_PASSWORD@localhost:5432/afrisync"
    exit 1
}

Write-Host "Database backend: $env:AFRISYNC_DATABASE_BACKEND"
Write-Host "Database URL is configured."
Write-Host "Server URL: http://127.0.0.1:8000"
Write-Host "Health check: http://127.0.0.1:8000/health"
Write-Host "Press CTRL + C to stop the server."

python -m uvicorn server:app --host 127.0.0.1 --port 8000
