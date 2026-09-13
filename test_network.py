from network import is_server_available


if is_server_available():
    print("AfriSync server is available.")
else:
    print("AfriSync server is unavailable.")