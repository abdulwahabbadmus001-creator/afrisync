import base64
import binascii
import hashlib
import json
import os
import re
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, field_validator
from background_sync import start_background_sync, stop_background_sync

from app.database import get_local_connection
from app.sync_engine import synchronize_pending_projects
from network import is_server_available


app = FastAPI(title="AfriSync Local App")

DEVICE_NAME = os.getenv("AFRISYNC_DEVICE_NAME", "AfriSync Local Device")
REMOTE_SERVER = os.getenv("AFRISYNC_REMOTE_URL", "http://127.0.0.1:8000").rstrip("/")
LOCAL_DATABASE = os.getenv("AFRISYNC_LOCAL_DB", "afrisync.db")
UPLOAD_ROOT = Path(os.getenv("AFRISYNC_UPLOAD_ROOT", "uploads"))
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024

UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


# ============================================================
# TIME
# ============================================================

def current_timestamp():
    return datetime.now().isoformat()


# ============================================================
# LOCAL DATABASE INITIALIZATION
# ============================================================

def column_exists(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return any(row[1] == column_name for row in cursor.fetchall())


def initialize_local_database():
    connection = get_local_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS local_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            full_name TEXT,
            email_verified INTEGER DEFAULT 1,
            password_hash TEXT NOT NULL,
            cached_at TEXT NOT NULL
        )
        """
    )

    local_user_columns = [
        ("email", "TEXT"),
        ("full_name", "TEXT"),
        ("email_verified", "INTEGER DEFAULT 1"),
        ("google_sub", "TEXT"),
        ("auth_provider", "TEXT DEFAULT 'password'"),
        ("avatar_url", "TEXT"),
    ]
    for column_name, definition in local_user_columns:
        if not column_exists(cursor, "local_users", column_name):
            cursor.execute(
                f"ALTER TABLE local_users ADD COLUMN {column_name} {definition}"
            )
    cursor.execute("UPDATE local_users SET email_verified = 1 WHERE email_verified IS NULL")
    cursor.execute("UPDATE local_users SET auth_provider = COALESCE(auth_provider, 'password') WHERE auth_provider IS NULL OR auth_provider = ''")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS local_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_hash TEXT UNIQUE NOT NULL,
            csrf_hash TEXT NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
        """
    )



    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            action TEXT NOT NULL,
            entity_type TEXT DEFAULT 'system',
            entity_uuid TEXT,
            message TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            started_at TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            status TEXT NOT NULL,
            total INTEGER DEFAULT 0,
            successful INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            conflicts INTEGER DEFAULT 0,
            message TEXT,
            details TEXT
        )
        """
    )



    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notification_uuid TEXT UNIQUE NOT NULL,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            category TEXT DEFAULT 'INFO',
            entity_type TEXT DEFAULT 'system',
            entity_uuid TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS project_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_uuid TEXT UNIQUE NOT NULL,
            project_uuid TEXT NOT NULL,
            user_id TEXT NOT NULL,
            content TEXT NOT NULL,
            sync_status TEXT DEFAULT 'PENDING',
            is_deleted INTEGER DEFAULT 0,
            deleted_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            sync_attempts INTEGER DEFAULT 0,
            last_sync_attempt TEXT,
            last_sync_error TEXT,
            last_synced_at TEXT,
            version INTEGER DEFAULT 0,
            conflict_data TEXT
        )
        """
    )

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_notes_project ON project_notes (project_uuid, user_id, is_deleted)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_notes_user_updated ON project_notes (user_id, updated_at)"
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS project_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attachment_uuid TEXT UNIQUE NOT NULL,
            project_uuid TEXT NOT NULL,
            user_id TEXT NOT NULL,
            original_file_name TEXT NOT NULL,
            stored_file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT DEFAULT 'application/octet-stream',
            file_size INTEGER DEFAULT 0,
            sync_status TEXT DEFAULT 'PENDING',
            is_deleted INTEGER DEFAULT 0,
            deleted_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            sync_attempts INTEGER DEFAULT 0,
            last_sync_attempt TEXT,
            last_sync_error TEXT,
            last_synced_at TEXT,
            version INTEGER DEFAULT 0,
            conflict_data TEXT
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_attachments_project ON project_attachments (project_uuid, user_id, is_deleted)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_attachments_user_updated ON project_attachments (user_id, updated_at)"
    )


    attachment_columns = [
        ("sync_attempts", "INTEGER DEFAULT 0"),
        ("last_sync_attempt", "TEXT"),
        ("last_sync_error", "TEXT"),
        ("last_synced_at", "TEXT"),
        ("version", "INTEGER DEFAULT 0"),
        ("conflict_data", "TEXT"),
    ]

    for column_name, definition in attachment_columns:
        if not column_exists(cursor, "project_attachments", column_name):
            cursor.execute(
                f"ALTER TABLE project_attachments ADD COLUMN {column_name} {definition}"
            )

    cursor.execute(
        "UPDATE project_attachments SET is_deleted = 1 WHERE sync_status = 'PENDING'"
    )
    cursor.execute(
        "UPDATE project_attachments SET sync_status = 'PENDING' WHERE sync_status IS NULL OR sync_status IN ('LOCAL', 'LOCAL_DELETED')"
    )
    cursor.execute(
        "UPDATE project_attachments SET is_deleted = 0 WHERE is_deleted IS NULL"
    )
    cursor.execute(
        "UPDATE project_attachments SET version = 0 WHERE version IS NULL"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_attachments_sync_user ON project_attachments (user_id, sync_status)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_attachments_uuid_user ON project_attachments (attachment_uuid, user_id)"
    )

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_activity_logs_user_created ON activity_logs (user_id, created_at)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_sync_history_user_completed ON sync_history (user_id, completed_at)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_notifications_user_read_created ON notifications (user_id, is_read, created_at)"
    )
    cursor.execute(
        "UPDATE notifications SET is_read = 0 WHERE is_read IS NULL"
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS remote_sync_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            sync_token TEXT NOT NULL,
            expires_at TEXT,
            saved_at TEXT NOT NULL
        )
        """
    )


    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS project_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_uuid TEXT NOT NULL,
            owner_user_id TEXT NOT NULL,
            member_user_id TEXT NOT NULL,
            member_username TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'VIEWER',
            is_deleted INTEGER DEFAULT 0,
            invited_at TEXT,
            updated_at TEXT,
            UNIQUE(project_uuid, member_user_id)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_local_project_members_member ON project_members (member_user_id, is_deleted)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_local_project_members_project ON project_members (project_uuid, is_deleted)"
    )
    cursor.execute(
        "UPDATE project_members SET role = UPPER(role) WHERE role IS NOT NULL"
    )
    cursor.execute(
        "UPDATE project_members SET role = 'VIEWER' WHERE role IS NULL OR role NOT IN ('EDITOR','VIEWER')"
    )
    cursor.execute(
        "UPDATE project_members SET is_deleted = 0 WHERE is_deleted IS NULL"
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT,
            progress INTEGER DEFAULT 0,
            sync_status TEXT DEFAULT 'PENDING',
            project_uuid TEXT UNIQUE,
            sync_attempts INTEGER DEFAULT 0,
            last_sync_attempt TEXT,
            last_sync_error TEXT,
            last_synced_at TEXT,
            user_id TEXT,
            is_deleted INTEGER DEFAULT 0,
            deleted_at TEXT,
            version INTEGER DEFAULT 0,
            updated_at TEXT,
            conflict_data TEXT
        )
        """
    )

    required_columns = [
        ("user_id", "TEXT"),
        ("is_deleted", "INTEGER DEFAULT 0"),
        ("deleted_at", "TEXT"),
        ("version", "INTEGER DEFAULT 0"),
        ("updated_at", "TEXT"),
        ("conflict_data", "TEXT"),
        ("sync_attempts", "INTEGER DEFAULT 0"),
        ("last_sync_attempt", "TEXT"),
        ("last_sync_error", "TEXT"),
        ("last_synced_at", "TEXT"),
    ]

    for column_name, definition in required_columns:
        if not column_exists(cursor, "projects", column_name):
            cursor.execute(
                f"ALTER TABLE projects ADD COLUMN {column_name} {definition}"
            )

    cursor.execute(
        "UPDATE projects SET is_deleted = 0 WHERE is_deleted IS NULL"
    )
    cursor.execute(
        "UPDATE projects SET version = 0 WHERE version IS NULL"
    )

    connection.commit()
    connection.close()


initialize_local_database()


def upgrade_project_notes_for_remote_sync():
    """
    Upgrade existing local-only notes so they can synchronize with the
    remote server. Old notes that were marked LOCAL become PENDING,
    which means they will be uploaded automatically.
    """
    connection = get_local_connection()
    cursor = connection.cursor()

    note_columns = [
        ("sync_attempts", "INTEGER DEFAULT 0"),
        ("last_sync_attempt", "TEXT"),
        ("last_sync_error", "TEXT"),
        ("last_synced_at", "TEXT"),
        ("version", "INTEGER DEFAULT 0"),
        ("conflict_data", "TEXT"),
    ]

    for column_name, definition in note_columns:
        if not column_exists(cursor, "project_notes", column_name):
            cursor.execute(
                f"ALTER TABLE project_notes ADD COLUMN {column_name} {definition}"
            )

    cursor.execute(
        "UPDATE project_notes SET sync_status = 'PENDING' WHERE sync_status IS NULL OR sync_status = 'LOCAL'"
    )
    cursor.execute(
        "UPDATE project_notes SET is_deleted = 0 WHERE is_deleted IS NULL"
    )
    cursor.execute(
        "UPDATE project_notes SET version = 0 WHERE version IS NULL"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_notes_sync_user ON project_notes (user_id, sync_status)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_notes_uuid_user ON project_notes (note_uuid, user_id)"
    )

    connection.commit()
    connection.close()


upgrade_project_notes_for_remote_sync()


@app.on_event("startup")
def start_local_background_services():
    start_background_sync()


@app.on_event("shutdown")
def stop_local_background_services():
    stop_background_sync()


# ============================================================
# PASSWORD CACHE
# ============================================================

def hash_password(password):
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()
    return f"{salt}${password_hash}"


def verify_password(password, stored_password):
    try:
        salt, stored_hash = stored_password.split("$", 1)
        password_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100_000,
        ).hex()
        return secrets.compare_digest(password_hash, stored_hash)
    except (ValueError, AttributeError):
        return False


def cache_user(
    user_id,
    username,
    password,
    email=None,
    full_name=None,
    email_verified=1,
    google_sub=None,
    auth_provider="password",
    avatar_url=None,
):
    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO local_users (
            user_id, username, email, full_name, email_verified, password_hash, cached_at,
            google_sub, auth_provider, avatar_url
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(username) DO UPDATE SET
            user_id = excluded.user_id,
            email = excluded.email,
            full_name = excluded.full_name,
            email_verified = excluded.email_verified,
            password_hash = excluded.password_hash,
            cached_at = excluded.cached_at,
            google_sub = excluded.google_sub,
            auth_provider = excluded.auth_provider,
            avatar_url = excluded.avatar_url
        """,
        (
            user_id,
            username,
            (email or None),
            (full_name or None),
            1 if email_verified else 0,
            hash_password(password),
            current_timestamp(),
            google_sub or None,
            auth_provider or "password",
            avatar_url or None,
        ),
    )
    connection.commit()
    connection.close()


def offline_login(username, password):
    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT user_id, username, password_hash
        FROM local_users
        WHERE lower(username) = lower(?)
           OR lower(COALESCE(email, '')) = lower(?)
        """,
        (username, username),
    )
    row = cursor.fetchone()
    connection.close()

    if not row:
        return None

    user_id, saved_username, stored_hash = row
    if not verify_password(password, stored_hash):
        return None

    return {
        "message": "Offline login successful.",
        "user_id": user_id,
        "username": saved_username,
        "offline": True,
    }


# ============================================================
# SECURE LOCAL SESSIONS
# ============================================================

SESSION_COOKIE = os.getenv("AFRISYNC_SESSION_COOKIE", "afrisync_session")
SESSION_HOURS = int(os.getenv("AFRISYNC_SESSION_HOURS", "12"))


def token_hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_session(user_id, username):
    session_token = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)
    now = datetime.now()
    expires = now + timedelta(hours=SESSION_HOURS)

    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        "DELETE FROM local_sessions WHERE expires_at <= ?",
        (now.isoformat(),),
    )
    cursor.execute(
        """
        INSERT INTO local_sessions (
            token_hash, csrf_hash, user_id, username,
            created_at, last_seen_at, expires_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            token_hash(session_token),
            token_hash(csrf_token),
            user_id,
            username,
            now.isoformat(),
            now.isoformat(),
            expires.isoformat(),
        ),
    )
    connection.commit()
    connection.close()
    return session_token, csrf_token, expires


def get_session(request):
    raw_token = request.cookies.get(SESSION_COOKIE)
    if not raw_token:
        raise HTTPException(status_code=401, detail="Authentication required.")

    connection = get_local_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT token_hash, csrf_hash, user_id, username, expires_at
        FROM local_sessions
        WHERE token_hash = ?
        """,
        (token_hash(raw_token),),
    )
    row = cursor.fetchone()

    if not row:
        connection.close()
        raise HTTPException(status_code=401, detail="Session is invalid or expired.")

    now = datetime.now()
    try:
        expires = datetime.fromisoformat(row["expires_at"])
    except (TypeError, ValueError):
        expires = now - timedelta(seconds=1)

    if expires <= now:
        cursor.execute(
            "DELETE FROM local_sessions WHERE token_hash = ?",
            (token_hash(raw_token),),
        )
        connection.commit()
        connection.close()
        raise HTTPException(status_code=401, detail="Session has expired. Please log in again.")

    cursor.execute(
        "UPDATE local_sessions SET last_seen_at = ? WHERE token_hash = ?",
        (now.isoformat(), token_hash(raw_token)),
    )
    connection.commit()
    connection.close()

    return {
        "user_id": row["user_id"],
        "username": row["username"],
        "csrf_hash": row["csrf_hash"],
        "raw_token": raw_token,
    }


def require_csrf(request, session):
    csrf_token = request.headers.get("X-CSRF-Token", "")
    if not csrf_token or not secrets.compare_digest(
        token_hash(csrf_token),
        session["csrf_hash"],
    ):
        raise HTTPException(status_code=403, detail="Invalid CSRF token.")


def authenticated_response(data, user_id, username):
    session_token, csrf_token, expires = create_session(user_id, username)
    payload = dict(data)
    payload.pop("user_id", None)
    payload.pop("sync_token", None)
    payload.pop("sync_token_expires_at", None)
    payload["username"] = username
    payload["device_name"] = DEVICE_NAME
    payload["csrf_token"] = csrf_token

    response = JSONResponse(payload)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_token,
        max_age=SESSION_HOURS * 60 * 60,
        httponly=True,
        samesite="strict",
        secure=False,
        path="/",
    )
    return response


def clear_session(request):
    raw_token = request.cookies.get(SESSION_COOKIE)
    if raw_token:
        connection = get_local_connection()
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM local_sessions WHERE token_hash = ?",
            (token_hash(raw_token),),
        )
        connection.commit()
        connection.close()


# ============================================================
# REMOTE SYNC TOKEN CACHE
# ============================================================


def cache_remote_sync_token(user_id, username, sync_token, expires_at=None):
    """
    Store the remote API token that server.py issues after online login.
    The sync engine uses this token to authenticate with port 8000.
    """
    if not user_id or not sync_token:
        return

    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS remote_sync_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            sync_token TEXT NOT NULL,
            expires_at TEXT,
            saved_at TEXT NOT NULL
        )
        """
    )


    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS project_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_uuid TEXT NOT NULL,
            owner_user_id TEXT NOT NULL,
            member_user_id TEXT NOT NULL,
            member_username TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'VIEWER',
            is_deleted INTEGER DEFAULT 0,
            invited_at TEXT,
            updated_at TEXT,
            UNIQUE(project_uuid, member_user_id)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_local_project_members_member ON project_members (member_user_id, is_deleted)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_local_project_members_project ON project_members (project_uuid, is_deleted)"
    )
    cursor.execute(
        "UPDATE project_members SET role = UPPER(role) WHERE role IS NOT NULL"
    )
    cursor.execute(
        "UPDATE project_members SET role = 'VIEWER' WHERE role IS NULL OR role NOT IN ('EDITOR','VIEWER')"
    )
    cursor.execute(
        "UPDATE project_members SET is_deleted = 0 WHERE is_deleted IS NULL"
    )
    cursor.execute(
        """
        INSERT INTO remote_sync_tokens (
            user_id, username, sync_token, expires_at, saved_at
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            sync_token = excluded.sync_token,
            expires_at = excluded.expires_at,
            saved_at = excluded.saved_at
        """,
        (
            user_id,
            username,
            sync_token,
            expires_at,
            current_timestamp(),
        ),
    )
    connection.commit()
    connection.close()


def has_remote_sync_token(user_id):
    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS remote_sync_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            sync_token TEXT NOT NULL,
            expires_at TEXT,
            saved_at TEXT NOT NULL
        )
        """
    )


    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS project_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_uuid TEXT NOT NULL,
            owner_user_id TEXT NOT NULL,
            member_user_id TEXT NOT NULL,
            member_username TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'VIEWER',
            is_deleted INTEGER DEFAULT 0,
            invited_at TEXT,
            updated_at TEXT,
            UNIQUE(project_uuid, member_user_id)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_local_project_members_member ON project_members (member_user_id, is_deleted)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_local_project_members_project ON project_members (project_uuid, is_deleted)"
    )
    cursor.execute(
        "UPDATE project_members SET role = UPPER(role) WHERE role IS NOT NULL"
    )
    cursor.execute(
        "UPDATE project_members SET role = 'VIEWER' WHERE role IS NULL OR role NOT IN ('EDITOR','VIEWER')"
    )
    cursor.execute(
        "UPDATE project_members SET is_deleted = 0 WHERE is_deleted IS NULL"
    )
    cursor.execute(
        """
        SELECT sync_token
        FROM remote_sync_tokens
        WHERE user_id = ?
        """,
        (user_id,),
    )
    row = cursor.fetchone()
    connection.close()
    return bool(row and row[0])


def get_cached_remote_sync_token(user_id):
    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT sync_token
        FROM remote_sync_tokens
        WHERE user_id = ?
        """,
        (user_id,),
    )
    row = cursor.fetchone()
    connection.close()
    return row[0] if row else None



def public_login_payload(data):
    """
    Prevent the remote sync token from being exposed to dashboard JavaScript.
    The local app stores it privately for the sync engine instead.
    """
    payload = dict(data)
    payload.pop("sync_token", None)
    payload.pop("sync_token_expires_at", None)
    return payload


# ============================================================
# ACTIVITY LOG + SYNC HISTORY
# ============================================================

def safe_json_dumps(value):
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        return json.dumps({"value": str(value)}, ensure_ascii=False)


def safe_json_loads(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value



NOTIFICATION_TITLES = {
    "REGISTER": "Account created",
    "LOGIN_ONLINE": "Online login",
    "LOGIN_OFFLINE": "Offline login",
    "CREATE_PROJECT": "Project created",
    "UPDATE_PROJECT": "Project updated",
    "DELETE_PROJECT": "Project deleted",
    "CREATE_NOTE": "Note added",
    "UPDATE_NOTE": "Note updated",
    "DELETE_NOTE": "Note deleted",
    "UPLOAD_ATTACHMENT": "Attachment uploaded",
    "DELETE_ATTACHMENT": "Attachment deleted",
    "RESOLVE_CONFLICT_SERVER": "Conflict resolved",
    "RESOLVE_CONFLICT_LOCAL": "Conflict resolved",
    "RESOLVE_CONFLICT_LOCAL_QUEUED": "Conflict queued",
    "RESOLVE_CONFLICT_FAILED": "Conflict still active",
    "INVITE_MEMBER": "Team invite sent",
    "UPDATE_MEMBER_ROLE": "Member role updated",
    "REMOVE_MEMBER": "Member removed",
    "SYNC_MANUAL": "Manual sync completed",
    "SYNC_OFFLINE": "Sync waiting for server",
    "SYNC_FAILED": "Sync failed",
    "SYNC_AUTH_REQUIRED": "Sync login required",
}

NOTIFICATION_CATEGORIES = {
    "REGISTER": "SUCCESS",
    "LOGIN_ONLINE": "INFO",
    "LOGIN_OFFLINE": "WARNING",
    "CREATE_PROJECT": "SUCCESS",
    "UPDATE_PROJECT": "INFO",
    "DELETE_PROJECT": "WARNING",
    "CREATE_NOTE": "INFO",
    "UPDATE_NOTE": "INFO",
    "DELETE_NOTE": "WARNING",
    "UPLOAD_ATTACHMENT": "INFO",
    "DELETE_ATTACHMENT": "WARNING",
    "RESOLVE_CONFLICT_SERVER": "SUCCESS",
    "RESOLVE_CONFLICT_LOCAL": "SUCCESS",
    "RESOLVE_CONFLICT_LOCAL_QUEUED": "WARNING",
    "RESOLVE_CONFLICT_FAILED": "DANGER",
    "INVITE_MEMBER": "INFO",
    "UPDATE_MEMBER_ROLE": "INFO",
    "REMOVE_MEMBER": "WARNING",
    "SYNC_MANUAL": "SUCCESS",
    "SYNC_OFFLINE": "WARNING",
    "SYNC_FAILED": "DANGER",
    "SYNC_AUTH_REQUIRED": "WARNING",
}


def create_notification(
    user_id,
    title,
    message,
    category="INFO",
    entity_type="system",
    entity_uuid=None,
):
    """
    Store an in-app notification for the current local user.

    Notifications are local-first: they work even when the remote server is offline.
    """
    if not user_id:
        return None

    notification_uuid = str(uuid.uuid4())

    try:
        connection = get_local_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notification_uuid TEXT UNIQUE NOT NULL,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                category TEXT DEFAULT 'INFO',
                entity_type TEXT DEFAULT 'system',
                entity_uuid TEXT,
                is_read INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO notifications (
                notification_uuid, user_id, title, message, category,
                entity_type, entity_uuid, is_read, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                notification_uuid,
                user_id,
                title,
                message,
                str(category or "INFO").upper(),
                entity_type or "system",
                entity_uuid,
                current_timestamp(),
            ),
        )
        connection.commit()
        connection.close()
        return notification_uuid
    except Exception as error:
        print(f"Notification write failed: {error}")
        return None


def maybe_notify_activity(user_id, action, message, entity_type="system", entity_uuid=None):
    action_key = str(action or "").upper()
    title = NOTIFICATION_TITLES.get(action_key)
    if not title:
        return
    category = NOTIFICATION_CATEGORIES.get(action_key, "INFO")
    create_notification(
        user_id=user_id,
        title=title,
        message=message,
        category=category,
        entity_type=entity_type,
        entity_uuid=entity_uuid,
    )


def serialize_notification_row(row):
    return {
        "notification_uuid": row["notification_uuid"],
        "title": row["title"],
        "message": row["message"],
        "category": row["category"],
        "entity_type": row["entity_type"],
        "entity_uuid": row["entity_uuid"],
        "is_read": bool(row["is_read"]),
        "created_at": row["created_at"],
    }


def clean_file_name(file_name):
    """
    Keep uploaded attachment names safe for local storage.
    The original name is preserved in the database for display.
    """
    name = Path(file_name or "attachment").name.strip()
    if not name:
        name = "attachment"

    name = re.sub(r"[^A-Za-z0-9À-ÖØ-öø-ÿ._ ()'-]+", "_", name)
    name = name.strip(" ._")

    if not name:
        name = "attachment"

    return name[:180]


def decode_attachment_content(file_content):
    """
    Decode a browser FileReader data URL or a plain base64 string.
    This avoids requiring python-multipart for the v1 attachment feature.
    """
    if not file_content or not isinstance(file_content, str):
        raise HTTPException(status_code=400, detail="Attachment content is required.")

    content = file_content.strip()
    if content.startswith("data:") and "," in content:
        content = content.split(",", 1)[1]

    try:
        return base64.b64decode(content, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="Invalid attachment content.")


def get_attachment_folder(user_id, project_uuid):
    safe_user_id = clean_file_name(user_id)
    safe_project_uuid = clean_file_name(project_uuid)
    folder = UPLOAD_ROOT / safe_user_id / safe_project_uuid
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def log_activity(
    user_id,
    action,
    message,
    entity_type="system",
    entity_uuid=None,
    details=None,
):
    """
    Store a user-specific audit record.

    This is local-first. It writes into afrisync.db, so it works even when
    the remote server on port 8000 is offline.
    """
    try:
        connection = get_local_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO activity_logs (
                user_id, action, entity_type, entity_uuid,
                message, details, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                action,
                entity_type,
                entity_uuid,
                message,
                safe_json_dumps(details),
                current_timestamp(),
            ),
        )
        connection.commit()
        connection.close()

        maybe_notify_activity(
            user_id=user_id,
            action=action,
            message=message,
            entity_type=entity_type,
            entity_uuid=entity_uuid,
        )
    except Exception as error:
        print(f"Activity log write failed: {error}")


def record_sync_history(
    user_id,
    started_at,
    completed_at,
    status,
    total=0,
    successful=0,
    failed=0,
    conflicts=0,
    message=None,
    details=None,
):
    """
    Store one synchronization attempt.
    """
    try:
        connection = get_local_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO sync_history (
                user_id, started_at, completed_at, status,
                total, successful, failed, conflicts,
                message, details
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                started_at,
                completed_at,
                status,
                int(total or 0),
                int(successful or 0),
                int(failed or 0),
                int(conflicts or 0),
                message,
                safe_json_dumps(details),
            ),
        )
        connection.commit()
        connection.close()
    except Exception as error:
        print(f"Sync history write failed: {error}")


def serialize_activity_row(row):
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "action": row["action"],
        "entity_type": row["entity_type"],
        "entity_uuid": row["entity_uuid"],
        "message": row["message"],
        "details": safe_json_loads(row["details"]),
        "created_at": row["created_at"],
    }


def serialize_sync_history_row(row):
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "status": row["status"],
        "total": row["total"],
        "successful": row["successful"],
        "failed": row["failed"],
        "conflicts": row["conflicts"],
        "message": row["message"],
        "details": safe_json_loads(row["details"]),
    }


# ============================================================
# VALIDATION
# ============================================================

def validate_text(value, field_name):
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} cannot be empty.")
    if len(value) < 2:
        raise ValueError(f"{field_name} must contain at least 2 characters.")
    if not any(char.isalpha() for char in value):
        raise ValueError(f"{field_name} must contain letters.")
    return value


def validate_location(value):
    value = value.strip()
    if not value:
        raise ValueError("Location cannot be empty.")
    if len(value) < 2:
        raise ValueError("Location must contain at least 2 characters.")
    if any(char.isdigit() for char in value):
        raise ValueError("Location must use words, not numbers.")
    if not all(char.isalpha() or char.isspace() or char in "-'" for char in value):
        raise ValueError("Location may use letters, spaces, hyphens or apostrophes only.")
    if not any(char.isalpha() for char in value):
        raise ValueError("Location must contain letters.")
    return value


class AuthRequest(BaseModel):
    username: str
    password: str
    email: str | None = None
    full_name: str | None = None


class GoogleAuthRequest(BaseModel):
    credential: str

    @field_validator("credential")
    @classmethod
    def validate_credential(cls, value):
        value = value.strip()
        if len(value) < 20:
            raise ValueError("Google credential is invalid.")
        return value


class PasswordResetRequest(BaseModel):
    username: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Username must contain at least 3 characters.")
        return value


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

    @field_validator("token")
    @classmethod
    def validate_token(cls, value):
        value = value.strip()
        if len(value) < 20:
            raise ValueError("Reset token is invalid.")
        return value

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value):
        if len(value) < 6:
            raise ValueError("New password must contain at least 6 characters.")
        return value


class EmailVerificationRequest(BaseModel):
    username_or_email: str


class EmailVerificationConfirm(BaseModel):
    username_or_email: str
    code: str


class LocalProject(BaseModel):
    project_uuid: str
    name: str
    location: str
    progress: int

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        return validate_text(value, "Project name")

    @field_validator("location")
    @classmethod
    def validate_location_field(cls, value):
        return validate_location(value)

    @field_validator("progress")
    @classmethod
    def validate_progress(cls, value):
        if value < 0 or value > 100:
            raise ValueError("Progress must be between 0 and 100.")
        return value


class ProjectNoteRequest(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def validate_content(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Note cannot be empty.")
        if len(value) > 2000:
            raise ValueError("Note cannot be longer than 2,000 characters.")
        return value


class AttachmentUploadRequest(BaseModel):
    file_name: str
    file_type: str = "application/octet-stream"
    file_content: str

    @field_validator("file_name")
    @classmethod
    def validate_file_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("File name is required.")
        return value

    @field_validator("file_content")
    @classmethod
    def validate_file_content(cls, value):
        if not value or not value.strip():
            raise ValueError("File content is required.")
        return value




class ProjectInviteRequest(BaseModel):
    username: str
    role: str = "VIEWER"

    @field_validator("username")
    @classmethod
    def validate_invite_username(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Username must contain at least 3 characters.")
        return value

    @field_validator("role")
    @classmethod
    def validate_invite_role(cls, value):
        value = (value or "VIEWER").strip().upper()
        if value not in {"EDITOR", "VIEWER"}:
            raise ValueError("Role must be EDITOR or VIEWER.")
        return value


class ProjectRoleUpdateRequest(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, value):
        value = (value or "VIEWER").strip().upper()
        if value not in {"EDITOR", "VIEWER"}:
            raise ValueError("Role must be EDITOR or VIEWER.")
        return value

# ============================================================
# DASHBOARD
# ============================================================

@app.get("/", response_class=HTMLResponse)
def dashboard():
    with open("templates/dashboard.html", "r", encoding="utf-8") as file:
        return file.read()


# ============================================================
# REMOTE STATUS
# ============================================================

@app.get("/remote-status")
def remote_status():
    online = is_server_available()
    return {
        "online": online,
        "status": "online" if online else "offline",
    }


# ============================================================
# REGISTER / LOGIN
# ============================================================

@app.post("/password-reset/request")
def request_password_reset(payload: PasswordResetRequest):
    try:
        response = requests.post(
            f"{REMOTE_SERVER}/password-reset/request",
            json={"username": payload.username.strip()},
            timeout=10,
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=503,
            detail="Password reset requires the AfriSync remote server to be online.",
        )

    try:
        data = response.json()
    except ValueError:
        data = {"detail": "Invalid response from AfriSync server."}

    if not response.ok:
        raise HTTPException(
            status_code=response.status_code,
            detail=data.get("detail", "Password reset request failed."),
        )

    return data


@app.post("/password-reset/confirm")
def confirm_password_reset(payload: PasswordResetConfirm):
    try:
        response = requests.post(
            f"{REMOTE_SERVER}/password-reset/confirm",
            json={
                "token": payload.token.strip(),
                "new_password": payload.new_password,
            },
            timeout=10,
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=503,
            detail="Password reset requires the AfriSync remote server to be online.",
        )

    try:
        data = response.json()
    except ValueError:
        data = {"detail": "Invalid response from AfriSync server."}

    if not response.ok:
        raise HTTPException(
            status_code=response.status_code,
            detail=data.get("detail", "Password reset failed."),
        )

    if data.get("user_id") and data.get("username"):
        cache_user(
            data["user_id"],
            data["username"],
            payload.new_password,
        )
        log_activity(
            data["user_id"],
            "PASSWORD_RESET",
            "Password was reset and the local offline cache was updated.",
            entity_type="user",
            entity_uuid=data["user_id"],
            details={"username": data["username"]},
        )

    return data


@app.get("/auth/google/config")
def get_google_auth_config():
    try:
        response = requests.get(
            f"{REMOTE_SERVER}/auth/google/config",
            timeout=8,
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=503,
            detail="Google login configuration requires the AfriSync remote server to be online.",
        )

    try:
        data = response.json()
    except ValueError:
        data = {"detail": "Invalid response from AfriSync server."}

    if not response.ok:
        raise HTTPException(
            status_code=response.status_code,
            detail=data.get("detail", "Could not read Google login configuration."),
        )
    return data


@app.post("/auth/google")
def login_with_google(payload: GoogleAuthRequest):
    try:
        response = requests.post(
            f"{REMOTE_SERVER}/auth/google",
            json={"credential": payload.credential.strip()},
            timeout=15,
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=503,
            detail="Google login requires the AfriSync remote server and internet connection to be online.",
        )

    try:
        data = response.json()
    except ValueError:
        data = {"detail": "Invalid response from AfriSync server."}

    if not response.ok:
        raise HTTPException(
            status_code=response.status_code,
            detail=data.get("detail", "Google login failed."),
        )

    cache_user(
        data["user_id"],
        data["username"],
        secrets.token_urlsafe(48),
        email=data.get("email"),
        full_name=data.get("full_name"),
        email_verified=True,
        google_sub=data.get("google_sub"),
        auth_provider=data.get("auth_provider") or "google",
        avatar_url=data.get("avatar_url"),
    )
    cache_remote_sync_token(
        data["user_id"],
        data["username"],
        data.get("sync_token"),
        data.get("sync_token_expires_at"),
    )
    log_activity(
        data["user_id"],
        "GOOGLE_LOGIN",
        "User logged in with Google.",
        entity_type="user",
        entity_uuid=data["user_id"],
        details={"username": data.get("username"), "email": data.get("email")},
    )
    data["offline"] = False
    return authenticated_response(data, data["user_id"], data["username"])


@app.post("/register")
def register_user(user: AuthRequest):
    payload = {
        "username": user.username.strip(),
        "password": user.password,
        "email": (user.email or "").strip(),
        "full_name": (user.full_name or "").strip(),
    }
    try:
        response = requests.post(
            f"{REMOTE_SERVER}/register",
            json=payload,
            timeout=15,
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=503,
            detail="Registration requires a connection to the AfriSync server.",
        )

    try:
        data = response.json()
    except ValueError:
        data = {"detail": "Invalid response from AfriSync server."}

    if not response.ok:
        raise HTTPException(
            status_code=response.status_code,
            detail=data.get("detail", "Registration failed."),
        )

    if data.get("verification_required"):
        log_activity(
            data.get("user_id"),
            "REGISTER_PENDING_VERIFICATION",
            "Account registered and is waiting for email verification.",
            entity_type="user",
            entity_uuid=data.get("user_id"),
            details={"username": data.get("username"), "email": data.get("email")},
        )
        return data

    cache_user(
        data["user_id"],
        data["username"],
        user.password,
        email=data.get("email"),
        full_name=payload.get("full_name"),
        email_verified=data.get("email_verified", True),
    )
    cache_remote_sync_token(
        data["user_id"],
        data["username"],
        data.get("sync_token"),
        data.get("sync_token_expires_at"),
    )

    log_activity(
        data["user_id"],
        "REGISTER",
        "Account registered and cached on this device.",
        entity_type="user",
        entity_uuid=data["user_id"],
        details={"username": data["username"], "email": data.get("email")},
    )

    return public_login_payload(data)


@app.get("/email-delivery/status")
def get_local_email_delivery_status():
    try:
        response = requests.get(
            f"{REMOTE_SERVER}/email-delivery/status",
            timeout=8,
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=503,
            detail="Email delivery status requires the AfriSync remote server to be online.",
        )

    try:
        data = response.json()
    except ValueError:
        data = {"detail": "Invalid response from AfriSync server."}

    if not response.ok:
        raise HTTPException(
            status_code=response.status_code,
            detail=data.get("detail", "Could not read email delivery status."),
        )
    return data


@app.post("/email-verification/resend")
def resend_email_verification(payload: EmailVerificationRequest):
    try:
        response = requests.post(
            f"{REMOTE_SERVER}/email-verification/resend",
            json={"username_or_email": payload.username_or_email.strip()},
            timeout=15,
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=503,
            detail="Email verification requires the AfriSync remote server to be online.",
        )

    try:
        data = response.json()
    except ValueError:
        data = {"detail": "Invalid response from AfriSync server."}

    if not response.ok:
        raise HTTPException(
            status_code=response.status_code,
            detail=data.get("detail", "Could not resend verification code."),
        )
    return data


@app.post("/email-verification/confirm")
def confirm_email_verification(payload: EmailVerificationConfirm):
    try:
        response = requests.post(
            f"{REMOTE_SERVER}/email-verification/confirm",
            json={
                "username_or_email": payload.username_or_email.strip(),
                "code": payload.code.strip(),
            },
            timeout=15,
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=503,
            detail="Email verification requires the AfriSync remote server to be online.",
        )

    try:
        data = response.json()
    except ValueError:
        data = {"detail": "Invalid response from AfriSync server."}

    if not response.ok:
        raise HTTPException(
            status_code=response.status_code,
            detail=data.get("detail", "Email verification failed."),
        )

    if data.get("user_id") and data.get("username"):
        cache_remote_sync_token(
            data["user_id"],
            data["username"],
            data.get("sync_token"),
            data.get("sync_token_expires_at"),
        )
        log_activity(
            data["user_id"],
            "EMAIL_VERIFIED",
            "Email address verified successfully.",
            entity_type="user",
            entity_uuid=data["user_id"],
            details={"username": data.get("username"), "email": data.get("email")},
        )

    return public_login_payload(data)


@app.post("/login")
def login_user(user: AuthRequest):
    username = user.username.strip()

    try:
        response = requests.post(
            f"{REMOTE_SERVER}/login",
            json={
                "username": username,
                "password": user.password,
            },
            timeout=8,
        )
    except requests.RequestException:
        cached = offline_login(username, user.password)
        if cached:
            log_activity(
                cached["user_id"],
                "LOGIN_OFFLINE",
                "User logged in using cached offline credentials.",
                entity_type="user",
                entity_uuid=cached["user_id"],
                details={"username": cached["username"]},
            )
            return authenticated_response(
                cached,
                cached["user_id"],
                cached["username"],
            )
        raise HTTPException(
            status_code=503,
            detail=(
                "AfriSync is offline and this account has not been cached "
                "on this device. Connect once and log in successfully first."
            ),
        )

    try:
        data = response.json()
    except ValueError:
        data = {"detail": "Invalid response from AfriSync server."}

    if not response.ok:
        raise HTTPException(
            status_code=response.status_code,
            detail=data.get("detail", "Login failed."),
        )

    cache_user(
        data["user_id"],
        data["username"],
        user.password,
        email=data.get("email"),
        full_name=data.get("full_name"),
        email_verified=data.get("email_verified", True),
    )
    cache_remote_sync_token(
        data["user_id"],
        data["username"],
        data.get("sync_token"),
        data.get("sync_token_expires_at"),
    )

    log_activity(
        data["user_id"],
        "LOGIN_ONLINE",
        "User logged in through the remote server.",
        entity_type="user",
        entity_uuid=data["user_id"],
        details={"username": data["username"]},
    )

    data["offline"] = False
    return authenticated_response(
        data,
        data["user_id"],
        data["username"],
    )


@app.get("/session")
def session_info(request: Request):
    session = get_session(request)
    return {
        "authenticated": True,
        "username": session["username"],
        "remote_token_cached": has_remote_sync_token(session["user_id"]),
    }


@app.post("/session/refresh")
def refresh_session(request: Request):
    session = get_session(request)
    require_csrf(request, session)
    return authenticated_response(
        {"message": "Session refreshed."},
        session["user_id"],
        session["username"],
    )


@app.post("/logout")
def logout_user(request: Request):
    session = get_session(request)
    require_csrf(request, session)
    log_activity(
        session["user_id"],
        "LOGOUT",
        "User logged out of AfriSync on this device.",
        entity_type="user",
        entity_uuid=session["user_id"],
        details={"username": session["username"]},
    )
    clear_session(request)
    response = JSONResponse({"message": "Logged out successfully."})
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response



# ============================================================
# LOCAL TEAM PERMISSIONS
# ============================================================

TEAM_ROLES = {"OWNER", "EDITOR", "VIEWER"}
ROLE_LEVELS = {"VIEWER": 1, "EDITOR": 2, "OWNER": 3}


def normalize_role(role):
    value = (role or "VIEWER").strip().upper()
    if value not in TEAM_ROLES:
        return "VIEWER"
    return value


def project_permission_payload(role, owner_user_id, owner_username=None):
    role = normalize_role(role)
    is_owner = role == "OWNER"
    is_editor_or_owner = ROLE_LEVELS[role] >= ROLE_LEVELS["EDITOR"]
    return {
        "access_role": role,
        "owner_user_id": owner_user_id,
        "owner_username": owner_username or owner_user_id,
        "is_owner": is_owner,
        "is_shared": not is_owner,
        # Owners and invited Editors can update and delete the shared project.
        "can_edit_project": is_editor_or_owner,
        "can_delete_project": is_editor_or_owner,
        # Owners and Editors can contribute notes and attachments.
        "can_add_content": is_editor_or_owner,
        # Only the Owner can invite/remove members or change roles.
        "can_manage_members": is_owner,
    }


def get_local_project_access(project_uuid, user_id, minimum_role="VIEWER"):
    connection = get_local_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT p.project_uuid, p.user_id, p.name, p.location, p.progress,
               p.sync_status, p.is_deleted, p.version, p.updated_at,
               CASE
                   WHEN p.user_id = ? THEN 'OWNER'
                   ELSE UPPER(COALESCE(pm.role, ''))
               END AS access_role,
               pm.member_username,
               pm.owner_user_id
        FROM projects p
        LEFT JOIN project_members pm
               ON pm.project_uuid = p.project_uuid
              AND pm.member_user_id = ?
              AND COALESCE(pm.is_deleted, 0) = 0
        WHERE p.project_uuid = ?
          AND COALESCE(p.is_deleted, 0) = 0
          AND (p.user_id = ? OR pm.member_user_id IS NOT NULL)
        """,
        (user_id, user_id, project_uuid, user_id),
    )
    project = cursor.fetchone()
    connection.close()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found or not shared with you.")

    role = normalize_role(project["access_role"])
    if ROLE_LEVELS[role] < ROLE_LEVELS[minimum_role]:
        raise HTTPException(status_code=403, detail=f"{minimum_role.title()} access is required for this action.")

    data = dict(project)
    data.update(project_permission_payload(role, project["user_id"]))
    return data


def get_project_owned_by_user(project_uuid, user_id):
    # Backward-compatible name used by earlier code. It now means:
    # the user can view the project because they own it or it was shared with them.
    return get_local_project_access(project_uuid, user_id, "VIEWER")


def cache_project_member(member):
    now = current_timestamp()
    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO project_members (
            project_uuid, owner_user_id, member_user_id, member_username,
            role, is_deleted, invited_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(project_uuid, member_user_id) DO UPDATE SET
            owner_user_id = excluded.owner_user_id,
            member_username = excluded.member_username,
            role = excluded.role,
            is_deleted = excluded.is_deleted,
            invited_at = COALESCE(project_members.invited_at, excluded.invited_at),
            updated_at = excluded.updated_at
        """,
        (
            member.get("project_uuid"),
            member.get("owner_user_id"),
            member.get("member_user_id"),
            member.get("member_username") or member.get("member_user_id"),
            normalize_role(member.get("role")),
            int(member.get("is_deleted") or 0),
            member.get("invited_at") or now,
            member.get("updated_at") or now,
        ),
    )
    connection.commit()
    connection.close()

# ============================================================
# LOCAL PROJECT LIST
# ============================================================

@app.get("/projects")
def get_projects(request: Request):
    session = get_session(request)
    user_id = session["user_id"]
    connection = get_local_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            p.project_uuid,
            p.user_id,
            p.name,
            p.location,
            p.progress,
            p.sync_status,
            p.is_deleted,
            p.deleted_at,
            p.version,
            p.updated_at,
            p.last_sync_error,
            p.last_synced_at,
            CASE
                WHEN p.user_id = ? THEN 'OWNER'
                ELSE UPPER(COALESCE(pm.role, 'VIEWER'))
            END AS access_role,
            CASE WHEN p.user_id = ? THEN 1 ELSE 0 END AS is_owner,
            CASE WHEN p.user_id = ? THEN 0 ELSE 1 END AS is_shared,
            COALESCE(owner.username, p.user_id) AS owner_username,
            (
                SELECT COUNT(*)
                FROM project_notes n
                WHERE n.project_uuid = p.project_uuid
                  AND COALESCE(n.is_deleted, 0) = 0
            ) AS note_count
        FROM projects p
        LEFT JOIN project_members pm
               ON pm.project_uuid = p.project_uuid
              AND pm.member_user_id = ?
              AND COALESCE(pm.is_deleted, 0) = 0
        LEFT JOIN local_users owner ON owner.user_id = p.user_id
        WHERE (p.user_id = ? OR pm.member_user_id IS NOT NULL)
          AND COALESCE(p.is_deleted, 0) = 0
        ORDER BY COALESCE(p.updated_at, '') DESC, p.id DESC
        """,
        (user_id, user_id, user_id, user_id, user_id),
    )

    rows = []
    for row in cursor.fetchall():
        project = dict(row)
        role = normalize_role(project.get("access_role"))
        project.update(project_permission_payload(role, project.get("user_id"), project.get("owner_username")))
        rows.append(project)
    connection.close()

    return rows


# ============================================================
# LOCAL CREATE / EDIT
# ============================================================

@app.post("/projects")
def save_local_project(project: LocalProject, request: Request):
    session = get_session(request)
    require_csrf(request, session)
    user_id = session["user_id"]
    connection = get_local_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT project_uuid, user_id, sync_status, version
        FROM projects
        WHERE project_uuid = ?
        """,
        (project.project_uuid,),
    )
    existing = cursor.fetchone()
    now = current_timestamp()

    if not existing:
        cursor.execute(
            """
            INSERT INTO projects (
                project_uuid,
                user_id,
                name,
                location,
                progress,
                sync_status,
                sync_attempts,
                last_sync_error,
                is_deleted,
                deleted_at,
                version,
                updated_at,
                conflict_data
            )
            VALUES (?, ?, ?, ?, ?, 'PENDING', 0, NULL, 0, NULL, 0, ?, NULL)
            """,
            (
                project.project_uuid,
                user_id,
                project.name,
                project.location,
                project.progress,
                now,
            ),
        )
        connection.commit()
        connection.close()
        log_activity(
            user_id,
            "CREATE_PROJECT",
            f"Created project: {project.name}.",
            entity_type="project",
            entity_uuid=project.project_uuid,
            details={
                "name": project.name,
                "location": project.location,
                "progress": project.progress,
                "sync_status": "PENDING",
            },
        )
        return {
            "message": "Project saved locally and queued for synchronization.",
            "project_uuid": project.project_uuid,
            "status": "PENDING",
            "offline_first": True,
        }

    access = get_local_project_access(project.project_uuid, user_id, "EDITOR")
    owner_user_id = access["owner_user_id"]

    if existing["sync_status"] == "CONFLICT":
        connection.close()
        raise HTTPException(
            status_code=409,
            detail="Resolve this project's synchronization conflict before editing it.",
        )

    cursor.execute(
        """
        UPDATE projects
        SET
            name = ?,
            location = ?,
            progress = ?,
            sync_status = 'PENDING',
            last_sync_error = NULL,
            is_deleted = 0,
            deleted_at = NULL,
            updated_at = ?,
            conflict_data = NULL
        WHERE project_uuid = ?
          AND user_id = ?
        """,
        (
            project.name,
            project.location,
            project.progress,
            now,
            project.project_uuid,
            owner_user_id,
        ),
    )

    connection.commit()
    connection.close()

    log_activity(
        user_id,
        "UPDATE_PROJECT",
        f"Updated project: {project.name}.",
        entity_type="project",
        entity_uuid=project.project_uuid,
        details={
            "name": project.name,
            "location": project.location,
            "progress": project.progress,
            "sync_status": "PENDING",
        },
    )

    return {
        "message": "Project updated locally and queued for synchronization.",
        "project_uuid": project.project_uuid,
        "status": "PENDING",
        "offline_first": True,
    }


# ============================================================
# LOCAL DELETE TOMBSTONE
# ============================================================

@app.delete("/projects/{project_uuid}")
def delete_local_project(project_uuid: str, request: Request):
    session = get_session(request)
    require_csrf(request, session)
    user_id = session["user_id"]
    connection = get_local_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT project_uuid, user_id, name, sync_status
        FROM projects
        WHERE project_uuid = ?
        """,
        (project_uuid,),
    )
    existing = cursor.fetchone()

    if not existing:
        connection.close()
        raise HTTPException(status_code=404, detail="Project not found.")

    access = get_local_project_access(project_uuid, user_id, "EDITOR")
    owner_user_id = access["owner_user_id"]

    if existing["sync_status"] == "CONFLICT":
        connection.close()
        raise HTTPException(
            status_code=409,
            detail="Resolve this project's synchronization conflict before deleting it.",
        )

    now = current_timestamp()

    cursor.execute(
        """
        UPDATE projects
        SET
            is_deleted = 1,
            deleted_at = ?,
            updated_at = ?,
            sync_status = 'PENDING',
            last_sync_error = NULL,
            conflict_data = NULL
        WHERE project_uuid = ?
          AND user_id = ?
        """,
        (
            now,
            now,
            project_uuid,
            owner_user_id,
        ),
    )

    project_name = existing["name"]
    connection.commit()
    connection.close()

    log_activity(
        user_id,
        "DELETE_PROJECT",
        f"Deleted project: {project_name}.",
        entity_type="project",
        entity_uuid=project_uuid,
        details={
            "name": project_name,
            "deleted_at": now,
            "sync_status": "PENDING",
        },
    )

    return {
        "message": "Project deleted locally and tombstone queued for synchronization.",
        "project_uuid": project_uuid,
        "status": "PENDING",
        "deleted_at": now,
    }


# ============================================================
# PROJECT NOTES
# ============================================================

@app.get("/projects/{project_uuid}/notes")
def get_project_notes(project_uuid: str, request: Request):
    session = get_session(request)
    user_id = session["user_id"]
    get_project_owned_by_user(project_uuid, user_id)

    connection = get_local_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT note_uuid, project_uuid, user_id, content, sync_status,
               is_deleted, deleted_at, created_at, updated_at,
               version, last_sync_error, last_synced_at
        FROM project_notes
        WHERE project_uuid = ?
          AND COALESCE(is_deleted, 0) = 0
        ORDER BY datetime(updated_at) DESC, id DESC
        """,
        (project_uuid,),
    )
    notes = [dict(row) for row in cursor.fetchall()]
    connection.close()
    return notes


@app.post("/projects/{project_uuid}/notes")
def create_project_note(project_uuid: str, note: ProjectNoteRequest, request: Request):
    session = get_session(request)
    require_csrf(request, session)
    user_id = session["user_id"]
    project = get_local_project_access(project_uuid, user_id, "EDITOR")

    note_uuid = str(uuid.uuid4())
    now = current_timestamp()

    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO project_notes (
            note_uuid, project_uuid, user_id, content,
            sync_status, is_deleted, deleted_at, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, 'PENDING', 0, NULL, ?, ?)
        """,
        (note_uuid, project_uuid, user_id, note.content, now, now),
    )
    connection.commit()
    connection.close()

    log_activity(
        user_id,
        "CREATE_NOTE",
        f"Added a note to project: {project['name']}.",
        entity_type="note",
        entity_uuid=note_uuid,
        details={
            "project_uuid": project_uuid,
            "project_name": project["name"],
        },
    )

    return {
        "message": "Note added successfully.",
        "note_uuid": note_uuid,
        "project_uuid": project_uuid,
        "sync_status": "PENDING",
        "created_at": now,
        "updated_at": now,
    }


@app.put("/projects/{project_uuid}/notes/{note_uuid}")
def update_project_note(
    project_uuid: str,
    note_uuid: str,
    note: ProjectNoteRequest,
    request: Request,
):
    session = get_session(request)
    require_csrf(request, session)
    user_id = session["user_id"]
    project = get_local_project_access(project_uuid, user_id, "EDITOR")
    now = current_timestamp()

    connection = get_local_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT note_uuid, user_id, project_uuid, is_deleted
        FROM project_notes
        WHERE note_uuid = ?
          AND project_uuid = ?
        """,
        (note_uuid, project_uuid),
    )
    existing = cursor.fetchone()

    if not existing or int(existing["is_deleted"] or 0) == 1:
        connection.close()
        raise HTTPException(status_code=404, detail="Note not found.")

    if existing["user_id"] != user_id:
        connection.close()
        raise HTTPException(status_code=403, detail="You can only edit or delete notes that you created.")

    cursor.execute(
        """
        UPDATE project_notes
        SET content = ?,
            sync_status = 'PENDING',
            updated_at = ?
        WHERE note_uuid = ?
          AND project_uuid = ?
        """,
        (note.content, now, note_uuid, project_uuid),
    )
    connection.commit()
    connection.close()

    log_activity(
        user_id,
        "UPDATE_NOTE",
        f"Updated a note on project: {project['name']}.",
        entity_type="note",
        entity_uuid=note_uuid,
        details={
            "project_uuid": project_uuid,
            "project_name": project["name"],
        },
    )

    return {
        "message": "Note updated successfully.",
        "note_uuid": note_uuid,
        "project_uuid": project_uuid,
        "sync_status": "PENDING",
        "updated_at": now,
    }


@app.delete("/projects/{project_uuid}/notes/{note_uuid}")
def delete_project_note(project_uuid: str, note_uuid: str, request: Request):
    session = get_session(request)
    require_csrf(request, session)
    user_id = session["user_id"]
    project = get_local_project_access(project_uuid, user_id, "EDITOR")
    now = current_timestamp()

    connection = get_local_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT note_uuid, user_id, project_uuid, is_deleted
        FROM project_notes
        WHERE note_uuid = ?
          AND project_uuid = ?
        """,
        (note_uuid, project_uuid),
    )
    existing = cursor.fetchone()

    if not existing or int(existing["is_deleted"] or 0) == 1:
        connection.close()
        raise HTTPException(status_code=404, detail="Note not found.")

    if existing["user_id"] != user_id:
        connection.close()
        raise HTTPException(status_code=403, detail="You can only edit or delete notes that you created.")

    cursor.execute(
        """
        UPDATE project_notes
        SET is_deleted = 1,
            deleted_at = ?,
            sync_status = 'PENDING',
            updated_at = ?
        WHERE note_uuid = ?
          AND project_uuid = ?
        """,
        (now, now, note_uuid, project_uuid),
    )
    connection.commit()
    connection.close()

    log_activity(
        user_id,
        "DELETE_NOTE",
        f"Deleted a note from project: {project['name']}.",
        entity_type="note",
        entity_uuid=note_uuid,
        details={
            "project_uuid": project_uuid,
            "project_name": project["name"],
            "deleted_at": now,
        },
    )

    return {
        "message": "Note deleted successfully.",
        "note_uuid": note_uuid,
        "project_uuid": project_uuid,
        "deleted_at": now,
    }



# ============================================================
# PROJECT ATTACHMENTS
# ============================================================

@app.get("/projects/{project_uuid}/attachments")
def get_project_attachments(project_uuid: str, request: Request):
    session = get_session(request)
    user_id = session["user_id"]
    get_project_owned_by_user(project_uuid, user_id)

    connection = get_local_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT attachment_uuid, project_uuid, user_id,
               original_file_name AS file_name,
               stored_file_name, file_type, file_size,
               sync_status, is_deleted, deleted_at,
               created_at, updated_at, sync_attempts,
               last_sync_attempt, last_sync_error,
               last_synced_at, version, conflict_data
        FROM project_attachments
        WHERE project_uuid = ?
          AND COALESCE(is_deleted, 0) = 0
        ORDER BY datetime(updated_at) DESC, id DESC
        """,
        (project_uuid,),
    )
    attachments = [dict(row) for row in cursor.fetchall()]
    connection.close()
    return attachments


@app.post("/projects/{project_uuid}/attachments")
def upload_project_attachment(
    project_uuid: str,
    attachment: AttachmentUploadRequest,
    request: Request,
):
    session = get_session(request)
    require_csrf(request, session)
    user_id = session["user_id"]
    project = get_local_project_access(project_uuid, user_id, "EDITOR")

    file_bytes = decode_attachment_content(attachment.file_content)
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Attachment file is empty.")
    if len(file_bytes) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Attachment is too large. Maximum allowed size is 10 MB for this version.",
        )

    attachment_uuid = str(uuid.uuid4())
    original_file_name = clean_file_name(attachment.file_name)
    stored_file_name = f"{attachment_uuid}_{original_file_name}"
    attachment_folder = get_attachment_folder(user_id, project_uuid)
    file_path = attachment_folder / stored_file_name

    try:
        file_path.write_bytes(file_bytes)
    except OSError as error:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to save attachment locally: {error}",
        )

    now = current_timestamp()
    file_type = (attachment.file_type or "application/octet-stream").strip()
    if not file_type:
        file_type = "application/octet-stream"

    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO project_attachments (
            attachment_uuid, project_uuid, user_id,
            original_file_name, stored_file_name, file_path,
            file_type, file_size, sync_status, is_deleted,
            deleted_at, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', 0, NULL, ?, ?)
        """,
        (
            attachment_uuid,
            project_uuid,
            user_id,
            original_file_name,
            stored_file_name,
            str(file_path),
            file_type,
            len(file_bytes),
            now,
            now,
        ),
    )
    connection.commit()
    connection.close()

    log_activity(
        user_id,
        "UPLOAD_ATTACHMENT",
        f"Uploaded attachment '{original_file_name}' to project: {project['name']}.",
        entity_type="attachment",
        entity_uuid=attachment_uuid,
        details={
            "project_uuid": project_uuid,
            "project_name": project["name"],
            "file_name": original_file_name,
            "file_type": file_type,
            "file_size": len(file_bytes),
            "sync_status": "PENDING",
        },
    )

    return {
        "message": "Attachment uploaded locally and queued for synchronization.",
        "attachment_uuid": attachment_uuid,
        "project_uuid": project_uuid,
        "file_name": original_file_name,
        "file_type": file_type,
        "file_size": len(file_bytes),
        "sync_status": "PENDING",
        "created_at": now,
        "updated_at": now,
        "open_url": f"/attachments/{attachment_uuid}/open",
    }


@app.get("/attachments/{attachment_uuid}/open")
def open_project_attachment(attachment_uuid: str, request: Request):
    session = get_session(request)
    user_id = session["user_id"]

    connection = get_local_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT attachment_uuid, project_uuid, user_id,
               original_file_name, file_path, file_type, is_deleted
        FROM project_attachments
        WHERE attachment_uuid = ?
        """,
        (attachment_uuid,),
    )
    row = cursor.fetchone()
    connection.close()

    if not row or int(row["is_deleted"] or 0) == 1:
        raise HTTPException(status_code=404, detail="Attachment not found.")

    get_local_project_access(row["project_uuid"], user_id, "VIEWER")

    file_path = Path(row["file_path"])
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Attachment file is missing from local storage.")

    return FileResponse(
        path=str(file_path),
        media_type=row["file_type"] or "application/octet-stream",
        filename=row["original_file_name"],
    )


@app.delete("/projects/{project_uuid}/attachments/{attachment_uuid}")
def delete_project_attachment(project_uuid: str, attachment_uuid: str, request: Request):
    session = get_session(request)
    require_csrf(request, session)
    user_id = session["user_id"]
    project = get_local_project_access(project_uuid, user_id, "EDITOR")
    now = current_timestamp()

    connection = get_local_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT attachment_uuid, user_id, project_uuid,
               original_file_name, file_path, is_deleted
        FROM project_attachments
        WHERE attachment_uuid = ?
          AND project_uuid = ?
        """,
        (attachment_uuid, project_uuid),
    )
    row = cursor.fetchone()

    if not row or int(row["is_deleted"] or 0) == 1:
        connection.close()
        raise HTTPException(status_code=404, detail="Attachment not found.")

    if row["user_id"] != user_id:
        connection.close()
        raise HTTPException(status_code=403, detail="You can only delete attachments that you uploaded.")

    cursor.execute(
        """
        UPDATE project_attachments
        SET is_deleted = 1,
            deleted_at = ?,
            updated_at = ?,
            sync_status = 'PENDING'
        WHERE attachment_uuid = ?
          AND project_uuid = ?
        """,
        (now, now, attachment_uuid, project_uuid),
    )
    connection.commit()
    connection.close()

    try:
        saved_path = Path(row["file_path"])
        if saved_path.is_file():
            saved_path.unlink()
    except OSError as error:
        print(f"Attachment file delete failed: {error}")

    log_activity(
        user_id,
        "DELETE_ATTACHMENT",
        f"Deleted attachment '{row['original_file_name']}' from project: {project['name']}.",
        entity_type="attachment",
        entity_uuid=attachment_uuid,
        details={
            "project_uuid": project_uuid,
            "project_name": project["name"],
            "file_name": row["original_file_name"],
            "deleted_at": now,
        },
    )

    return {
        "message": "Attachment deleted locally.",
        "attachment_uuid": attachment_uuid,
        "project_uuid": project_uuid,
        "deleted_at": now,
    }


# ============================================================
# CONFLICT HELPERS
# ============================================================

def parse_conflict_data(raw_value):
    if not raw_value:
        return {}
    try:
        data = json.loads(raw_value)
        return data if isinstance(data, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def serialize_local_conflict(row):
    conflict = parse_conflict_data(row["conflict_data"])
    server_project = conflict.get("server_project") or {}
    return {
        "project_uuid": row["project_uuid"],
        "user_id": row["user_id"],
        "status": row["sync_status"],
        "message": conflict.get("message", "Version conflict detected."),
        "local_project": {
            "project_uuid": row["project_uuid"],
            "user_id": row["user_id"],
            "name": row["name"],
            "location": row["location"],
            "progress": row["progress"],
            "is_deleted": int(row["is_deleted"] or 0),
            "deleted_at": row["deleted_at"],
            "version": int(row["version"] or 0),
            "updated_at": row["updated_at"],
        },
        "server_project": server_project,
    }


def get_local_conflict_row(project_uuid, user_id):
    connection = get_local_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT project_uuid, user_id, name, location, progress,
               sync_status, is_deleted, deleted_at, version,
               updated_at, conflict_data
        FROM projects
        WHERE project_uuid = ?
          AND user_id = ?
          AND sync_status = 'CONFLICT'
        """,
        (project_uuid, user_id),
    )
    row = cursor.fetchone()
    connection.close()
    return row


@app.get("/conflicts")
def get_conflicts(request: Request):
    session = get_session(request)
    user_id = session["user_id"]
    connection = get_local_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT project_uuid, user_id, name, location, progress,
               sync_status, is_deleted, deleted_at, version,
               updated_at, conflict_data
        FROM projects
        WHERE user_id = ?
          AND sync_status = 'CONFLICT'
        ORDER BY COALESCE(updated_at, '') DESC, id DESC
        """,
        (user_id,),
    )
    rows = cursor.fetchall()
    connection.close()
    return [serialize_local_conflict(row) for row in rows]


@app.get("/conflicts/{project_uuid}")
def get_conflict(project_uuid: str, request: Request):
    session = get_session(request)
    user_id = session["user_id"]
    row = get_local_conflict_row(project_uuid, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Conflict not found.")
    return serialize_local_conflict(row)


@app.post("/conflicts/{project_uuid}/use-server")
def resolve_conflict_use_server(project_uuid: str, request: Request):
    session = get_session(request)
    require_csrf(request, session)
    user_id = session["user_id"]
    row = get_local_conflict_row(project_uuid, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Conflict not found.")

    conflict = parse_conflict_data(row["conflict_data"])
    server_project = conflict.get("server_project")

    if not isinstance(server_project, dict) or not server_project:
        raise HTTPException(
            status_code=409,
            detail="The stored conflict does not contain a server version.",
        )

    if server_project.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Conflict ownership mismatch.")

    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE projects
        SET
            name = ?,
            location = ?,
            progress = ?,
            is_deleted = ?,
            deleted_at = ?,
            version = ?,
            updated_at = ?,
            sync_status = 'SYNCED',
            last_sync_error = NULL,
            last_synced_at = ?,
            conflict_data = NULL
        WHERE project_uuid = ?
          AND user_id = ?
        """,
        (
            server_project.get("name", row["name"]),
            server_project.get("location", row["location"]),
            int(server_project.get("progress", row["progress"])),
            int(server_project.get("is_deleted", 0)),
            server_project.get("deleted_at"),
            int(server_project.get("version", row["version"] or 0)),
            server_project.get("updated_at") or current_timestamp(),
            current_timestamp(),
            project_uuid,
            user_id,
        ),
    )
    connection.commit()
    connection.close()

    log_activity(
        user_id,
        "RESOLVE_CONFLICT_SERVER",
        f"Conflict resolved with server version: {server_project.get('name', project_uuid)}.",
        entity_type="project",
        entity_uuid=project_uuid,
        details={"resolution": "server", "server_project": server_project},
    )

    return {
        "message": "Conflict resolved using the server version.",
        "project_uuid": project_uuid,
        "resolution": "server",
    }


@app.post("/conflicts/{project_uuid}/keep-local")
def resolve_conflict_keep_local(project_uuid: str, request: Request):
    session = get_session(request)
    require_csrf(request, session)
    user_id = session["user_id"]
    row = get_local_conflict_row(project_uuid, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Conflict not found.")

    conflict = parse_conflict_data(row["conflict_data"])
    server_project = conflict.get("server_project")

    if not isinstance(server_project, dict) or not server_project:
        raise HTTPException(
            status_code=409,
            detail="The stored conflict does not contain a server version.",
        )

    if server_project.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Conflict ownership mismatch.")

    server_version = int(server_project.get("version", row["version"] or 0))

    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE projects
        SET
            version = ?,
            sync_status = 'PENDING',
            last_sync_error = NULL,
            conflict_data = NULL,
            updated_at = ?
        WHERE project_uuid = ?
          AND user_id = ?
        """,
        (
            server_version,
            current_timestamp(),
            project_uuid,
            user_id,
        ),
    )
    connection.commit()
    connection.close()

    if not is_server_available():
        log_activity(
            user_id,
            "RESOLVE_CONFLICT_LOCAL_QUEUED",
            f"Kept local version and queued project for sync: {row['name']}.",
            entity_type="project",
            entity_uuid=project_uuid,
            details={"resolution": "local_queued", "server_version": server_version},
        )
        return {
            "message": (
                "Your local version was kept and queued. "
                "It will synchronize when the server is available."
            ),
            "project_uuid": project_uuid,
            "resolution": "queued",
        }

    sync_started_at = current_timestamp()
    sync_result = synchronize_pending_projects(user_id)
    sync_completed_at = current_timestamp()
    record_sync_history(
        user_id,
        sync_started_at,
        sync_completed_at,
        "completed",
        total=sync_result.get("total", 0),
        successful=sync_result.get("successful", 0),
        failed=sync_result.get("failed", 0),
        conflicts=sync_result.get("conflicts", 0),
        message="Conflict keep-local synchronization completed.",
        details=sync_result,
    )

    refreshed = get_local_conflict_row(project_uuid, user_id)
    if refreshed:
        log_activity(
            user_id,
            "RESOLVE_CONFLICT_FAILED",
            f"Conflict remained unresolved after trying to keep local version: {row['name']}.",
            entity_type="project",
            entity_uuid=project_uuid,
            details={"resolution": "conflict", "sync": sync_result},
        )
        return {
            "message": "The server changed again. The conflict remains unresolved.",
            "project_uuid": project_uuid,
            "resolution": "conflict",
            "sync": sync_result,
        }

    log_activity(
        user_id,
        "RESOLVE_CONFLICT_LOCAL",
        f"Conflict resolved using local version: {row['name']}.",
        entity_type="project",
        entity_uuid=project_uuid,
        details={"resolution": "local", "sync": sync_result},
    )

    return {
        "message": "Conflict resolved using your local version.",
        "project_uuid": project_uuid,
        "resolution": "local",
        "sync": sync_result,
    }



# ============================================================
# PROJECT TEAM MEMBERS
# ============================================================

@app.get("/projects/{project_uuid}/members")
def get_local_project_members(project_uuid: str, request: Request):
    session = get_session(request)
    user_id = session["user_id"]
    project = get_local_project_access(project_uuid, user_id, "VIEWER")

    connection = get_local_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT project_uuid, owner_user_id, member_user_id,
               member_username, role, is_deleted, invited_at, updated_at
        FROM project_members
        WHERE project_uuid = ?
          AND COALESCE(is_deleted, 0) = 0
        ORDER BY role, member_username
        """,
        (project_uuid,),
    )
    members = [dict(row) for row in cursor.fetchall()]
    connection.close()

    return [{
        "project_uuid": project_uuid,
        "owner_user_id": project["user_id"],
        "member_user_id": project["user_id"],
        "member_username": project.get("owner_username") or project["user_id"],
        "role": "OWNER",
        "is_deleted": 0,
        "invited_at": None,
        "updated_at": None,
    }] + members


@app.post("/projects/{project_uuid}/members")
def invite_local_project_member(project_uuid: str, invite: ProjectInviteRequest, request: Request):
    session = get_session(request)
    require_csrf(request, session)
    user_id = session["user_id"]
    project = get_local_project_access(project_uuid, user_id, "OWNER")

    if not is_server_available():
        raise HTTPException(status_code=503, detail="Inviting team members requires the remote server to be online.")

    token = get_cached_remote_sync_token(user_id)
    if not token:
        raise HTTPException(status_code=401, detail="Remote sync token is missing. Log out and log in again while server 8000 is running.")

    try:
        response = requests.post(
            f"{REMOTE_SERVER}/team/projects/{project_uuid}/members",
            json={"username": invite.username, "role": normalize_role(invite.role)},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        data = response.json()
    except requests.RequestException as error:
        raise HTTPException(status_code=503, detail=f"Unable to invite team member: {error}")
    except ValueError:
        raise HTTPException(status_code=502, detail="Invalid response from remote server while inviting member.")

    if not response.ok:
        raise HTTPException(status_code=response.status_code, detail=data.get("detail", "Invite failed."))

    cache_project_member(data)
    log_activity(
        user_id,
        "INVITE_MEMBER",
        f"Invited {data.get('member_username')} as {data.get('role')} on project: {project['name']}.",
        entity_type="project_member",
        entity_uuid=data.get("member_user_id"),
        details=data,
    )
    return data


@app.put("/projects/{project_uuid}/members/{member_user_id}")
def update_local_project_member_role(
    project_uuid: str,
    member_user_id: str,
    role_update: ProjectRoleUpdateRequest,
    request: Request,
):
    session = get_session(request)
    require_csrf(request, session)
    user_id = session["user_id"]
    project = get_local_project_access(project_uuid, user_id, "OWNER")

    if member_user_id == user_id:
        raise HTTPException(status_code=400, detail="The owner's role cannot be changed.")

    if not is_server_available():
        raise HTTPException(status_code=503, detail="Changing team roles requires the remote server to be online.")

    token = get_cached_remote_sync_token(user_id)
    if not token:
        raise HTTPException(status_code=401, detail="Remote sync token is missing. Log out and log in again while server 8000 is running.")

    role = normalize_role(role_update.role)

    try:
        response = requests.put(
            f"{REMOTE_SERVER}/team/projects/{project_uuid}/members/{member_user_id}",
            json={"role": role},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        data = response.json()
    except requests.RequestException as error:
        raise HTTPException(status_code=503, detail=f"Unable to update team member role: {error}")
    except ValueError:
        raise HTTPException(status_code=502, detail="Invalid response from remote server while updating member role.")

    if not response.ok:
        raise HTTPException(status_code=response.status_code, detail=data.get("detail", "Role update failed."))

    cache_project_member(data)
    log_activity(
        user_id,
        "UPDATE_MEMBER_ROLE",
        f"Changed {data.get('member_username')} to {data.get('role')} on project: {project['name']}.",
        entity_type="project_member",
        entity_uuid=data.get("member_user_id"),
        details=data,
    )
    return data


@app.delete("/projects/{project_uuid}/members/{member_user_id}")
def remove_local_project_member(project_uuid: str, member_user_id: str, request: Request):
    session = get_session(request)
    require_csrf(request, session)
    user_id = session["user_id"]
    project = get_local_project_access(project_uuid, user_id, "OWNER")

    if not is_server_available():
        raise HTTPException(status_code=503, detail="Removing team members requires the remote server to be online.")

    token = get_cached_remote_sync_token(user_id)
    if not token:
        raise HTTPException(status_code=401, detail="Remote sync token is missing. Log out and log in again while server 8000 is running.")

    try:
        response = requests.delete(
            f"{REMOTE_SERVER}/team/projects/{project_uuid}/members/{member_user_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        data = response.json()
    except requests.RequestException as error:
        raise HTTPException(status_code=503, detail=f"Unable to remove team member: {error}")
    except ValueError:
        raise HTTPException(status_code=502, detail="Invalid response from remote server while removing member.")

    if not response.ok:
        raise HTTPException(status_code=response.status_code, detail=data.get("detail", "Remove failed."))

    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE project_members
        SET is_deleted = 1,
            updated_at = ?
        WHERE project_uuid = ?
          AND member_user_id = ?
        """,
        (current_timestamp(), project_uuid, member_user_id),
    )
    connection.commit()
    connection.close()

    log_activity(
        user_id,
        "REMOVE_MEMBER",
        f"Removed a team member from project: {project['name']}.",
        entity_type="project_member",
        entity_uuid=member_user_id,
        details=data,
    )
    return data


# ============================================================
# MANUAL SYNC
# ============================================================

@app.post("/sync")
def sync_projects(request: Request):
    session = get_session(request)
    require_csrf(request, session)
    user_id = session["user_id"]
    started_at = current_timestamp()

    if not is_server_available():
        connection = get_local_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM projects
            WHERE user_id = ? AND sync_status = 'PENDING'
            """,
            (user_id,),
        )
        pending_projects = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT COUNT(*) FROM project_notes
            WHERE user_id = ? AND sync_status = 'PENDING'
            """,
            (user_id,),
        )
        pending_notes = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT COUNT(*) FROM project_attachments
            WHERE user_id = ? AND sync_status = 'PENDING'
            """,
            (user_id,),
        )
        pending_attachments = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT COUNT(*) FROM projects
            WHERE user_id = ? AND sync_status = 'CONFLICT'
            """,
            (user_id,),
        )
        project_conflicts = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT COUNT(*) FROM project_notes
            WHERE user_id = ? AND sync_status = 'CONFLICT'
            """,
            (user_id,),
        )
        note_conflicts = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT COUNT(*) FROM project_attachments
            WHERE user_id = ? AND sync_status = 'CONFLICT'
            """,
            (user_id,),
        )
        attachment_conflicts = cursor.fetchone()[0]
        pending = pending_projects + pending_notes + pending_attachments
        conflicts = project_conflicts + note_conflicts + attachment_conflicts
        connection.close()

        completed_at = current_timestamp()
        result = {
            "message": (
                "AfriSync is offline. Local changes are safely queued "
                "and will synchronize when connectivity returns."
            ),
            "status": "offline",
            "total": pending,
            "successful": 0,
            "failed": 0,
            "conflicts": conflicts,
        }
        record_sync_history(
            user_id,
            started_at,
            completed_at,
            "offline",
            total=pending,
            successful=0,
            failed=0,
            conflicts=conflicts,
            message=result["message"],
            details=result,
        )
        log_activity(
            user_id,
            "SYNC_OFFLINE",
            f"Manual sync skipped because the remote server is offline. Pending: {pending}.",
            entity_type="sync",
            details={"pending": pending, "conflicts": conflicts},
        )
        return result

    if not has_remote_sync_token(user_id):
        message = (
            "Remote sync token is missing. Log out, start the remote server on port 8000, "
            "then log in again to refresh secure synchronization access."
        )
        completed_at = current_timestamp()
        record_sync_history(
            user_id,
            started_at,
            completed_at,
            "auth_required",
            failed=1,
            message=message,
            details={"error": message},
        )
        log_activity(
            user_id,
            "SYNC_AUTH_REQUIRED",
            message,
            entity_type="sync",
            details={"remote_token_cached": False},
        )
        raise HTTPException(status_code=401, detail=message)

    try:
        result = synchronize_pending_projects(user_id)
    except Exception as error:
        completed_at = current_timestamp()
        record_sync_history(
            user_id,
            started_at,
            completed_at,
            "failed",
            failed=1,
            message=str(error),
            details={"error": str(error)},
        )
        log_activity(
            user_id,
            "SYNC_FAILED",
            f"Manual sync failed: {error}",
            entity_type="sync",
            details={"error": str(error)},
        )
        raise HTTPException(status_code=500, detail=f"Synchronization failed: {error}")

    completed_at = current_timestamp()
    status = "completed"
    if int(result.get("failed", 0)) > 0:
        status = "partial_failure"
    if int(result.get("conflicts", 0)) > 0:
        status = "conflict"

    response_payload = {
        "message": "Synchronization completed.",
        "status": "online",
        "total": result.get("total", 0),
        "successful": result.get("successful", 0),
        "failed": result.get("failed", 0),
        "conflicts": result.get("conflicts", 0),
        "pull": result.get("pull", {}),
    }

    record_sync_history(
        user_id,
        started_at,
        completed_at,
        status,
        total=response_payload["total"],
        successful=response_payload["successful"],
        failed=response_payload["failed"],
        conflicts=response_payload["conflicts"],
        message=response_payload["message"],
        details=result,
    )
    log_activity(
        user_id,
        "SYNC_MANUAL",
        (
            "Manual sync completed: "
            f"{response_payload['successful']} successful, "
            f"{response_payload['failed']} failed, "
            f"{response_payload['conflicts']} conflict(s)."
        ),
        entity_type="sync",
        details=response_payload,
    )

    return response_payload


@app.get("/activity")
def get_activity(request: Request, limit: int = 20):
    session = get_session(request)
    user_id = session["user_id"]
    safe_limit = max(1, min(int(limit or 20), 100))

    connection = get_local_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT id, user_id, action, entity_type, entity_uuid,
               message, details, created_at
        FROM activity_logs
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (user_id, safe_limit),
    )
    rows = cursor.fetchall()
    connection.close()
    return [serialize_activity_row(row) for row in rows]


@app.get("/sync-history")
def get_sync_history(request: Request, limit: int = 10):
    session = get_session(request)
    user_id = session["user_id"]
    safe_limit = max(1, min(int(limit or 10), 100))

    connection = get_local_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT id, user_id, started_at, completed_at, status,
               total, successful, failed, conflicts, message, details
        FROM sync_history
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (user_id, safe_limit),
    )
    rows = cursor.fetchall()
    connection.close()
    return [serialize_sync_history_row(row) for row in rows]


@app.get("/notifications")
def get_notifications(request: Request, limit: int = 30, unread_only: bool = False):
    session = get_session(request)
    user_id = session["user_id"]
    safe_limit = max(1, min(int(limit or 30), 100))

    connection = get_local_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    if unread_only:
        cursor.execute(
            """
            SELECT notification_uuid, title, message, category,
                   entity_type, entity_uuid, is_read, created_at
            FROM notifications
            WHERE user_id = ? AND COALESCE(is_read, 0) = 0
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, safe_limit),
        )
    else:
        cursor.execute(
            """
            SELECT notification_uuid, title, message, category,
                   entity_type, entity_uuid, is_read, created_at
            FROM notifications
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, safe_limit),
        )

    rows = cursor.fetchall()
    connection.close()
    return [serialize_notification_row(row) for row in rows]


@app.get("/notifications/unread-count")
def get_unread_notification_count(request: Request):
    session = get_session(request)
    user_id = session["user_id"]

    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM notifications
        WHERE user_id = ? AND COALESCE(is_read, 0) = 0
        """,
        (user_id,),
    )
    count = cursor.fetchone()[0]
    connection.close()
    return {"unread": int(count or 0)}


@app.post("/notifications/{notification_uuid}/read")
def mark_notification_read(notification_uuid: str, request: Request):
    session = get_session(request)
    require_csrf(request, session)
    user_id = session["user_id"]

    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE notifications
        SET is_read = 1
        WHERE notification_uuid = ? AND user_id = ?
        """,
        (notification_uuid, user_id),
    )
    changed = cursor.rowcount
    connection.commit()
    connection.close()

    if not changed:
        raise HTTPException(status_code=404, detail="Notification not found.")

    return {"message": "Notification marked as read.", "notification_uuid": notification_uuid}


@app.post("/notifications/read-all")
def mark_all_notifications_read(request: Request):
    session = get_session(request)
    require_csrf(request, session)
    user_id = session["user_id"]

    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE notifications
        SET is_read = 1
        WHERE user_id = ? AND COALESCE(is_read, 0) = 0
        """,
        (user_id,),
    )
    changed = cursor.rowcount
    connection.commit()
    connection.close()

    return {"message": "All notifications marked as read.", "updated": int(changed or 0)}


@app.delete("/notifications/{notification_uuid}")
def delete_notification(notification_uuid: str, request: Request):
    session = get_session(request)
    require_csrf(request, session)
    user_id = session["user_id"]

    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        DELETE FROM notifications
        WHERE notification_uuid = ? AND user_id = ?
        """,
        (notification_uuid, user_id),
    )
    changed = cursor.rowcount
    connection.commit()
    connection.close()

    if not changed:
        raise HTTPException(status_code=404, detail="Notification not found.")

    return {"message": "Notification deleted.", "notification_uuid": notification_uuid}


@app.delete("/notifications/clear-read")
def clear_read_notifications(request: Request):
    session = get_session(request)
    require_csrf(request, session)
    user_id = session["user_id"]

    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        DELETE FROM notifications
        WHERE user_id = ? AND COALESCE(is_read, 0) = 1
        """,
        (user_id,),
    )
    deleted = cursor.rowcount
    connection.commit()
    connection.close()

    return {"message": "Read notifications cleared.", "deleted": int(deleted or 0)}


@app.get("/health")
def health_check():
    return {
        "status": "online",
        "service": "AfriSync Local App",
        "device_name": DEVICE_NAME,
        "local_database": LOCAL_DATABASE,
        "upload_root": str(UPLOAD_ROOT),
        "remote_server": REMOTE_SERVER,
        "remote_online": is_server_available(),
    }
