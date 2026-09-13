import os
import sqlite3


def get_local_database_path():
    """
    Return the SQLite file used by the local AfriSync client.

    Default: afrisync.db
    Multi-device testing can override this with AFRISYNC_LOCAL_DB.
    """
    return os.getenv("AFRISYNC_LOCAL_DB", "afrisync.db")


def get_server_database_path():
    """
    Return the SQLite file used by the remote AfriSync server.

    Default: server.db
    Test/deployment setups can override this with AFRISYNC_SERVER_DB.
    """
    return os.getenv("AFRISYNC_SERVER_DB", "server.db")


def get_local_connection():
    return sqlite3.connect(get_local_database_path())


def get_server_connection():
    return sqlite3.connect(get_server_database_path())
