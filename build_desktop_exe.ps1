$ErrorActionPreference = "Stop"

Write-Host "AfriSync Desktop EXE Builder"
Write-Host "Project folder: $PSScriptRoot"
Write-Host ""

Set-Location $PSScriptRoot

if (-not (Test-Path ".\desktop_launcher.py")) {
    Write-Host "ERROR: desktop_launcher.py was not found in this folder."
    exit 1
}

Write-Host "Installing desktop packaging requirement..."
python -m pip install -r requirements_desktop.txt

Write-Host ""
Write-Host "Building AfriSyncLauncher.exe..."
python -m PyInstaller --noconfirm --onefile --windowed --name AfriSyncLauncher desktop_launcher.py

if (Test-Path ".\dist\AfriSyncLauncher.exe") {
    Copy-Item ".\dist\AfriSyncLauncher.exe" ".\AfriSyncLauncher.exe" -Force
    Write-Host ""
    Write-Host "SUCCESS: AfriSyncLauncher.exe has been created in your AfriSync folder."
    Write-Host "Run it by double-clicking: $PSScriptRoot\AfriSyncLauncher.exe"
} else {
    Write-Host ""
    Write-Host "ERROR: Build finished but AfriSyncLauncher.exe was not found."
    exit 1
}
