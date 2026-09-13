$ErrorActionPreference = "Stop"

$env:AFRISYNC_SERVER_DB = "server.db"
$env:AFRISYNC_SERVER_UPLOAD_ROOT = "server_uploads"
$env:AFRISYNC_SYNC_SECRET_FILE = ".afrisync_server_secret"

# Real personal-email delivery settings.
# Create afrisync_email_config.ps1 from afrisync_email_config.example.ps1
# and put your sender Gmail address + Gmail App Password there.
$env:AFRISYNC_SMTP_HOST = "smtp.gmail.com"
$env:AFRISYNC_SMTP_PORT = "587"
$env:AFRISYNC_SMTP_USE_SSL = "0"
$env:AFRISYNC_SMTP_FROM_NAME = "AfriSync"
$env:AFRISYNC_EMAIL_REQUIRE_SMTP = "1"
$env:AFRISYNC_EMAIL_ALLOW_DEVELOPMENT_CODE = "0"

$configPath = Join-Path $PSScriptRoot "afrisync_email_config.ps1"
$googleConfigPath = Join-Path $PSScriptRoot "afrisync_google_config.ps1"
$env:AFRISYNC_GOOGLE_CLIENT_ID = ""

if (Test-Path $configPath) {
    . $configPath
    Write-Host "Loaded email sender config from afrisync_email_config.ps1" -ForegroundColor Green
} else {
    Write-Host "Email sender config file not found: afrisync_email_config.ps1" -ForegroundColor Yellow
    Write-Host "Copy afrisync_email_config.example.ps1 to afrisync_email_config.ps1 and add your Gmail App Password." -ForegroundColor Yellow
}

if (Test-Path $googleConfigPath) {
    . $googleConfigPath
    Write-Host "Loaded Google OAuth config from afrisync_google_config.ps1" -ForegroundColor Green
} else {
    Write-Host "Google OAuth config file not found: afrisync_google_config.ps1" -ForegroundColor Yellow
    Write-Host "Copy afrisync_google_config.example.ps1 to afrisync_google_config.ps1 and add your Web Client ID." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "AfriSync Remote Server" -ForegroundColor Cyan
Write-Host "URL: http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "SMTP Host: $env:AFRISYNC_SMTP_HOST" -ForegroundColor Cyan
Write-Host "SMTP Port: $env:AFRISYNC_SMTP_PORT" -ForegroundColor Cyan
Write-Host "SMTP Username: $env:AFRISYNC_SMTP_USERNAME" -ForegroundColor Cyan
Write-Host "From Email: $env:AFRISYNC_SMTP_FROM_EMAIL" -ForegroundColor Cyan
Write-Host "Development code on screen: $env:AFRISYNC_EMAIL_ALLOW_DEVELOPMENT_CODE" -ForegroundColor Cyan
Write-Host "Google OAuth Client ID configured: $([bool]$env:AFRISYNC_GOOGLE_CLIENT_ID)" -ForegroundColor Cyan
Write-Host ""

python -m uvicorn server:app --reload --host 127.0.0.1 --port 8000
