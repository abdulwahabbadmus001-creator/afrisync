$ErrorActionPreference = "Stop"

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupRoot = ".\backups\afrisync_backup_$timestamp"

Write-Host "Creating AfriSync backup..."
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

if (Test-Path ".\server.db") {
    Copy-Item ".\server.db" "$backupRoot\server.db" -Force
    Write-Host "Backed up server.db"
} else {
    Write-Host "server.db not found. Skipping."
}

if (Test-Path ".\server_uploads") {
    Copy-Item ".\server_uploads" "$backupRoot\server_uploads" -Recurse -Force
    Write-Host "Backed up server_uploads"
} else {
    Write-Host "server_uploads folder not found. Skipping."
}

if (Test-Path ".\sync_secret.key") {
    Copy-Item ".\sync_secret.key" "$backupRoot\sync_secret.key" -Force
    Write-Host "Backed up sync_secret.key"
}

Write-Host "Backup completed: $backupRoot"
