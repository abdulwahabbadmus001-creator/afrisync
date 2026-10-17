@echo off
set "BACKEND=C:\Projects\afrisync"
set "MOBILE=C:\Users\USER\Downloads\afrisync_mobile_app_v1\afrisync-mobile"
set "CLI=C:\Users\USER\AppData\Roaming\npm\afrisync.cmd"

start "AfriSync Backend" cmd /k "cd /d %BACKEND% && .venv\Scripts\python.exe start_afrisync_backend.py"
timeout /t 2 /nobreak >nul
start "AfriSync Mobile" cmd /k "cd /d %MOBILE% && %CLI% run -- npx.cmd expo start --clear"
