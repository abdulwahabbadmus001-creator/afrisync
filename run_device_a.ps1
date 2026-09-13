$env:AFRISYNC_DEVICE_NAME = "Device A"
$env:AFRISYNC_LOCAL_DB = "afrisync_device_a.db"
$env:AFRISYNC_UPLOAD_ROOT = "uploads_device_a"
$env:AFRISYNC_SESSION_COOKIE = "afrisync_device_a_session"
$env:AFRISYNC_REMOTE_URL = "http://127.0.0.1:8000"

python -m uvicorn local_app:app --reload --host 127.0.0.1 --port 8001
