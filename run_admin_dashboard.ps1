$env:AFRISYNC_SERVER_DB="server.db"
$env:AFRISYNC_SERVER_UPLOAD_ROOT="server_uploads"
$env:AFRISYNC_ADMIN_USERNAME="admin"
$env:AFRISYNC_ADMIN_PASSWORD="admin12345"
$env:AFRISYNC_ADMIN_SESSION_HOURS="8"

Write-Host ""
Write-Host "AfriSync Admin Dashboard v2.0" -ForegroundColor Cyan
Write-Host "URL: http://127.0.0.1:8010/admin" -ForegroundColor Green
Write-Host "Username: admin" -ForegroundColor Yellow
Write-Host "Password: admin12345" -ForegroundColor Yellow
Write-Host ""

python -m uvicorn admin_app:app --host 127.0.0.1 --port 8010
