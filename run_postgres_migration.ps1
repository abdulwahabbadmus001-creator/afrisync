$ErrorActionPreference = "Stop"

Write-Host "Starting AfriSync SQLite to PostgreSQL migration..."

if (Test-Path ".\afrisync_postgres_config.ps1") {
    . ".\afrisync_postgres_config.ps1"
} else {
    Write-Host "Missing afrisync_postgres_config.ps1"
    Write-Host "Copy afrisync_postgres_config.example.ps1 to afrisync_postgres_config.ps1 and edit AFRISYNC_DATABASE_URL."
    exit 1
}

if (-not $env:AFRISYNC_DATABASE_URL) {
    Write-Host "AFRISYNC_DATABASE_URL is not set."
    exit 1
}

Write-Host "Running migration script..."
python migrate_server_sqlite_to_postgres.py
Write-Host "Migration command completed."
