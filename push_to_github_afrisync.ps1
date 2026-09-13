$ErrorActionPreference = "Stop"

Write-Host "AfriSync GitHub Push Script"
Write-Host "Repository: https://github.com/abdulwahabbadmus001-creator/afrisync.git"
Write-Host ""

if (-not (Test-Path "server.py")) {
    Write-Host "ERROR: Run this script from the AfriSync project folder. server.py was not found."
    exit 1
}

if (-not (Test-Path ".gitignore")) {
    Write-Host "ERROR: .gitignore is missing. Add it before pushing to avoid uploading private files."
    exit 1
}

git --version

git init

git branch -M main

$remoteExists = git remote 2>$null | Select-String -Pattern "^origin$"
if ($remoteExists) {
    git remote set-url origin "https://github.com/abdulwahabbadmus001-creator/afrisync.git"
} else {
    git remote add origin "https://github.com/abdulwahabbadmus001-creator/afrisync.git"
}

Write-Host ""
Write-Host "Current remote:"
git remote -v

Write-Host ""
Write-Host "Adding project files safely..."
git add .

Write-Host ""
Write-Host "Checking staged files..."
git status --short

Write-Host ""
Write-Host "Removing known private files from staging if accidentally added..."
git reset HEAD .venv server.db afrisync_device_a.db afrisync_device_b.db server_uploads uploads uploads_device_a uploads_device_b backups .env afrisync_email_config.ps1 afrisync_google_config.ps1 afrisync_postgres_config.ps1 afrisync_production_config.ps1 sync_secret.key 2>$null

Write-Host ""
Write-Host "Final status before commit:"
git status --short

Write-Host ""
Write-Host "Creating commit..."
git commit -m "Initial open-source release of AfriSync"

Write-Host ""
Write-Host "Pushing to GitHub..."
git push -u origin main

Write-Host ""
Write-Host "Done. Open: https://github.com/abdulwahabbadmus001-creator/afrisync"
