$ErrorActionPreference = "Stop"

Write-Host "Starting AfriSync Desktop Launcher..."
Write-Host "Project folder: $PSScriptRoot"
Write-Host ""

Set-Location $PSScriptRoot
python desktop_launcher.py
