import base64
import binascii
from datetime import datetime
from typing import Optional
import hashlib
import hmac
import json
import os
import smtplib
import re
import secrets
import sqlite3
from afrisync_db import get_afrisync_connection, column_exists as backend_column_exists, get_database_backend
import requests
import time
import uuid
from pathlib import Path
from email.message import EmailMessage

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, field_validator

from app.sync_engine import synchronize_pending_projects
from app.database import get_local_connection

app = FastAPI(title="AfriSync API")
SERVER_DATABASE = os.getenv("AFRISYNC_SERVER_DB", "server.db")
SERVER_UPLOAD_ROOT = Path(os.getenv("AFRISYNC_SERVER_UPLOAD_ROOT", "server_uploads"))
MAX_ATTACHMENT_BYTES = int(os.getenv("AFRISYNC_MAX_ATTACHMENT_BYTES", str(10 * 1024 * 1024)))
SYNC_TOKEN_TTL_SECONDS = int(os.getenv("AFRISYNC_SYNC_TOKEN_TTL_SECONDS", str(30 * 24 * 60 * 60)))
PASSWORD_RESET_TTL_SECONDS = int(os.getenv("AFRISYNC_PASSWORD_RESET_TTL_SECONDS", str(60 * 60)))
EMAIL_VERIFICATION_TTL_SECONDS = int(os.getenv("AFRISYNC_EMAIL_VERIFICATION_TTL_SECONDS", str(10 * 60)))
SMTP_HOST = os.getenv("AFRISYNC_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("AFRISYNC_SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("AFRISYNC_SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("AFRISYNC_SMTP_PASSWORD", "").strip()
SMTP_FROM_EMAIL = os.getenv("AFRISYNC_SMTP_FROM_EMAIL", SMTP_USERNAME).strip()
SMTP_FROM_NAME = os.getenv("AFRISYNC_SMTP_FROM_NAME", "AfriSync").strip()
SMTP_USE_SSL = os.getenv("AFRISYNC_SMTP_USE_SSL", "0").strip().lower() in {"1", "true", "yes", "on"}
EMAIL_ALLOW_DEVELOPMENT_CODE = os.getenv("AFRISYNC_EMAIL_ALLOW_DEVELOPMENT_CODE", "0").strip().lower() in {"1", "true", "yes", "on"}
EMAIL_REQUIRE_SMTP = os.getenv("AFRISYNC_EMAIL_REQUIRE_SMTP", "1").strip().lower() in {"1", "true", "yes", "on"}
GOOGLE_OAUTH_CLIENT_ID = os.getenv("AFRISYNC_GOOGLE_CLIENT_ID", "").strip()
GOOGLE_OAUTH_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
SYNC_SECRET_FILE = Path(os.getenv("AFRISYNC_SYNC_SECRET_FILE", ".afrisync_server_secret"))
SERVER_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


def get_connection():
    return get_afrisync_connection(SERVER_DATABASE)


def column_exists(cursor, table_name, column_name):
    return backend_column_exists(cursor, table_name, column_name)


print(f"[AfriSync Remote] Database backend: {get_database_backend()}")


def current_timestamp():
    return datetime.now().isoformat()


def clean_file_name(file_name):
    name = Path(file_name or "attachment").name.strip()
    if not name:
        name = "attachment"
    name = re.sub(r"[^A-Za-z0-9À-ÖØ-öø-ÿ._ ()'-]+", "_", name)
    name = name.strip(" ._")
    if not name:
        name = "attachment"
    return name[:180]


def get_server_attachment_folder(user_id, project_uuid):
    safe_user_id = clean_file_name(user_id)
    safe_project_uuid = clean_file_name(project_uuid)
    folder = SERVER_UPLOAD_ROOT / safe_user_id / safe_project_uuid
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def decode_base64_file(file_content):
    if not file_content:
        return b""
    content = file_content.strip()
    if content.startswith("data:") and "," in content:
        content = content.split(",", 1)[1]
    try:
        return base64.b64decode(content, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="Invalid attachment file content.")


def encode_file_to_base64(file_path):
    try:
        path = Path(file_path)
        if not path.is_file():
            return None
        return base64.b64encode(path.read_bytes()).decode("utf-8")
    except OSError:
        return None


def initialize_database():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    user_additions = [
        ("email", "TEXT"),
        ("full_name", "TEXT"),
        ("email_verified", "INTEGER DEFAULT 1"),
        ("email_verified_at", "TEXT"),
        ("is_disabled", "INTEGER DEFAULT 0"),
        ("disabled_at", "TEXT"),
        ("disabled_reason", "TEXT"),
        ("updated_at", "TEXT"),
        ("password_updated_at", "TEXT"),
        ("google_sub", "TEXT"),
        ("auth_provider", "TEXT DEFAULT 'password'"),
        ("google_linked_at", "TEXT"),
        ("avatar_url", "TEXT"),
    ]
    for name, definition in user_additions:
        if not column_exists(cursor, "users", name):
            cursor.execute(f"ALTER TABLE users ADD COLUMN {name} {definition}")
    cursor.execute("UPDATE users SET is_disabled = 0 WHERE is_disabled IS NULL")
    cursor.execute("UPDATE users SET email_verified = 1 WHERE email_verified IS NULL")
    cursor.execute("UPDATE users SET email = lower(trim(email)) WHERE email IS NOT NULL AND trim(email) != ''")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users (lower(email)) WHERE email IS NOT NULL AND email != ''")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub_unique ON users (google_sub) WHERE google_sub IS NOT NULL AND google_sub != ''")
    cursor.execute("UPDATE users SET auth_provider = COALESCE(auth_provider, 'password') WHERE auth_provider IS NULL OR auth_provider = ''")
    cursor.execute("UPDATE users SET updated_at = COALESCE(updated_at, created_at, ?) WHERE updated_at IS NULL", (current_timestamp(),))
    cursor.execute("UPDATE users SET password_updated_at = COALESCE(password_updated_at, created_at, updated_at, ?) WHERE password_updated_at IS NULL", (current_timestamp(),))

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT,
            progress INTEGER DEFAULT 0,
            sync_status TEXT DEFAULT 'SYNCED',
            project_uuid TEXT UNIQUE,
            user_id TEXT,
            is_deleted INTEGER DEFAULT 0,
            deleted_at TEXT,
            version INTEGER DEFAULT 1,
            updated_at TEXT,
            conflict_data TEXT
        )
    """)

    additions = [
        ("user_id", "TEXT"),
        ("is_deleted", "INTEGER DEFAULT 0"),
        ("deleted_at", "TEXT"),
        ("version", "INTEGER DEFAULT 1"),
        ("updated_at", "TEXT"),
        ("conflict_data", "TEXT"),
    ]
    for name, definition in additions:
        if not column_exists(cursor, "projects", name):
            cursor.execute(f"ALTER TABLE projects ADD COLUMN {name} {definition}")

    cursor.execute("UPDATE projects SET is_deleted = 0 WHERE is_deleted IS NULL")
    cursor.execute("UPDATE projects SET version = 1 WHERE version IS NULL OR version < 1")
    cursor.execute("UPDATE projects SET updated_at = ? WHERE updated_at IS NULL", (current_timestamp(),))
    connection.commit()
    connection.close()


initialize_database()


# ============================================================
# PASSWORD RESET DATABASE
# ============================================================

def initialize_password_reset_database():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_hash TEXT UNIQUE NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used_at TEXT
        )
        """
    )

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_password_reset_user ON password_reset_tokens (user_id, used_at, expires_at)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_password_reset_hash ON password_reset_tokens (token_hash)"
    )

    connection.commit()
    connection.close()


initialize_password_reset_database()


# ============================================================
# EMAIL VERIFICATION DATABASE
# ============================================================

def initialize_email_verification_database():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS email_verification_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code_hash TEXT NOT NULL,
            user_id TEXT NOT NULL,
            email TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            attempts INTEGER DEFAULT 0
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_email_verification_user ON email_verification_codes (user_id, used_at, expires_at)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_email_verification_code ON email_verification_codes (code_hash)"
    )
    connection.commit()
    connection.close()


initialize_email_verification_database()


# ============================================================
# SERVER NOTE SYNCHRONIZATION DATABASE
# ============================================================

def initialize_notes_database():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS project_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_uuid TEXT UNIQUE NOT NULL,
            project_uuid TEXT NOT NULL,
            user_id TEXT NOT NULL,
            content TEXT NOT NULL,
            sync_status TEXT DEFAULT 'SYNCED',
            is_deleted INTEGER DEFAULT 0,
            deleted_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            version INTEGER DEFAULT 1,
            conflict_data TEXT
        )
        """
    )

    note_columns = [
        ("project_uuid", "TEXT"),
        ("user_id", "TEXT"),
        ("content", "TEXT DEFAULT ''"),
        ("sync_status", "TEXT DEFAULT 'SYNCED'"),
        ("is_deleted", "INTEGER DEFAULT 0"),
        ("deleted_at", "TEXT"),
        ("created_at", "TEXT"),
        ("updated_at", "TEXT"),
        ("version", "INTEGER DEFAULT 1"),
        ("conflict_data", "TEXT"),
    ]

    for name, definition in note_columns:
        if not column_exists(cursor, "project_notes", name):
            cursor.execute(f"ALTER TABLE project_notes ADD COLUMN {name} {definition}")

    now = current_timestamp()
    cursor.execute("UPDATE project_notes SET sync_status = 'SYNCED' WHERE sync_status IS NULL")
    cursor.execute("UPDATE project_notes SET is_deleted = 0 WHERE is_deleted IS NULL")
    cursor.execute("UPDATE project_notes SET version = 1 WHERE version IS NULL OR version < 1")
    cursor.execute("UPDATE project_notes SET created_at = ? WHERE created_at IS NULL", (now,))
    cursor.execute("UPDATE project_notes SET updated_at = ? WHERE updated_at IS NULL", (now,))

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_server_notes_user_updated ON project_notes (user_id, updated_at)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_server_notes_project ON project_notes (project_uuid, user_id, is_deleted)"
    )

    connection.commit()
    connection.close()


initialize_notes_database()


# ============================================================
# SERVER ATTACHMENT SYNCHRONIZATION DATABASE
# ============================================================

def initialize_attachments_database():
    connection = get_connection()
    cursor = connection.cursor()

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
            sync_status TEXT DEFAULT 'SYNCED',
            is_deleted INTEGER DEFAULT 0,
            deleted_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            version INTEGER DEFAULT 1,
            conflict_data TEXT
        )
        """
    )

    attachment_columns = [
        ("project_uuid", "TEXT"),
        ("user_id", "TEXT"),
        ("original_file_name", "TEXT DEFAULT 'attachment'"),
        ("stored_file_name", "TEXT DEFAULT ''"),
        ("file_path", "TEXT DEFAULT ''"),
        ("file_type", "TEXT DEFAULT 'application/octet-stream'"),
        ("file_size", "INTEGER DEFAULT 0"),
        ("sync_status", "TEXT DEFAULT 'SYNCED'"),
        ("is_deleted", "INTEGER DEFAULT 0"),
        ("deleted_at", "TEXT"),
        ("created_at", "TEXT"),
        ("updated_at", "TEXT"),
        ("version", "INTEGER DEFAULT 1"),
        ("conflict_data", "TEXT"),
    ]

    for name, definition in attachment_columns:
        if not column_exists(cursor, "project_attachments", name):
            cursor.execute(f"ALTER TABLE project_attachments ADD COLUMN {name} {definition}")

    now = current_timestamp()
    cursor.execute("UPDATE project_attachments SET sync_status = 'SYNCED' WHERE sync_status IS NULL")
    cursor.execute("UPDATE project_attachments SET is_deleted = 0 WHERE is_deleted IS NULL")
    cursor.execute("UPDATE project_attachments SET version = 1 WHERE version IS NULL OR version < 1")
    cursor.execute("UPDATE project_attachments SET created_at = ? WHERE created_at IS NULL", (now,))
    cursor.execute("UPDATE project_attachments SET updated_at = ? WHERE updated_at IS NULL", (now,))

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_server_attachments_user_updated ON project_attachments (user_id, updated_at)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_server_attachments_project ON project_attachments (project_uuid, user_id, is_deleted)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_server_attachments_uuid_user ON project_attachments (attachment_uuid, user_id)"
    )

    connection.commit()
    connection.close()


initialize_attachments_database()


def hash_password(password):
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000
    ).hex()
    return f"{salt}${password_hash}"


def verify_password(password, stored_password):
    try:
        salt, stored_hash = stored_password.split("$")
        password_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000
        ).hex()
        return secrets.compare_digest(password_hash, stored_hash)
    except ValueError:
        return False


def hash_token(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_password_reset_token(cursor, user_id, username):
    raw_token = secrets.token_urlsafe(36)
    now = datetime.now()
    expires_at = datetime.fromtimestamp(time.time() + PASSWORD_RESET_TTL_SECONDS)

    cursor.execute(
        "UPDATE password_reset_tokens SET used_at = ? WHERE user_id = ? AND used_at IS NULL",
        (now.isoformat(), user_id),
    )
    cursor.execute(
        "DELETE FROM password_reset_tokens WHERE expires_at <= ?",
        (now.isoformat(),),
    )
    cursor.execute(
        """
        INSERT INTO password_reset_tokens (
            token_hash, user_id, username, created_at, expires_at, used_at
        ) VALUES (?, ?, ?, ?, ?, NULL)
        """,
        (
            hash_token(raw_token),
            user_id,
            username,
            now.isoformat(),
            expires_at.isoformat(),
        ),
    )
    return raw_token, expires_at.isoformat()


def normalize_email(value):
    email = (value or "").strip().lower()
    if not email:
        return ""
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ValueError("Enter a valid email address.")
    return email




def google_oauth_is_configured():
    return bool(GOOGLE_OAUTH_CLIENT_ID and not is_placeholder_secret(GOOGLE_OAUTH_CLIENT_ID))


def google_auth_status_payload():
    return {
        "configured": google_oauth_is_configured(),
        "client_id": GOOGLE_OAUTH_CLIENT_ID if google_oauth_is_configured() else None,
        "provider": "google",
        "mode": "google_identity_services",
    }


def make_unique_google_username(cursor, email, full_name=None):
    if email and "@" in email:
        base = email.split("@", 1)[0]
    elif full_name:
        base = re.sub(r"[^A-Za-z0-9_.-]+", ".", full_name.strip().lower())
    else:
        base = "google_user"
    base = re.sub(r"[^A-Za-z0-9_.-]+", "", base).strip("._-").lower() or "google_user"
    if len(base) < 3:
        base = f"user_{base}"
    base = base[:28]
    candidate = base
    counter = 2
    while True:
        cursor.execute("SELECT user_id FROM users WHERE lower(username) = lower(?)", (candidate,))
        if not cursor.fetchone():
            return candidate
        candidate = f"{base[:24]}{counter}"
        counter += 1


def verify_google_id_token(credential):
    if not google_oauth_is_configured():
        raise HTTPException(
            status_code=503,
            detail="Google login is not configured. Add AFRISYNC_GOOGLE_CLIENT_ID and restart the remote server.",
        )
    credential = (credential or "").strip()
    if not credential:
        raise HTTPException(status_code=400, detail="Google credential is required.")
    try:
        response = requests.get(
            GOOGLE_OAUTH_TOKENINFO_URL,
            params={"id_token": credential},
            timeout=10,
        )
        claims = response.json()
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"Could not verify Google credential: {error}")
    if not response.ok:
        raise HTTPException(status_code=401, detail="Google credential is invalid or expired.")
    if claims.get("aud") != GOOGLE_OAUTH_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Google credential was issued for a different app.")
    if claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        raise HTTPException(status_code=401, detail="Google credential issuer is invalid.")
    try:
        if int(claims.get("exp", "0")) <= int(time.time()):
            raise HTTPException(status_code=401, detail="Google credential has expired.")
    except ValueError:
        raise HTTPException(status_code=401, detail="Google credential expiry is invalid.")
    if str(claims.get("email_verified", "false")).lower() not in {"true", "1"}:
        raise HTTPException(status_code=403, detail="Google account email is not verified.")
    email = normalize_email(claims.get("email", ""))
    if not email:
        raise HTTPException(status_code=400, detail="Google did not return an email address.")
    if not claims.get("sub"):
        raise HTTPException(status_code=400, detail="Google did not return a stable account ID.")
    return {
        "google_sub": claims.get("sub"),
        "email": email,
        "full_name": (claims.get("name") or "").strip() or None,
        "avatar_url": (claims.get("picture") or "").strip() or None,
    }

def is_placeholder_secret(value):
    value = (value or "").strip()
    if not value:
        return True
    lowered = value.lower()
    placeholders = [
        "put_",
        "your_",
        "change_me",
        "example",
        "gmail_app_password",
        "sender@gmail.com",
    ]
    return any(item in lowered for item in placeholders)


def smtp_is_configured():
    return bool(
        SMTP_HOST
        and SMTP_PORT
        and not is_placeholder_secret(SMTP_USERNAME)
        and not is_placeholder_secret(SMTP_PASSWORD)
        and not is_placeholder_secret(SMTP_FROM_EMAIL)
    )


def email_delivery_status_payload():
    return {
        "smtp_configured": smtp_is_configured(),
        "host": SMTP_HOST,
        "port": SMTP_PORT,
        "use_ssl": SMTP_USE_SSL,
        "from_email": SMTP_FROM_EMAIL if SMTP_FROM_EMAIL and not is_placeholder_secret(SMTP_FROM_EMAIL) else None,
        "from_name": SMTP_FROM_NAME,
        "development_code_allowed": EMAIL_ALLOW_DEVELOPMENT_CODE,
        "real_email_required": EMAIL_REQUIRE_SMTP,
    }


def send_email_message(to_email, subject, plain_body):
    if not smtp_is_configured():
        return {
            "sent": False,
            "delivery": "smtp_not_configured",
            "message": (
                "Real email delivery is not configured. Add a sender Gmail address and a Gmail App Password "
                "inside run_remote_server.ps1, then restart the remote server."
            ),
        }

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    message["To"] = to_email
    message.set_content(plain_body)

    try:
        if SMTP_USE_SSL or int(SMTP_PORT) == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=25) as server:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(message)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=25) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(message)
        return {"sent": True, "delivery": "smtp", "message": "Email sent."}
    except smtplib.SMTPAuthenticationError:
        return {
            "sent": False,
            "delivery": "smtp_auth_failed",
            "message": (
                "Gmail rejected the sender login. Use a Gmail App Password, not the normal Gmail password, "
                "and restart the remote server."
            ),
        }
    except Exception as error:
        return {
            "sent": False,
            "delivery": "smtp_failed",
            "message": f"Email could not be sent: {error}",
        }


def create_email_verification_code(cursor, user_id, email):
    code = f"{secrets.randbelow(10000):04d}"
    now = datetime.now()
    expires_at = datetime.fromtimestamp(time.time() + EMAIL_VERIFICATION_TTL_SECONDS)

    cursor.execute(
        "UPDATE email_verification_codes SET used_at = ? WHERE user_id = ? AND used_at IS NULL",
        (now.isoformat(), user_id),
    )
    cursor.execute(
        "DELETE FROM email_verification_codes WHERE expires_at <= ?",
        (now.isoformat(),),
    )
    cursor.execute(
        """
        INSERT INTO email_verification_codes (
            code_hash, user_id, email, created_at, expires_at, used_at, attempts
        ) VALUES (?, ?, ?, ?, ?, NULL, 0)
        """,
        (hash_token(code), user_id, email, now.isoformat(), expires_at.isoformat()),
    )
    return code, expires_at.isoformat()


def send_verification_code(email, username, code):
    body = (
        f"Hello {username},\n\n"
        f"Your AfriSync account verification code is: {code}\n\n"
        "This 4-digit code expires in 10 minutes. Enter it in AfriSync to activate your account.\n\n"
        "If you did not create an AfriSync account, you can safely ignore this message.\n\n"
        "AfriSync Team"
    )
    return send_email_message(email, "Verify your AfriSync account", body)


def send_password_reset_email(email, username, token):
    body = (
        f"Hello {username},\n\n"
        "A password reset was requested for your AfriSync account.\n\n"
        f"Reset token: {token}\n\n"
        "This token expires in 60 minutes. Paste it into the AfriSync password reset screen to set a new password.\n\n"
        "If you did not request this reset, ignore this message.\n\n"
        "AfriSync Team"
    )
    return send_email_message(email, "Reset your AfriSync password", body)


# ============================================================
# REMOTE API SECURITY
# ============================================================


def base64url_encode(raw_bytes):
    return base64.urlsafe_b64encode(raw_bytes).decode("utf-8").rstrip("=")


def base64url_decode(value):
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))


def get_sync_secret():
    """
    Returns the signing secret used for remote synchronization tokens.

    For local development, the secret is automatically created in
    .afrisync_server_secret. In production, set AFRISYNC_SYNC_SECRET
    in the server environment instead.
    """
    environment_secret = os.environ.get("AFRISYNC_SYNC_SECRET")
    if environment_secret:
        return environment_secret.encode("utf-8")

    if SYNC_SECRET_FILE.exists():
        saved_secret = SYNC_SECRET_FILE.read_text(encoding="utf-8").strip()
        if saved_secret:
            return saved_secret.encode("utf-8")

    generated_secret = secrets.token_urlsafe(64)
    SYNC_SECRET_FILE.write_text(generated_secret, encoding="utf-8")
    return generated_secret.encode("utf-8")


def sign_token_payload(encoded_payload):
    signature = hmac.new(
        get_sync_secret(),
        encoded_payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64url_encode(signature)


def create_sync_token(user_id, username):
    issued_at = int(time.time())
    expires_at = issued_at + SYNC_TOKEN_TTL_SECONDS
    payload = {
        "typ": "afrisync-sync-token",
        "sub": user_id,
        "username": username,
        "iat": issued_at,
        "exp": expires_at,
    }
    encoded_payload = base64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signature = sign_token_payload(encoded_payload)
    token = f"{encoded_payload}.{signature}"
    return token, datetime.fromtimestamp(expires_at).isoformat()


def read_bearer_token(request: Request):
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Remote API token is required.")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Remote API token is empty.")
    return token


def verify_sync_token(token):
    try:
        encoded_payload, supplied_signature = token.split(".", 1)
    except ValueError:
        raise HTTPException(status_code=401, detail="Remote API token is malformed.")

    expected_signature = sign_token_payload(encoded_payload)
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise HTTPException(status_code=401, detail="Remote API token signature is invalid.")

    try:
        payload = json.loads(base64url_decode(encoded_payload).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=401, detail="Remote API token payload is invalid.")

    if payload.get("typ") != "afrisync-sync-token":
        raise HTTPException(status_code=401, detail="Remote API token type is invalid.")

    user_id = payload.get("sub")
    username = payload.get("username")
    expires_at = int(payload.get("exp") or 0)

    if not user_id or not username:
        raise HTTPException(status_code=401, detail="Remote API token is missing user details.")

    if expires_at <= int(time.time()):
        raise HTTPException(status_code=401, detail="Remote API token has expired. Log in again.")

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT user_id, username, COALESCE(is_disabled, 0) AS is_disabled, password_updated_at
        FROM users
        WHERE user_id = ? AND username = ?
        """,
        (user_id, username),
    )
    user = cursor.fetchone()
    connection.close()

    if not user:
        raise HTTPException(status_code=401, detail="Remote API token user no longer exists.")

    if int(user["is_disabled"] or 0) == 1:
        raise HTTPException(status_code=403, detail="This user account has been disabled by an administrator.")

    password_updated_at = user["password_updated_at"]
    if password_updated_at:
        try:
            password_updated_timestamp = int(datetime.fromisoformat(password_updated_at).timestamp())
            issued_at = int(payload.get("iat") or 0)
            if issued_at and issued_at < password_updated_timestamp:
                raise HTTPException(status_code=401, detail="Remote API token is no longer valid. Log in again.")
        except ValueError:
            pass

    return {
        "user_id": user["user_id"],
        "username": user["username"],
    }


def require_sync_auth(request: Request):
    return verify_sync_token(read_bearer_token(request))


def require_payload_owner(payload_user_id, authenticated_user_id):
    if payload_user_id != authenticated_user_id:
        raise HTTPException(
            status_code=403,
            detail="Payload user_id does not match the authenticated remote user.",
        )


def validate_text(value, field_name):
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} cannot be empty.")
    if len(value) < 2:
        raise ValueError(f"{field_name} must contain at least 2 characters.")
    if not any(character.isalpha() for character in value):
        raise ValueError(f"{field_name} must contain letters.")
    return value


def validate_location(value):
    value = value.strip()
    if not value:
        raise ValueError("Location cannot be empty.")
    if len(value) < 2:
        raise ValueError("Location must contain at least 2 characters.")
    if not any(character.isalpha() for character in value):
        raise ValueError("Location must contain letters.")
    if any(character.isdigit() for character in value):
        raise ValueError("Location must use words only. Numbers are not allowed.")
    if not re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ' -]+", value):
        raise ValueError("Location may contain letters, spaces, hyphens or apostrophes only.")
    return value


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    full_name: Optional[str] = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Username must contain at least 3 characters.")
        if not any(character.isalpha() for character in value):
            raise ValueError("Username must contain letters.")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
            raise ValueError("Username may contain letters, numbers, dots, underscores and hyphens only.")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        if value is None or not str(value).strip():
            return None
        return normalize_email(value)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value):
        if value is None:
            return None
        value = value.strip()
        if value and len(value) < 2:
            raise ValueError("Full name must contain at least 2 characters.")
        return value or None

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        if len(value) < 6:
            raise ValueError("Password must contain at least 6 characters.")
        return value


class LoginRequest(BaseModel):
    username: str
    password: str


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

    @field_validator("username_or_email")
    @classmethod
    def validate_identifier(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Enter your username or email address.")
        return value


class EmailVerificationConfirm(BaseModel):
    username_or_email: str
    code: str

    @field_validator("username_or_email")
    @classmethod
    def validate_identifier(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Enter your username or email address.")
        return value

    @field_validator("code")
    @classmethod
    def validate_code(cls, value):
        value = value.strip()
        if not re.fullmatch(r"\d{4}", value):
            raise ValueError("Verification code must be exactly 4 digits.")
        return value


class GoogleAuthRequest(BaseModel):
    credential: str

    @field_validator("credential")
    @classmethod
    def validate_credential(cls, value):
        value = value.strip()
        if len(value) < 20:
            raise ValueError("Google credential is invalid.")
        return value


class Project(BaseModel):
    project_uuid: str
    user_id: str
    name: str
    location: str
    progress: int
    is_deleted: int = 0
    deleted_at: Optional[str] = None
    # None means a direct dashboard/API edit. An integer means a sync client
    # is using optimistic concurrency and expects that exact server version.
    version: Optional[int] = None
    updated_at: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        return validate_text(value, "Project name")

    @field_validator("location")
    @classmethod
    def validate_project_location(cls, value):
        return validate_location(value)

    @field_validator("progress")
    @classmethod
    def validate_progress(cls, value):
        if value < 0 or value > 100:
            raise ValueError("Progress must be between 0 and 100.")
        return value

    @field_validator("is_deleted")
    @classmethod
    def validate_deleted(cls, value):
        if value not in (0, 1):
            raise ValueError("is_deleted must be 0 or 1.")
        return value




class SyncNote(BaseModel):
    note_uuid: str
    project_uuid: str
    user_id: str
    content: str
    is_deleted: int = 0
    deleted_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    version: Optional[int] = None

    @field_validator("content")
    @classmethod
    def validate_content(cls, value):
        value = value.strip()
        if len(value) > 2000:
            raise ValueError("Note cannot be longer than 2,000 characters.")
        return value

    @field_validator("is_deleted")
    @classmethod
    def validate_note_deleted(cls, value):
        if value not in (0, 1):
            raise ValueError("is_deleted must be 0 or 1.")
        return value


class SyncAttachment(BaseModel):
    attachment_uuid: str
    project_uuid: str
    user_id: str
    original_file_name: str
    file_type: Optional[str] = "application/octet-stream"
    file_size: int = 0
    file_content: Optional[str] = None
    is_deleted: int = 0
    deleted_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    version: Optional[int] = None

    @field_validator("original_file_name")
    @classmethod
    def validate_original_file_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Attachment file name is required.")
        return value

    @field_validator("file_size")
    @classmethod
    def validate_file_size(cls, value):
        if value < 0:
            raise ValueError("File size cannot be negative.")
        if value > MAX_ATTACHMENT_BYTES:
            raise ValueError("Attachment is too large for this version.")
        return value

    @field_validator("is_deleted")
    @classmethod
    def validate_attachment_deleted(cls, value):
        if value not in (0, 1):
            raise ValueError("is_deleted must be 0 or 1.")
        return value



# ============================================================
# TEAM COLLABORATION + ROLES
# ============================================================

TEAM_ROLES = {"OWNER", "EDITOR", "VIEWER"}
ROLE_LEVELS = {"VIEWER": 1, "EDITOR": 2, "OWNER": 3}


def normalize_role(role):
    value = (role or "VIEWER").strip().upper()
    if value not in TEAM_ROLES or value == "OWNER":
        # OWNER is assigned automatically to the creator only.
        value = "VIEWER"
    return value


def initialize_team_database():
    connection = get_connection()
    cursor = connection.cursor()
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
            invited_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(project_uuid, member_user_id)
        )
        """
    )
    columns = [
        ("owner_user_id", "TEXT"),
        ("member_user_id", "TEXT"),
        ("member_username", "TEXT DEFAULT ''"),
        ("role", "TEXT DEFAULT 'VIEWER'"),
        ("is_deleted", "INTEGER DEFAULT 0"),
        ("invited_at", "TEXT"),
        ("updated_at", "TEXT"),
    ]
    for name, definition in columns:
        if not column_exists(cursor, "project_members", name):
            cursor.execute(f"ALTER TABLE project_members ADD COLUMN {name} {definition}")
    now = current_timestamp()
    cursor.execute("UPDATE project_members SET role = UPPER(role) WHERE role IS NOT NULL")
    cursor.execute("UPDATE project_members SET role = 'VIEWER' WHERE role IS NULL OR role NOT IN ('EDITOR','VIEWER')")
    cursor.execute("UPDATE project_members SET is_deleted = 0 WHERE is_deleted IS NULL")
    cursor.execute("UPDATE project_members SET invited_at = ? WHERE invited_at IS NULL", (now,))
    cursor.execute("UPDATE project_members SET updated_at = ? WHERE updated_at IS NULL", (now,))
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_members_member ON project_members (member_user_id, is_deleted)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_members_project ON project_members (project_uuid, is_deleted)"
    )
    connection.commit()
    connection.close()


initialize_team_database()


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
        value = normalize_role(value)
        if value not in {"EDITOR", "VIEWER"}:
            raise ValueError("Role must be EDITOR or VIEWER.")
        return value


class ProjectRoleUpdateRequest(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, value):
        value = normalize_role(value)
        if value not in {"EDITOR", "VIEWER"}:
            raise ValueError("Role must be EDITOR or VIEWER.")
        return value


def get_username_for_user_id(user_id):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    connection.close()
    return row["username"] if row else None


def get_user_by_username(username):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "SELECT user_id, username FROM users WHERE lower(username) = lower(?)",
        (username.strip(),),
    )
    row = cursor.fetchone()
    connection.close()
    return row


def get_project_owner_row(project_uuid):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT p.project_uuid, p.user_id AS owner_user_id, p.name, p.is_deleted,
               u.username AS owner_username
        FROM projects p
        LEFT JOIN users u ON u.user_id = p.user_id
        WHERE p.project_uuid = ?
        """,
        (project_uuid,),
    )
    row = cursor.fetchone()
    connection.close()
    return row


def server_project_access_role(project_uuid, user_id):
    owner = get_project_owner_row(project_uuid)
    if not owner or int(owner["is_deleted"] or 0) == 1:
        return None
    if owner["owner_user_id"] == user_id:
        return "OWNER"

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT role
        FROM project_members
        WHERE project_uuid = ?
          AND member_user_id = ?
          AND COALESCE(is_deleted, 0) = 0
        """,
        (project_uuid, user_id),
    )
    row = cursor.fetchone()
    connection.close()
    if not row:
        return None
    role = (row["role"] or "VIEWER").upper()
    return role if role in TEAM_ROLES else "VIEWER"


def require_server_project_permission(project_uuid, user_id, minimum_role="VIEWER"):
    role = server_project_access_role(project_uuid, user_id)
    if not role:
        raise HTTPException(status_code=403, detail="You do not have access to this project.")
    if ROLE_LEVELS[role] < ROLE_LEVELS[minimum_role]:
        raise HTTPException(status_code=403, detail=f"{minimum_role.title()} access is required for this action.")
    return role


def shared_project_select_sql(include_deleted=False):
    deleted_filter = "" if include_deleted else "AND COALESCE(p.is_deleted, 0) = 0"
    return f"""
        SELECT p.project_uuid, p.user_id, p.name, p.location, p.progress,
               p.sync_status, p.is_deleted, p.deleted_at, p.version, p.updated_at,
               CASE
                   WHEN p.user_id = ? THEN 'OWNER'
                   ELSE UPPER(COALESCE(pm.role, 'VIEWER'))
               END AS access_role,
               CASE WHEN p.user_id = ? THEN 1 ELSE 0 END AS is_owner,
               owner.username AS owner_username
        FROM projects p
        LEFT JOIN project_members pm
               ON pm.project_uuid = p.project_uuid
              AND pm.member_user_id = ?
              AND COALESCE(pm.is_deleted, 0) = 0
        LEFT JOIN users owner ON owner.user_id = p.user_id
        WHERE (p.user_id = ? OR pm.member_user_id IS NOT NULL)
          {deleted_filter}
        ORDER BY p.id
    """


def accessible_project_ids_subquery():
    return """
        SELECT p.project_uuid
        FROM projects p
        LEFT JOIN project_members pm
               ON pm.project_uuid = p.project_uuid
              AND pm.member_user_id = ?
              AND COALESCE(pm.is_deleted, 0) = 0
        WHERE (p.user_id = ? OR pm.member_user_id IS NOT NULL)
          AND COALESCE(p.is_deleted, 0) = 0
    """

def find_user_by_identifier(cursor, identifier):
    identifier = (identifier or "").strip().lower()
    cursor.execute(
        """
        SELECT user_id, username, email, full_name, password_hash,
               COALESCE(email_verified, 1) AS email_verified,
               COALESCE(is_disabled, 0) AS is_disabled
        FROM users
        WHERE lower(username) = ?
           OR lower(COALESCE(email, '')) = ?
        """,
        (identifier, identifier),
    )
    return cursor.fetchone()


@app.get("/", response_class=HTMLResponse)
def dashboard():
    with open("templates/dashboard.html", "r", encoding="utf-8") as file:
        return file.read()


@app.get("/email-delivery/status")
def get_email_delivery_status():
    return email_delivery_status_payload()


@app.get("/auth/google/config")
def google_auth_config():
    return google_auth_status_payload()


@app.post("/auth/google")
def google_auth(payload: GoogleAuthRequest):
    google_profile = verify_google_id_token(payload.credential)
    now = current_timestamp()

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT user_id, username, email, full_name, COALESCE(is_disabled, 0) AS is_disabled
        FROM users
        WHERE google_sub = ?
        """,
        (google_profile["google_sub"],),
    )
    user = cursor.fetchone()

    if not user:
        cursor.execute(
            """
            SELECT user_id, username, email, full_name, COALESCE(is_disabled, 0) AS is_disabled
            FROM users
            WHERE lower(COALESCE(email, '')) = lower(?)
            """,
            (google_profile["email"],),
        )
        user = cursor.fetchone()

    if user:
        if int(user["is_disabled"] or 0) == 1:
            connection.close()
            raise HTTPException(status_code=403, detail="This user account has been disabled by an administrator.")
        cursor.execute(
            """
            UPDATE users
            SET google_sub = COALESCE(google_sub, ?),
                email = ?,
                full_name = COALESCE(NULLIF(full_name, ''), ?),
                avatar_url = ?,
                email_verified = 1,
                email_verified_at = COALESCE(email_verified_at, ?),
                auth_provider = CASE
                    WHEN auth_provider IS NULL OR auth_provider = '' OR auth_provider = 'password' THEN 'google_linked'
                    ELSE auth_provider
                END,
                google_linked_at = COALESCE(google_linked_at, ?),
                updated_at = ?
            WHERE user_id = ?
            """,
            (
                google_profile["google_sub"],
                google_profile["email"],
                google_profile["full_name"],
                google_profile["avatar_url"],
                now,
                now,
                now,
                user["user_id"],
            ),
        )
        user_id = user["user_id"]
        username = user["username"]
        created = False
    else:
        user_id = str(uuid.uuid4())
        username = make_unique_google_username(cursor, google_profile["email"], google_profile["full_name"])
        cursor.execute(
            """
            INSERT INTO users (
                user_id, username, email, full_name, password_hash,
                email_verified, email_verified_at, password_updated_at, updated_at,
                google_sub, auth_provider, google_linked_at, avatar_url
            ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, 'google', ?, ?)
            """,
            (
                user_id,
                username,
                google_profile["email"],
                google_profile["full_name"],
                hash_password(secrets.token_urlsafe(48)),
                now,
                now,
                now,
                google_profile["google_sub"],
                now,
                google_profile["avatar_url"],
            ),
        )
        created = True

    connection.commit()
    connection.close()

    sync_token, sync_token_expires_at = create_sync_token(user_id, username)
    return {
        "message": "Google sign-in successful." if not created else "Google account created successfully.",
        "user_id": user_id,
        "username": username,
        "email": google_profile["email"],
        "full_name": google_profile["full_name"],
        "avatar_url": google_profile["avatar_url"],
        "email_verified": True,
        "auth_provider": "google" if created else "google_linked",
        "created": created,
        "sync_token": sync_token,
        "sync_token_expires_at": sync_token_expires_at,
    }


@app.post("/register")
def register_user(user: RegisterRequest):
    email = normalize_email(user.email) if user.email else None
    full_name = (user.full_name or "").strip() or None
    now = current_timestamp()

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT user_id FROM users
        WHERE lower(username) = lower(?)
           OR (? IS NOT NULL AND lower(COALESCE(email, '')) = lower(?))
        """,
        (user.username, email, email),
    )
    if cursor.fetchone():
        connection.close()
        raise HTTPException(status_code=409, detail="Username or email already exists.")

    new_user_id = str(uuid.uuid4())
    email_verified = 0 if email else 1
    email_verified_at = None if email else now

    cursor.execute(
        """
        INSERT INTO users (
            user_id, username, email, full_name, password_hash,
            email_verified, email_verified_at, password_updated_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_user_id,
            user.username,
            email,
            full_name,
            hash_password(user.password),
            email_verified,
            email_verified_at,
            now,
            now,
        ),
    )

    if email:
        verification_code, expires_at = create_email_verification_code(cursor, new_user_id, email)
        connection.commit()
        connection.close()
        delivery = send_verification_code(email, user.username, verification_code)
        if not delivery.get("sent") and EMAIL_REQUIRE_SMTP and not EMAIL_ALLOW_DEVELOPMENT_CODE:
            raise HTTPException(
                status_code=503,
                detail=(
                    delivery.get("message")
                    or "Verification email could not be sent. Configure SMTP and try Resend Code."
                ),
            )

        response = {
            "message": "Account created. A 4-digit verification code has been sent to your personal email address.",
            "verification_required": True,
            "user_id": new_user_id,
            "username": user.username,
            "email": email,
            "email_sent": delivery.get("sent", False),
            "email_delivery": delivery.get("delivery"),
            "delivery_message": delivery.get("message"),
            "verification_code_expires_at": expires_at,
            "expires_in_minutes": int(EMAIL_VERIFICATION_TTL_SECONDS / 60),
        }
        if not delivery.get("sent") and EMAIL_ALLOW_DEVELOPMENT_CODE:
            response["development_verification_code"] = verification_code
        return response

    connection.commit()
    connection.close()
    sync_token, sync_token_expires_at = create_sync_token(new_user_id, user.username)
    return {
        "message": "Account created successfully.",
        "verification_required": False,
        "user_id": new_user_id,
        "username": user.username,
        "email": email,
        "sync_token": sync_token,
        "sync_token_expires_at": sync_token_expires_at,
    }


@app.post("/login")
def login_user(user: LoginRequest):
    connection = get_connection()
    cursor = connection.cursor()
    existing_user = find_user_by_identifier(cursor, user.username)
    connection.close()

    if not existing_user or not verify_password(user.password, existing_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username/email or password.")
    if int(existing_user["is_disabled"] or 0) == 1:
        raise HTTPException(status_code=403, detail="This user account has been disabled by an administrator.")
    if existing_user["email"] and int(existing_user["email_verified"] or 0) != 1:
        raise HTTPException(
            status_code=403,
            detail="Email verification is required before login. Use the verification code sent to your email.",
        )

    sync_token, sync_token_expires_at = create_sync_token(
        existing_user["user_id"],
        existing_user["username"],
    )
    return {
        "message": "Login successful.",
        "user_id": existing_user["user_id"],
        "username": existing_user["username"],
        "email": existing_user["email"],
        "email_verified": True,
        "sync_token": sync_token,
        "sync_token_expires_at": sync_token_expires_at,
    }


@app.post("/email-verification/resend")
def resend_email_verification(payload: EmailVerificationRequest):
    connection = get_connection()
    cursor = connection.cursor()
    user = find_user_by_identifier(cursor, payload.username_or_email)
    if not user:
        connection.close()
        raise HTTPException(status_code=404, detail="Account not found.")
    if int(user["is_disabled"] or 0) == 1:
        connection.close()
        raise HTTPException(status_code=403, detail="This account has been disabled.")
    if not user["email"]:
        connection.close()
        raise HTTPException(status_code=400, detail="This account does not have an email address to verify.")
    if int(user["email_verified"] or 0) == 1:
        connection.close()
        return {"message": "Email is already verified.", "already_verified": True}

    verification_code, expires_at = create_email_verification_code(cursor, user["user_id"], user["email"])
    connection.commit()
    connection.close()
    delivery = send_verification_code(user["email"], user["username"], verification_code)
    if not delivery.get("sent") and EMAIL_REQUIRE_SMTP and not EMAIL_ALLOW_DEVELOPMENT_CODE:
        raise HTTPException(
            status_code=503,
            detail=(
                delivery.get("message")
                or "Verification email could not be sent. Configure SMTP and try again."
            ),
        )

    response = {
        "message": "A new 4-digit verification code has been sent to your personal email address.",
        "username": user["username"],
        "email": user["email"],
        "email_sent": delivery.get("sent", False),
        "email_delivery": delivery.get("delivery"),
        "delivery_message": delivery.get("message"),
        "verification_code_expires_at": expires_at,
        "expires_in_minutes": int(EMAIL_VERIFICATION_TTL_SECONDS / 60),
    }
    if not delivery.get("sent") and EMAIL_ALLOW_DEVELOPMENT_CODE:
        response["development_verification_code"] = verification_code
    return response


@app.post("/email-verification/confirm")
def confirm_email_verification(payload: EmailVerificationConfirm):
    identifier = payload.username_or_email.strip().lower()
    code = payload.code.strip()
    now = datetime.now()

    connection = get_connection()
    cursor = connection.cursor()
    user = find_user_by_identifier(cursor, identifier)
    if not user:
        connection.close()
        raise HTTPException(status_code=404, detail="Account not found.")
    if int(user["is_disabled"] or 0) == 1:
        connection.close()
        raise HTTPException(status_code=403, detail="This account has been disabled.")
    if not user["email"]:
        connection.close()
        raise HTTPException(status_code=400, detail="This account does not have an email address to verify.")
    if int(user["email_verified"] or 0) == 1:
        connection.close()
        sync_token, sync_token_expires_at = create_sync_token(user["user_id"], user["username"])
        return {
            "message": "Email is already verified.",
            "already_verified": True,
            "user_id": user["user_id"],
            "username": user["username"],
            "email": user["email"],
            "sync_token": sync_token,
            "sync_token_expires_at": sync_token_expires_at,
        }

    cursor.execute(
        """
        SELECT id, expires_at, used_at, attempts
        FROM email_verification_codes
        WHERE user_id = ?
          AND email = ?
          AND code_hash = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (user["user_id"], user["email"], hash_token(code)),
    )
    record = cursor.fetchone()

    if not record or record["used_at"]:
        cursor.execute(
            "UPDATE email_verification_codes SET attempts = attempts + 1 WHERE user_id = ? AND used_at IS NULL",
            (user["user_id"],),
        )
        connection.commit()
        connection.close()
        raise HTTPException(status_code=400, detail="Verification code is invalid.")

    try:
        expires_at = datetime.fromisoformat(record["expires_at"])
    except (TypeError, ValueError):
        expires_at = now

    if expires_at <= now:
        cursor.execute(
            "UPDATE email_verification_codes SET used_at = ? WHERE id = ?",
            (now.isoformat(), record["id"]),
        )
        connection.commit()
        connection.close()
        raise HTTPException(status_code=400, detail="Verification code has expired. Request a new code.")

    verified_at = now.isoformat()
    cursor.execute(
        """
        UPDATE users
        SET email_verified = 1, email_verified_at = ?, updated_at = ?
        WHERE user_id = ?
        """,
        (verified_at, verified_at, user["user_id"]),
    )
    cursor.execute(
        "UPDATE email_verification_codes SET used_at = ? WHERE id = ?",
        (verified_at, record["id"]),
    )
    connection.commit()
    connection.close()

    sync_token, sync_token_expires_at = create_sync_token(user["user_id"], user["username"])
    return {
        "message": "Email verified successfully. You can now log in.",
        "verified": True,
        "user_id": user["user_id"],
        "username": user["username"],
        "email": user["email"],
        "email_verified_at": verified_at,
        "sync_token": sync_token,
        "sync_token_expires_at": sync_token_expires_at,
    }


@app.post("/password-reset/request")
def request_password_reset(payload: PasswordResetRequest):
    username = payload.username.strip()
    generic_message = (
        "If this account exists and is active, a password reset token has been created."
    )

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT user_id, username, email, COALESCE(is_disabled, 0) AS is_disabled
        FROM users
        WHERE lower(username) = lower(?)
           OR lower(COALESCE(email, '')) = lower(?)
        """,
        (username, username),
    )
    user = cursor.fetchone()

    if not user or int(user["is_disabled"] or 0) == 1:
        connection.close()
        return {
            "message": generic_message,
            "development_reset_token": None,
            "reset_token_expires_at": None,
        }

    reset_token, expires_at = create_password_reset_token(
        cursor,
        user["user_id"],
        user["username"],
    )
    connection.commit()
    connection.close()

    delivery = None
    if user["email"]:
        delivery = send_password_reset_email(user["email"], user["username"], reset_token)

    if delivery and not delivery.get("sent") and EMAIL_REQUIRE_SMTP and not EMAIL_ALLOW_DEVELOPMENT_CODE:
        raise HTTPException(
            status_code=503,
            detail=(
                delivery.get("message")
                or "Password reset email could not be sent. Configure SMTP and try again."
            ),
        )

    response = {
        "message": (
            "Password reset email sent to the account email address."
            if delivery and delivery.get("sent")
            else "Password reset token created."
        ),
        "username": user["username"],
        "email_sent": bool(delivery and delivery.get("sent")),
        "email_delivery": delivery.get("delivery") if delivery else "no_email_on_account",
        "reset_token_expires_at": expires_at,
        "expires_in_minutes": int(PASSWORD_RESET_TTL_SECONDS / 60),
    }
    if EMAIL_ALLOW_DEVELOPMENT_CODE or not user["email"]:
        response["development_reset_token"] = reset_token
    else:
        response["development_reset_token"] = None
    return response


@app.post("/password-reset/confirm")
def confirm_password_reset(payload: PasswordResetConfirm):
    reset_token = payload.token.strip()
    now = datetime.now()

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT prt.id, prt.user_id, prt.username, prt.expires_at, prt.used_at,
               COALESCE(u.is_disabled, 0) AS is_disabled
        FROM password_reset_tokens prt
        JOIN users u ON u.user_id = prt.user_id
        WHERE prt.token_hash = ?
        """,
        (hash_token(reset_token),),
    )
    record = cursor.fetchone()

    if not record or record["used_at"]:
        connection.close()
        raise HTTPException(status_code=400, detail="Reset token is invalid or has already been used.")

    try:
        expires_at = datetime.fromisoformat(record["expires_at"])
    except (TypeError, ValueError):
        expires_at = now

    if expires_at <= now:
        cursor.execute(
            "UPDATE password_reset_tokens SET used_at = ? WHERE id = ?",
            (now.isoformat(), record["id"]),
        )
        connection.commit()
        connection.close()
        raise HTTPException(status_code=400, detail="Reset token has expired. Request a new one.")

    if int(record["is_disabled"] or 0) == 1:
        connection.close()
        raise HTTPException(status_code=403, detail="This user account has been disabled by an administrator.")

    password_updated_at = now.isoformat()
    cursor.execute(
        """
        UPDATE users
        SET password_hash = ?, password_updated_at = ?, updated_at = ?
        WHERE user_id = ?
        """,
        (
            hash_password(payload.new_password),
            password_updated_at,
            password_updated_at,
            record["user_id"],
        ),
    )
    cursor.execute(
        "UPDATE password_reset_tokens SET used_at = ? WHERE id = ?",
        (password_updated_at, record["id"]),
    )
    connection.commit()
    connection.close()

    return {
        "message": "Password reset successful. You can now log in with the new password.",
        "user_id": record["user_id"],
        "username": record["username"],
        "password_updated_at": password_updated_at,
    }


@app.get("/projects")
def get_projects(request: Request, user_id: Optional[str] = None):
    authenticated_user = require_sync_auth(request)
    user_id = authenticated_user["user_id"]
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(shared_project_select_sql(include_deleted=False), (user_id, user_id, user_id, user_id))
    projects = [dict(row) for row in cursor.fetchall()]
    connection.close()
    return projects


@app.get("/sync/projects")
def get_sync_projects(request: Request, user_id: Optional[str] = None):
    authenticated_user = require_sync_auth(request)
    user_id = authenticated_user["user_id"]
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(shared_project_select_sql(include_deleted=True), (user_id, user_id, user_id, user_id))
    projects = [dict(row) for row in cursor.fetchall()]
    connection.close()
    return projects


def conflict_detail(existing_project):
    return {
        "message": "Version conflict detected.",
        "status": "conflict",
        "server_project": {
            "project_uuid": existing_project["project_uuid"],
            "user_id": existing_project["user_id"],
            "name": existing_project["name"],
            "location": existing_project["location"],
            "progress": existing_project["progress"],
            "is_deleted": existing_project["is_deleted"],
            "deleted_at": existing_project["deleted_at"],
            "version": existing_project["version"],
            "updated_at": existing_project["updated_at"],
        },
    }


@app.post("/projects")
def receive_project(project: Project, request: Request):
    authenticated_user = require_sync_auth(request)
    auth_user_id = authenticated_user["user_id"]
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT project_uuid, user_id, name, location, progress,
               is_deleted, deleted_at, version, updated_at
        FROM projects WHERE project_uuid = ?
        """,
        (project.project_uuid,),
    )
    existing = cursor.fetchone()
    now = current_timestamp()

    if not existing:
        # Only the authenticated creator can create a new owned project.
        require_payload_owner(project.user_id, auth_user_id)
        deleted_at = project.deleted_at or (now if project.is_deleted else None)
        cursor.execute(
            """
            INSERT INTO projects (
                project_uuid, user_id, name, location, progress, sync_status,
                is_deleted, deleted_at, version, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'SYNCED', ?, ?, 1, ?)
            """,
            (
                project.project_uuid, project.user_id, project.name, project.location,
                project.progress, project.is_deleted, deleted_at, now,
            ),
        )
        connection.commit()
        connection.close()
        return {
            "message": "Project tombstone saved." if project.is_deleted else "Project saved successfully.",
            "project_uuid": project.project_uuid,
            "status": "deleted" if project.is_deleted else "synced",
            "deleted_at": deleted_at,
            "version": 1,
            "updated_at": now,
            "access_role": "OWNER",
        }

    if existing["user_id"] != project.user_id:
        connection.close()
        raise HTTPException(status_code=403, detail="Project owner mismatch.")

    role = server_project_access_role(project.project_uuid, auth_user_id)
    if not role:
        connection.close()
        raise HTTPException(status_code=403, detail="You do not have access to this project.")

    server_deleted = bool(existing["is_deleted"])
    incoming_deleted = bool(project.is_deleted)
    server_version = int(existing["version"] or 1)

    if incoming_deleted and ROLE_LEVELS[role] < ROLE_LEVELS["EDITOR"]:
        connection.close()
        raise HTTPException(status_code=403, detail="Editor access is required to delete this project.")

    if not incoming_deleted and ROLE_LEVELS[role] < ROLE_LEVELS["EDITOR"]:
        connection.close()
        raise HTTPException(status_code=403, detail="Editor access is required to update this project.")

    if server_deleted and not incoming_deleted:
        connection.close()
        return {
            "message": "Project was previously deleted on server.",
            "project_uuid": project.project_uuid,
            "status": "deleted_on_server",
            "deleted_at": existing["deleted_at"],
            "version": server_version,
            "updated_at": existing["updated_at"],
        }

    if server_deleted and incoming_deleted:
        connection.close()
        return {
            "message": "Project already deleted.",
            "project_uuid": project.project_uuid,
            "status": "already_deleted",
            "deleted_at": existing["deleted_at"],
            "version": server_version,
            "updated_at": existing["updated_at"],
        }

    if project.version is not None and int(project.version) != server_version:
        detail = conflict_detail(existing)
        connection.close()
        raise HTTPException(status_code=409, detail=detail)

    new_version = server_version + 1

    if incoming_deleted:
        deleted_at = project.deleted_at or now
        cursor.execute(
            """
            UPDATE projects
            SET is_deleted = 1, deleted_at = ?, sync_status = 'SYNCED',
                version = ?, updated_at = ?
            WHERE project_uuid = ? AND user_id = ?
            """,
            (deleted_at, new_version, now, project.project_uuid, project.user_id),
        )
        connection.commit()
        connection.close()
        return {
            "message": "Project deleted through synchronization.",
            "project_uuid": project.project_uuid,
            "status": "deleted",
            "deleted_at": deleted_at,
            "version": new_version,
            "updated_at": now,
        }

    unchanged = (
        existing["name"] == project.name
        and existing["location"] == project.location
        and existing["progress"] == project.progress
    )

    if unchanged:
        connection.close()
        return {
            "message": "Project already up to date.",
            "project_uuid": project.project_uuid,
            "status": "already_synced",
            "version": server_version,
            "updated_at": existing["updated_at"],
        }

    cursor.execute(
        """
        UPDATE projects
        SET name = ?, location = ?, progress = ?, sync_status = 'SYNCED',
            is_deleted = 0, deleted_at = NULL, version = ?, updated_at = ?
        WHERE project_uuid = ? AND user_id = ?
        """,
        (
            project.name, project.location, project.progress,
            new_version, now, project.project_uuid, project.user_id,
        ),
    )
    connection.commit()
    connection.close()
    return {
        "message": "Project updated successfully.",
        "project_uuid": project.project_uuid,
        "status": "updated",
        "version": new_version,
        "updated_at": now,
    }


@app.delete("/projects/{project_uuid}")
def delete_project(project_uuid: str, request: Request, user_id: Optional[str] = None):
    authenticated_user = require_sync_auth(request)
    user_id = authenticated_user["user_id"]
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT project_uuid, user_id, name, is_deleted, deleted_at,
               version, updated_at
        FROM projects WHERE project_uuid = ?
        """,
        (project_uuid,),
    )
    project = cursor.fetchone()

    if not project:
        connection.close()
        raise HTTPException(status_code=404, detail="Project not found.")
    role = server_project_access_role(project_uuid, user_id)
    if not role or ROLE_LEVELS[role] < ROLE_LEVELS["EDITOR"]:
        connection.close()
        raise HTTPException(status_code=403, detail="Editor access is required to delete this project.")
    owner_user_id = project["user_id"]
    if bool(project["is_deleted"]):
        connection.close()
        return {
            "message": "Project already deleted.",
            "project_uuid": project_uuid,
            "deleted_at": project["deleted_at"],
            "version": project["version"],
            "updated_at": project["updated_at"],
        }

    deleted_at = current_timestamp()
    new_version = int(project["version"] or 1) + 1
    cursor.execute(
        """
        UPDATE projects
        SET is_deleted = 1, deleted_at = ?, sync_status = 'SYNCED',
            version = ?, updated_at = ?
        WHERE project_uuid = ? AND user_id = ?
        """,
        (deleted_at, new_version, deleted_at, project_uuid, owner_user_id),
    )
    connection.commit()
    connection.close()
    return {
        "message": "Project deleted successfully.",
        "project_uuid": project_uuid,
        "deleted_at": deleted_at,
        "version": new_version,
        "updated_at": deleted_at,
    }


# ============================================================
# LOCAL CONFLICT RESOLUTION
#
# Conflict records live in afrisync.db because they describe a
# local unsynchronized version versus the current server copy.
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
            "version": int(row["version"] or 1),
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
        WHERE project_uuid = ? AND user_id = ? AND sync_status = 'CONFLICT'
        """,
        (project_uuid, user_id),
    )
    row = cursor.fetchone()
    connection.close()
    return row


@app.get("/conflicts")
def get_conflicts(request: Request, user_id: Optional[str] = None):
    authenticated_user = require_sync_auth(request)
    user_id = authenticated_user["user_id"]
    connection = get_local_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT project_uuid, user_id, name, location, progress,
               sync_status, is_deleted, deleted_at, version,
               updated_at, conflict_data
        FROM projects
        WHERE user_id = ? AND sync_status = 'CONFLICT'
        ORDER BY COALESCE(updated_at, '') DESC, id DESC
        """,
        (user_id,),
    )
    rows = cursor.fetchall()
    connection.close()
    return [serialize_local_conflict(row) for row in rows]


@app.get("/conflicts/{project_uuid}")
def get_conflict(project_uuid: str, request: Request, user_id: Optional[str] = None):
    authenticated_user = require_sync_auth(request)
    user_id = authenticated_user["user_id"]
    row = get_local_conflict_row(project_uuid, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Conflict not found.")
    return serialize_local_conflict(row)


@app.post("/conflicts/{project_uuid}/use-server")
def resolve_conflict_use_server(project_uuid: str, request: Request, user_id: Optional[str] = None):
    authenticated_user = require_sync_auth(request)
    user_id = authenticated_user["user_id"]
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
        SET name = ?, location = ?, progress = ?,
            is_deleted = ?, deleted_at = ?,
            version = ?, updated_at = ?,
            sync_status = 'SYNCED',
            last_sync_error = NULL,
            last_synced_at = ?,
            conflict_data = NULL
        WHERE project_uuid = ? AND user_id = ?
        """,
        (
            server_project.get("name", row["name"]),
            server_project.get("location", row["location"]),
            int(server_project.get("progress", row["progress"])),
            int(server_project.get("is_deleted", 0)),
            server_project.get("deleted_at"),
            int(server_project.get("version", row["version"] or 1)),
            server_project.get("updated_at") or current_timestamp(),
            current_timestamp(),
            project_uuid,
            user_id,
        ),
    )
    connection.commit()
    connection.close()

    return {
        "message": "Conflict resolved using the server version.",
        "project_uuid": project_uuid,
        "resolution": "server",
    }


@app.post("/conflicts/{project_uuid}/keep-local")
def resolve_conflict_keep_local(project_uuid: str, request: Request, user_id: Optional[str] = None):
    authenticated_user = require_sync_auth(request)
    user_id = authenticated_user["user_id"]
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

    # Rebase the local copy onto the server's current version. The next push
    # will only succeed if the server has not changed again in the meantime.
    server_version = int(server_project.get("version", row["version"] or 1))

    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE projects
        SET version = ?,
            sync_status = 'PENDING',
            last_sync_error = NULL,
            conflict_data = NULL,
            updated_at = ?
        WHERE project_uuid = ? AND user_id = ?
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

    sync_result = synchronize_pending_projects(user_id)

    refreshed = get_local_conflict_row(project_uuid, user_id)
    if refreshed:
        return {
            "message": "The server changed again. The conflict remains unresolved.",
            "project_uuid": project_uuid,
            "resolution": "conflict",
            "sync": sync_result,
        }

    return {
        "message": "Conflict resolved using your local version.",
        "project_uuid": project_uuid,
        "resolution": "local",
        "sync": sync_result,
    }


@app.post("/sync")
def sync_projects(request: Request, user_id: Optional[str] = None):
    authenticated_user = require_sync_auth(request)
    user_id = authenticated_user["user_id"]
    result = synchronize_pending_projects(user_id)
    return {
        "message": "Synchronization completed",
        "user_id": user_id,
        "total": result["total"],
        "successful": result["successful"],
        "failed": result["failed"],
        "conflicts": result.get("conflicts", 0),
        "pull": result.get("pull", {}),
    }



# ============================================================
# REMOTE NOTE SYNCHRONIZATION
# ============================================================

def server_note_dict(row):
    return {
        "note_uuid": row["note_uuid"],
        "project_uuid": row["project_uuid"],
        "user_id": row["user_id"],
        "content": row["content"],
        "sync_status": row["sync_status"],
        "is_deleted": int(row["is_deleted"] or 0),
        "deleted_at": row["deleted_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "version": int(row["version"] or 1),
    }


def note_conflict_detail(existing_note):
    return {
        "message": "Note version conflict detected.",
        "status": "conflict",
        "server_note": server_note_dict(existing_note),
    }


def verify_server_project_owner(project_uuid, user_id):
    # Backward-compatible name. Collaboration now allows any user with view access.
    require_server_project_permission(project_uuid, user_id, "VIEWER")


@app.get("/sync/notes")
def get_sync_notes(request: Request, user_id: Optional[str] = None):
    authenticated_user = require_sync_auth(request)
    user_id = authenticated_user["user_id"]
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        f"""
        SELECT note_uuid, project_uuid, user_id, content, sync_status,
               is_deleted, deleted_at, created_at, updated_at, version
        FROM project_notes
        WHERE project_uuid IN ({accessible_project_ids_subquery()})
        ORDER BY id
        """,
        (user_id, user_id),
    )
    notes = [server_note_dict(row) for row in cursor.fetchall()]
    connection.close()
    return notes


@app.post("/sync/notes")
def receive_note(note: SyncNote, request: Request):
    authenticated_user = require_sync_auth(request)
    require_payload_owner(note.user_id, authenticated_user["user_id"])
    require_server_project_permission(note.project_uuid, authenticated_user["user_id"], "EDITOR")

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT note_uuid, project_uuid, user_id, content, sync_status,
               is_deleted, deleted_at, created_at, updated_at, version
        FROM project_notes
        WHERE note_uuid = ?
        """,
        (note.note_uuid,),
    )
    existing = cursor.fetchone()
    now = current_timestamp()
    created_at = note.created_at or now
    updated_at = note.updated_at or now
    deleted_at = note.deleted_at or (now if note.is_deleted else None)

    if not existing:
        cursor.execute(
            """
            INSERT INTO project_notes (
                note_uuid, project_uuid, user_id, content, sync_status,
                is_deleted, deleted_at, created_at, updated_at, version
            ) VALUES (?, ?, ?, ?, 'SYNCED', ?, ?, ?, ?, 1)
            """,
            (
                note.note_uuid,
                note.project_uuid,
                note.user_id,
                note.content,
                int(note.is_deleted or 0),
                deleted_at,
                created_at,
                now,
            ),
        )
        connection.commit()
        connection.close()
        return {
            "message": "Note tombstone saved." if note.is_deleted else "Note saved successfully.",
            "note_uuid": note.note_uuid,
            "project_uuid": note.project_uuid,
            "status": "deleted" if note.is_deleted else "synced",
            "deleted_at": deleted_at,
            "version": 1,
            "updated_at": now,
        }

    if existing["user_id"] != note.user_id:
        connection.close()
        raise HTTPException(status_code=403, detail="You do not have permission to modify this note.")

    server_version = int(existing["version"] or 1)
    incoming_deleted = bool(note.is_deleted)
    server_deleted = bool(existing["is_deleted"])

    if note.version is not None and int(note.version) != server_version:
        detail = note_conflict_detail(existing)
        connection.close()
        raise HTTPException(status_code=409, detail=detail)

    if server_deleted and incoming_deleted:
        connection.close()
        return {
            "message": "Note already deleted.",
            "note_uuid": note.note_uuid,
            "project_uuid": note.project_uuid,
            "status": "already_deleted",
            "deleted_at": existing["deleted_at"],
            "version": server_version,
            "updated_at": existing["updated_at"],
        }

    unchanged = (
        existing["content"] == note.content
        and int(existing["is_deleted"] or 0) == int(note.is_deleted or 0)
    )
    if unchanged:
        connection.close()
        return {
            "message": "Note already up to date.",
            "note_uuid": note.note_uuid,
            "project_uuid": note.project_uuid,
            "status": "already_synced",
            "deleted_at": existing["deleted_at"],
            "version": server_version,
            "updated_at": existing["updated_at"],
        }

    new_version = server_version + 1

    if incoming_deleted:
        cursor.execute(
            """
            UPDATE project_notes
            SET is_deleted = 1,
                deleted_at = ?,
                sync_status = 'SYNCED',
                version = ?,
                updated_at = ?
            WHERE note_uuid = ?
              AND user_id = ?
            """,
            (deleted_at or now, new_version, now, note.note_uuid, note.user_id),
        )
        connection.commit()
        connection.close()
        return {
            "message": "Note deleted through synchronization.",
            "note_uuid": note.note_uuid,
            "project_uuid": note.project_uuid,
            "status": "deleted",
            "deleted_at": deleted_at or now,
            "version": new_version,
            "updated_at": now,
        }

    cursor.execute(
        """
        UPDATE project_notes
        SET content = ?,
            is_deleted = 0,
            deleted_at = NULL,
            sync_status = 'SYNCED',
            version = ?,
            updated_at = ?
        WHERE note_uuid = ?
          AND user_id = ?
        """,
        (note.content, new_version, now, note.note_uuid, note.user_id),
    )
    connection.commit()
    connection.close()
    return {
        "message": "Note updated successfully.",
        "note_uuid": note.note_uuid,
        "project_uuid": note.project_uuid,
        "status": "updated",
        "version": new_version,
        "updated_at": now,
    }



# ============================================================
# REMOTE ATTACHMENT SYNCHRONIZATION
# ============================================================

def server_attachment_dict(row, include_content=False):
    payload = {
        "attachment_uuid": row["attachment_uuid"],
        "project_uuid": row["project_uuid"],
        "user_id": row["user_id"],
        "original_file_name": row["original_file_name"],
        "file_type": row["file_type"] or "application/octet-stream",
        "file_size": int(row["file_size"] or 0),
        "sync_status": row["sync_status"],
        "is_deleted": int(row["is_deleted"] or 0),
        "deleted_at": row["deleted_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "version": int(row["version"] or 1),
    }

    if include_content and int(row["is_deleted"] or 0) == 0:
        payload["file_content"] = encode_file_to_base64(row["file_path"])
    else:
        payload["file_content"] = None

    return payload


def attachment_conflict_detail(existing_attachment):
    return {
        "message": "Attachment version conflict detected.",
        "status": "conflict",
        "server_attachment": server_attachment_dict(existing_attachment, include_content=True),
    }


@app.get("/sync/attachments")
def get_sync_attachments(request: Request, user_id: Optional[str] = None):
    authenticated_user = require_sync_auth(request)
    user_id = authenticated_user["user_id"]
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        f"""
        SELECT attachment_uuid, project_uuid, user_id,
               original_file_name, stored_file_name, file_path,
               file_type, file_size, sync_status,
               is_deleted, deleted_at, created_at,
               updated_at, version
        FROM project_attachments
        WHERE project_uuid IN ({accessible_project_ids_subquery()})
        ORDER BY id
        """,
        (user_id, user_id),
    )
    attachments = [server_attachment_dict(row, include_content=True) for row in cursor.fetchall()]
    connection.close()
    return attachments


@app.post("/sync/attachments")
def receive_attachment(attachment: SyncAttachment, request: Request):
    authenticated_user = require_sync_auth(request)
    require_payload_owner(attachment.user_id, authenticated_user["user_id"])
    require_server_project_permission(attachment.project_uuid, authenticated_user["user_id"], "EDITOR")

    file_bytes = b""
    if not attachment.is_deleted:
        file_bytes = decode_base64_file(attachment.file_content or "")
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Attachment file content is required for active attachments.")
        if len(file_bytes) > MAX_ATTACHMENT_BYTES:
            raise HTTPException(status_code=413, detail="Attachment is too large for this version.")

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT attachment_uuid, project_uuid, user_id,
               original_file_name, stored_file_name, file_path,
               file_type, file_size, sync_status,
               is_deleted, deleted_at, created_at,
               updated_at, version
        FROM project_attachments
        WHERE attachment_uuid = ?
        """,
        (attachment.attachment_uuid,),
    )
    existing = cursor.fetchone()
    now = current_timestamp()
    created_at = attachment.created_at or now
    deleted_at = attachment.deleted_at or (now if attachment.is_deleted else None)
    safe_name = clean_file_name(attachment.original_file_name)
    file_type = (attachment.file_type or "application/octet-stream").strip() or "application/octet-stream"
    file_size = int(attachment.file_size or len(file_bytes) or 0)

    saved_path = ""
    stored_file_name = ""
    if not attachment.is_deleted:
        stored_file_name = f"{attachment.attachment_uuid}_{safe_name}"
        attachment_folder = get_server_attachment_folder(attachment.user_id, attachment.project_uuid)
        saved_path_obj = attachment_folder / stored_file_name
        try:
            saved_path_obj.write_bytes(file_bytes)
        except OSError as error:
            connection.close()
            raise HTTPException(status_code=500, detail=f"Unable to save attachment on server: {error}")
        saved_path = str(saved_path_obj)
        file_size = len(file_bytes)

    if not existing:
        cursor.execute(
            """
            INSERT INTO project_attachments (
                attachment_uuid, project_uuid, user_id,
                original_file_name, stored_file_name, file_path,
                file_type, file_size, sync_status,
                is_deleted, deleted_at, created_at,
                updated_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'SYNCED', ?, ?, ?, ?, 1)
            """,
            (
                attachment.attachment_uuid,
                attachment.project_uuid,
                attachment.user_id,
                safe_name,
                stored_file_name,
                saved_path,
                file_type,
                file_size,
                int(attachment.is_deleted or 0),
                deleted_at,
                created_at,
                now,
            ),
        )
        connection.commit()
        connection.close()
        return {
            "message": "Attachment tombstone saved." if attachment.is_deleted else "Attachment saved successfully.",
            "attachment_uuid": attachment.attachment_uuid,
            "project_uuid": attachment.project_uuid,
            "status": "deleted" if attachment.is_deleted else "synced",
            "deleted_at": deleted_at,
            "version": 1,
            "updated_at": now,
        }

    if existing["user_id"] != attachment.user_id:
        connection.close()
        raise HTTPException(status_code=403, detail="You do not have permission to modify this attachment.")

    server_version = int(existing["version"] or 1)
    incoming_deleted = bool(attachment.is_deleted)
    server_deleted = bool(existing["is_deleted"])

    if attachment.version is not None and int(attachment.version) != server_version:
        detail = attachment_conflict_detail(existing)
        connection.close()
        raise HTTPException(status_code=409, detail=detail)

    if server_deleted and incoming_deleted:
        connection.close()
        return {
            "message": "Attachment already deleted.",
            "attachment_uuid": attachment.attachment_uuid,
            "project_uuid": attachment.project_uuid,
            "status": "already_deleted",
            "deleted_at": existing["deleted_at"],
            "version": server_version,
            "updated_at": existing["updated_at"],
        }

    unchanged = (
        existing["original_file_name"] == safe_name
        and int(existing["file_size"] or 0) == file_size
        and (existing["file_type"] or "application/octet-stream") == file_type
        and int(existing["is_deleted"] or 0) == int(attachment.is_deleted or 0)
    )
    if unchanged:
        connection.close()
        return {
            "message": "Attachment already up to date.",
            "attachment_uuid": attachment.attachment_uuid,
            "project_uuid": attachment.project_uuid,
            "status": "already_synced",
            "deleted_at": existing["deleted_at"],
            "version": server_version,
            "updated_at": existing["updated_at"],
        }

    new_version = server_version + 1

    if incoming_deleted:
        cursor.execute(
            """
            UPDATE project_attachments
            SET is_deleted = 1,
                deleted_at = ?,
                sync_status = 'SYNCED',
                version = ?,
                updated_at = ?
            WHERE attachment_uuid = ?
              AND user_id = ?
            """,
            (deleted_at or now, new_version, now, attachment.attachment_uuid, attachment.user_id),
        )
        connection.commit()
        connection.close()
        return {
            "message": "Attachment deleted through synchronization.",
            "attachment_uuid": attachment.attachment_uuid,
            "project_uuid": attachment.project_uuid,
            "status": "deleted",
            "deleted_at": deleted_at or now,
            "version": new_version,
            "updated_at": now,
        }

    cursor.execute(
        """
        UPDATE project_attachments
        SET original_file_name = ?,
            stored_file_name = ?,
            file_path = ?,
            file_type = ?,
            file_size = ?,
            is_deleted = 0,
            deleted_at = NULL,
            sync_status = 'SYNCED',
            version = ?,
            updated_at = ?
        WHERE attachment_uuid = ?
          AND user_id = ?
        """,
        (
            safe_name,
            stored_file_name,
            saved_path,
            file_type,
            file_size,
            new_version,
            now,
            attachment.attachment_uuid,
            attachment.user_id,
        ),
    )
    connection.commit()
    connection.close()
    return {
        "message": "Attachment updated successfully.",
        "attachment_uuid": attachment.attachment_uuid,
        "project_uuid": attachment.project_uuid,
        "status": "updated",
        "version": new_version,
        "updated_at": now,
    }



# ============================================================
# TEAM COLLABORATION ENDPOINTS
# ============================================================

@app.get("/sync/members")
def get_sync_members(request: Request):
    authenticated_user = require_sync_auth(request)
    user_id = authenticated_user["user_id"]
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT pm.project_uuid, pm.owner_user_id, pm.member_user_id,
               pm.member_username, pm.role, pm.is_deleted,
               pm.invited_at, pm.updated_at,
               owner.username AS owner_username
        FROM project_members pm
        LEFT JOIN users owner ON owner.user_id = pm.owner_user_id
        WHERE pm.owner_user_id = ? OR pm.member_user_id = ?
        ORDER BY pm.updated_at DESC, pm.id DESC
        """,
        (user_id, user_id),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    connection.close()
    return rows


@app.get("/team/projects/{project_uuid}/members")
def get_project_members(project_uuid: str, request: Request):
    authenticated_user = require_sync_auth(request)
    user_id = authenticated_user["user_id"]
    require_server_project_permission(project_uuid, user_id, "VIEWER")
    owner = get_project_owner_row(project_uuid)
    connection = get_connection()
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
    result = []
    if owner:
        result.append({
            "project_uuid": project_uuid,
            "owner_user_id": owner["owner_user_id"],
            "member_user_id": owner["owner_user_id"],
            "member_username": owner["owner_username"] or owner["owner_user_id"],
            "role": "OWNER",
            "is_deleted": 0,
            "invited_at": None,
            "updated_at": None,
        })
    result.extend(members)
    return result


@app.post("/team/projects/{project_uuid}/members")
def invite_project_member(project_uuid: str, invite: ProjectInviteRequest, request: Request):
    authenticated_user = require_sync_auth(request)
    owner_user_id = authenticated_user["user_id"]
    require_server_project_permission(project_uuid, owner_user_id, "OWNER")
    target = get_user_by_username(invite.username)
    if not target:
        raise HTTPException(status_code=404, detail="No AfriSync account exists with that username.")
    if target["user_id"] == owner_user_id:
        raise HTTPException(status_code=400, detail="The project owner is already a member.")
    role = normalize_role(invite.role)
    now = current_timestamp()
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO project_members (
            project_uuid, owner_user_id, member_user_id, member_username,
            role, is_deleted, invited_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 0, ?, ?)
        ON CONFLICT(project_uuid, member_user_id) DO UPDATE SET
            owner_user_id = excluded.owner_user_id,
            member_username = excluded.member_username,
            role = excluded.role,
            is_deleted = 0,
            updated_at = excluded.updated_at
        """,
        (
            project_uuid,
            owner_user_id,
            target["user_id"],
            target["username"],
            role,
            now,
            now,
        ),
    )
    connection.commit()
    connection.close()
    return {
        "message": f"{target['username']} was added as {role.title()}.",
        "project_uuid": project_uuid,
        "owner_user_id": owner_user_id,
        "member_user_id": target["user_id"],
        "member_username": target["username"],
        "role": role,
        "is_deleted": 0,
        "invited_at": now,
        "updated_at": now,
    }


@app.put("/team/projects/{project_uuid}/members/{member_user_id}")
def update_project_member_role(
    project_uuid: str,
    member_user_id: str,
    role_update: ProjectRoleUpdateRequest,
    request: Request,
):
    authenticated_user = require_sync_auth(request)
    owner_user_id = authenticated_user["user_id"]
    require_server_project_permission(project_uuid, owner_user_id, "OWNER")

    if member_user_id == owner_user_id:
        raise HTTPException(status_code=400, detail="The owner's role cannot be changed.")

    new_role = normalize_role(role_update.role)
    now = current_timestamp()

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE project_members
        SET role = ?,
            is_deleted = 0,
            updated_at = ?
        WHERE project_uuid = ?
          AND owner_user_id = ?
          AND member_user_id = ?
        """,
        (new_role, now, project_uuid, owner_user_id, member_user_id),
    )
    changed = cursor.rowcount

    cursor.execute(
        """
        SELECT project_uuid, owner_user_id, member_user_id,
               member_username, role, is_deleted, invited_at, updated_at
        FROM project_members
        WHERE project_uuid = ?
          AND owner_user_id = ?
          AND member_user_id = ?
        """,
        (project_uuid, owner_user_id, member_user_id),
    )
    member = cursor.fetchone()
    connection.commit()
    connection.close()

    if not changed or not member:
        raise HTTPException(status_code=404, detail="Project member was not found.")

    data = dict(member)
    data["message"] = f"{data['member_username']} is now {new_role.title()}."
    return data


@app.delete("/team/projects/{project_uuid}/members/{member_user_id}")
def remove_project_member(project_uuid: str, member_user_id: str, request: Request):
    authenticated_user = require_sync_auth(request)
    owner_user_id = authenticated_user["user_id"]
    require_server_project_permission(project_uuid, owner_user_id, "OWNER")
    if member_user_id == owner_user_id:
        raise HTTPException(status_code=400, detail="The owner cannot remove themselves from their own project.")
    now = current_timestamp()
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE project_members
        SET is_deleted = 1,
            updated_at = ?
        WHERE project_uuid = ?
          AND owner_user_id = ?
          AND member_user_id = ?
        """,
        (now, project_uuid, owner_user_id, member_user_id),
    )
    changed = cursor.rowcount
    connection.commit()
    connection.close()
    if not changed:
        raise HTTPException(status_code=404, detail="Project member was not found.")
    return {
        "message": "Project member removed.",
        "project_uuid": project_uuid,
        "member_user_id": member_user_id,
        "is_deleted": 1,
        "updated_at": now,
    }



# ============================================================
# PRODUCTION / DEPLOYMENT HEALTH CHECK
# ============================================================

@app.get("/health")
def health():
    """Small health endpoint for deployment platforms and monitoring."""
    stats = {}
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        for table_name in [
            "users",
            "projects",
            "project_notes",
            "project_attachments",
            "project_members",
            "sync_tokens",
            "password_reset_tokens",
            "email_verification_codes",
        ]:
            try:
                cursor.execute(f"SELECT COUNT(*) AS total FROM {table_name}")
                row = cursor.fetchone()
                stats[table_name] = int(row["total"] if row else 0)
            except Exception:
                stats[table_name] = None
        database_ok = True
    except Exception as error:
        database_ok = False
        stats["database_error"] = str(error)
    finally:
        if connection:
            connection.close()

    return {
        "status": "online" if database_ok else "degraded",
        "service": "AfriSync Remote Server",
        "database_ok": database_ok,
        "database_backend": get_database_backend(),
        "sqlite_database": SERVER_DATABASE,
        "server_upload_root": str(SERVER_UPLOAD_ROOT),
        "smtp_configured": bool(SMTP_USERNAME and SMTP_PASSWORD and SMTP_FROM_EMAIL),
        "google_oauth_configured": bool(GOOGLE_OAUTH_CLIENT_ID),
        "email_requires_smtp": EMAIL_REQUIRE_SMTP,
        "development_code_enabled": EMAIL_ALLOW_DEVELOPMENT_CODE,
        "generated_at": current_timestamp(),
        "stats": stats,
    }

# AFRISYNC_DEVELOPER_PLATFORM_V1
from developer_api import register_developer_api
register_developer_api(app, get_connection, current_timestamp, require_sync_auth)

