import os

import requests


def get_remote_server_url():
    return os.getenv("AFRISYNC_REMOTE_URL", "http://127.0.0.1:8000").rstrip("/")


def is_server_available(timeout=3):
    try:
        response = requests.get(f"{get_remote_server_url()}/health", timeout=timeout)
        return response.status_code < 500
    except requests.RequestException:
        return False
