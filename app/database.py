import sqlite3


LOCAL_DATABASE = "afrisync.db"
SERVER_DATABASE = "server.db"


def get_local_connection():
    """
    Connect to the local AfriSync database.
    """
    return sqlite3.connect(LOCAL_DATABASE)


def get_server_connection():
    """
    Connect to the AfriSync server database.
    """
    return sqlite3.connect(SERVER_DATABASE)