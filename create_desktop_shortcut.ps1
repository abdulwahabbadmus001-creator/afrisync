$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

$exePath = Join-Path $PSScriptRoot "AfriSyncLauncher.exe"
if (-not (Test-Path $exePath)) {
    Write-Host "ERROR: AfriSyncLauncher.exe was not found."
    Write-Host "Run .\build_desktop_exe.ps1 first."
    exit 1
}

$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "AfriSync Launcher.lnk"

$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.Description = "Start AfriSync Remote Server, Device A, Device B, and Admin Dashboard"
$shortcut.Save()

Write-Host "SUCCESS: Desktop shortcut created: $shortcutPath"
