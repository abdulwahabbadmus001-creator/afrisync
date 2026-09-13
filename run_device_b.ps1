$env:AFRISYNC_DEVICE_NAME = "Device B"
$env:AFRISYNC_LOCAL_DB = "afrisync_device_b.db"
$env:AFRISYNC_UPLOAD_ROOT = "uploads_device_b"
$env:AFRISYNC_SESSION_COOKIE = "afrisync_device_b_session"
$env:AFRISYNC_REMOTE_URL = "http://127.0.0.1:8000"

python -m uvicorn local_app:app --reload --host 127.0.0.1 --port 8002
