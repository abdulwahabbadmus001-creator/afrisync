import base64
import binascii
import json
import os
import re
from datetime import datetime
from pathlib import Path

import requests

from app.database import get_local_connection
from pull_sync import pull_projects

SERVER_BASE_URL = os.getenv("AFRISYNC_REMOTE_URL", "http://127.0.0.1:8000").rstrip("/")
PROJECTS_URL = f"{SERVER_BASE_URL}/projects"
NOTES_URL = f"{SERVER_BASE_URL}/sync/notes"
ATTACHMENTS_URL = f"{SERVER_BASE_URL}/sync/attachments"
MEMBERS_URL = f"{SERVER_BASE_URL}/sync/members"
UPLOAD_ROOT = Path(os.getenv("AFRISYNC_UPLOAD_ROOT", "uploads"))
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


def current_timestamp():
    return datetime.now().isoformat()


def column_exists(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return any(row[1] == column_name for row in cursor.fetchall())


def clean_file_name(file_name):
    name = Path(file_name or "attachment").name.strip()
    if not name:
        name = "attachment"
    name = re.sub(r"[^A-Za-z0-9À-ÖØ-öø-ÿ._ ()'-]+", "_", name)
    name = name.strip(" ._")
    if not name:
        name = "attachment"
    return name[:180]


def get_attachment_folder(user_id, project_uuid):
    safe_user_id = clean_file_name(user_id)
    safe_project_uuid = clean_file_name(project_uuid)
    folder = UPLOAD_ROOT / safe_user_id / safe_project_uuid
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def encode_file_to_base64(file_path):
    try:
        path = Path(file_path)
        if not path.is_file():
            return None
        return base64.b64encode(path.read_bytes()).decode("utf-8")
    except OSError:
        return None


def decode_base64_file(file_content):
    if not file_content:
        return b""
    content = file_content.strip()
    if content.startswith("data:") and "," in content:
        content = content.split(",", 1)[1]
    try:
        return base64.b64decode(content, validate=True)
    except (binascii.Error, ValueError):
        return b""


# ============================================================
# REMOTE API TOKEN SUPPORT
# ============================================================


class SyncAuthenticationError(Exception):
    pass


def ensure_remote_token_schema():
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
    connection.commit()
    connection.close()


def get_remote_sync_token(user_id):
    if not user_id:
        return None
    ensure_remote_token_schema()
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
    if not row:
        return None
    return row[0]


def get_sync_auth_headers(user_id):
    token = get_remote_sync_token(user_id)
    if not token:
        raise SyncAuthenticationError(
            "Remote sync token is missing. Log in while the remote server is running."
        )
    return {"Authorization": f"Bearer {token}"}


def count_pending_items(user_id=None):
    ensure_local_note_schema()
    ensure_local_attachment_schema()
    connection = get_local_connection()
    cursor = connection.cursor()
    total = 0
    for table_name in ("projects", "project_notes", "project_attachments"):
        query = f"SELECT COUNT(*) FROM {table_name} WHERE sync_status = 'PENDING'"
        params = ()
        if user_id:
            query += " AND user_id = ?"
            params = (user_id,)
        try:
            cursor.execute(query, params)
            total += int(cursor.fetchone()[0] or 0)
        except Exception:
            pass
    connection.close()
    return total


def ensure_local_note_schema():
    """
    Keep the local note table compatible with remote note synchronization.
    Older AfriSync versions had notes that were local-only. This migration
    adds the sync fields and converts LOCAL notes into PENDING notes.
    """
    connection = get_local_connection()
    cursor = connection.cursor()
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

    additions = [
        ("sync_attempts", "INTEGER DEFAULT 0"),
        ("last_sync_attempt", "TEXT"),
        ("last_sync_error", "TEXT"),
        ("last_synced_at", "TEXT"),
        ("version", "INTEGER DEFAULT 0"),
        ("conflict_data", "TEXT"),
    ]
    for name, definition in additions:
        if not column_exists(cursor, "project_notes", name):
            cursor.execute(f"ALTER TABLE project_notes ADD COLUMN {name} {definition}")

    cursor.execute("UPDATE project_notes SET sync_status = 'PENDING' WHERE sync_status IS NULL OR sync_status = 'LOCAL'")
    cursor.execute("UPDATE project_notes SET is_deleted = 0 WHERE is_deleted IS NULL")
    cursor.execute("UPDATE project_notes SET version = 0 WHERE version IS NULL")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_notes_sync_user ON project_notes (user_id, sync_status)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_notes_uuid_user ON project_notes (note_uuid, user_id)"
    )
    connection.commit()
    connection.close()


# ============================================================
# PROJECT SYNCHRONIZATION
# ============================================================

def get_pending_projects(user_id=None):
    connection = get_local_connection()
    cursor = connection.cursor()
    query = """
        SELECT p.project_uuid, p.user_id, p.name, p.location, p.progress,
               p.is_deleted, p.deleted_at, p.version, p.updated_at
        FROM projects p
        WHERE p.sync_status = 'PENDING'
    """
    params = ()
    if user_id:
        query += """
          AND (
              p.user_id = ?
              OR EXISTS (
                  SELECT 1
                  FROM project_members pm
                  WHERE pm.project_uuid = p.project_uuid
                    AND pm.member_user_id = ?
                    AND UPPER(COALESCE(pm.role, 'VIEWER')) = 'EDITOR'
                    AND COALESCE(pm.is_deleted, 0) = 0
              )
          )
        """
        params = (user_id, user_id)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    connection.close()
    return rows


def mark_project_sync_attempt(project_uuid):
    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE projects
        SET sync_attempts = COALESCE(sync_attempts, 0) + 1,
            last_sync_attempt = ?,
            last_sync_error = NULL
        WHERE project_uuid = ?
        """,
        (current_timestamp(), project_uuid),
    )
    connection.commit()
    connection.close()


def mark_project_sync_success(project_uuid, version=None, updated_at=None):
    connection = get_local_connection()
    cursor = connection.cursor()
    if version is None:
        cursor.execute(
            """
            UPDATE projects
            SET sync_status = 'SYNCED',
                last_sync_error = NULL,
                last_synced_at = ?,
                conflict_data = NULL
            WHERE project_uuid = ?
            """,
            (current_timestamp(), project_uuid),
        )
    else:
        cursor.execute(
            """
            UPDATE projects
            SET sync_status = 'SYNCED',
                last_sync_error = NULL,
                last_synced_at = ?,
                version = ?,
                updated_at = ?,
                conflict_data = NULL
            WHERE project_uuid = ?
            """,
            (current_timestamp(), int(version), updated_at or current_timestamp(), project_uuid),
        )
    connection.commit()
    connection.close()


def mark_project_sync_failure(project_uuid, error_message):
    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE projects
        SET sync_status = 'PENDING',
            last_sync_error = ?
        WHERE project_uuid = ?
        """,
        (error_message, project_uuid),
    )
    connection.commit()
    connection.close()


def mark_project_conflict(project_uuid, conflict_payload):
    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE projects
        SET sync_status = 'CONFLICT',
            last_sync_error = 'Version conflict: server changed since last synchronization.',
            conflict_data = ?
        WHERE project_uuid = ?
        """,
        (json.dumps(conflict_payload), project_uuid),
    )
    connection.commit()
    connection.close()


def mark_project_deleted_from_server(project_uuid, deleted_at=None, version=None, updated_at=None):
    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE projects
        SET is_deleted = 1,
            deleted_at = ?,
            sync_status = 'SYNCED',
            last_sync_error = NULL,
            last_synced_at = ?,
            version = COALESCE(?, version),
            updated_at = COALESCE(?, updated_at),
            conflict_data = NULL
        WHERE project_uuid = ?
        """,
        (
            deleted_at or current_timestamp(),
            current_timestamp(),
            version,
            updated_at or current_timestamp(),
            project_uuid,
        ),
    )
    connection.commit()
    connection.close()


def synchronize_project(project):
    (
        project_uuid,
        user_id,
        name,
        location,
        progress,
        is_deleted,
        deleted_at,
        version,
        updated_at,
    ) = project

    mark_project_sync_attempt(project_uuid)

    payload = {
        "project_uuid": project_uuid,
        "user_id": user_id,
        "name": name,
        "location": location,
        "progress": progress,
        "is_deleted": int(is_deleted or 0),
        "deleted_at": deleted_at,
        "version": int(version or 0),
        "updated_at": updated_at,
    }

    try:
        response = requests.post(PROJECTS_URL, json=payload, headers=get_sync_auth_headers(user_id), timeout=10)

        if response.status_code == 409:
            data = response.json()
            detail = data.get("detail", data)
            mark_project_conflict(project_uuid, detail)
            print(f"Project conflict detected: {name}")
            return "conflict"

        response.raise_for_status()
        data = response.json()
        status = data.get("status")

        if status == "deleted_on_server":
            mark_project_deleted_from_server(
                project_uuid,
                data.get("deleted_at"),
                data.get("version"),
                data.get("updated_at"),
            )
            return True

        if status in {"synced", "updated", "already_synced", "deleted", "already_deleted"}:
            mark_project_sync_success(project_uuid, data.get("version"), data.get("updated_at"))
            return True

        message = f"Unexpected project server response: {data}"
        mark_project_sync_failure(project_uuid, message)
        return False

    except SyncAuthenticationError as error:
        mark_project_sync_failure(project_uuid, str(error))
        return False
    except requests.RequestException as error:
        mark_project_sync_failure(project_uuid, str(error))
        return False
    except ValueError as error:
        mark_project_sync_failure(project_uuid, f"Invalid JSON response from server: {error}")
        return False


def push_pending_projects(user_id=None):
    projects = get_pending_projects(user_id)
    successful = failed = conflicts = 0

    for project in projects:
        result = synchronize_project(project)
        if result == "conflict":
            conflicts += 1
        elif result:
            successful += 1
        else:
            failed += 1

    return {
        "total": len(projects),
        "successful": successful,
        "failed": failed,
        "conflicts": conflicts,
    }


# ============================================================
# NOTE SYNCHRONIZATION
# ============================================================

def get_pending_notes(user_id=None):
    ensure_local_note_schema()
    connection = get_local_connection()
    cursor = connection.cursor()
    query = """
        SELECT note_uuid, project_uuid, user_id, content,
               is_deleted, deleted_at, created_at, updated_at, version
        FROM project_notes
        WHERE sync_status = 'PENDING'
    """
    params = ()
    if user_id:
        query += " AND user_id = ?"
        params = (user_id,)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    connection.close()
    return rows


def mark_note_sync_attempt(note_uuid):
    ensure_local_note_schema()
    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE project_notes
        SET sync_attempts = COALESCE(sync_attempts, 0) + 1,
            last_sync_attempt = ?,
            last_sync_error = NULL
        WHERE note_uuid = ?
        """,
        (current_timestamp(), note_uuid),
    )
    connection.commit()
    connection.close()


def mark_note_sync_success(note_uuid, version=None, updated_at=None):
    ensure_local_note_schema()
    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE project_notes
        SET sync_status = 'SYNCED',
            last_sync_error = NULL,
            last_synced_at = ?,
            version = COALESCE(?, version),
            updated_at = COALESCE(?, updated_at),
            conflict_data = NULL
        WHERE note_uuid = ?
        """,
        (current_timestamp(), version, updated_at, note_uuid),
    )
    connection.commit()
    connection.close()


def mark_note_sync_failure(note_uuid, error_message):
    ensure_local_note_schema()
    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE project_notes
        SET sync_status = 'PENDING',
            last_sync_error = ?
        WHERE note_uuid = ?
        """,
        (error_message, note_uuid),
    )
    connection.commit()
    connection.close()


def mark_note_conflict(note_uuid, conflict_payload):
    ensure_local_note_schema()
    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE project_notes
        SET sync_status = 'CONFLICT',
            last_sync_error = 'Note conflict: server changed since last synchronization.',
            conflict_data = ?
        WHERE note_uuid = ?
        """,
        (json.dumps(conflict_payload), note_uuid),
    )
    connection.commit()
    connection.close()


def synchronize_note(note):
    (
        note_uuid,
        project_uuid,
        user_id,
        content,
        is_deleted,
        deleted_at,
        created_at,
        updated_at,
        version,
    ) = note

    mark_note_sync_attempt(note_uuid)

    payload = {
        "note_uuid": note_uuid,
        "project_uuid": project_uuid,
        "user_id": user_id,
        "content": content,
        "is_deleted": int(is_deleted or 0),
        "deleted_at": deleted_at,
        "created_at": created_at,
        "updated_at": updated_at,
        "version": int(version or 0),
    }

    try:
        response = requests.post(NOTES_URL, json=payload, headers=get_sync_auth_headers(user_id), timeout=10)

        if response.status_code == 409:
            data = response.json()
            detail = data.get("detail", data)
            mark_note_conflict(note_uuid, detail)
            print(f"Note conflict detected: {note_uuid}")
            return "conflict"

        response.raise_for_status()
        data = response.json()
        status = data.get("status")

        if status in {"synced", "updated", "already_synced", "deleted", "already_deleted"}:
            mark_note_sync_success(note_uuid, data.get("version"), data.get("updated_at"))
            return True

        message = f"Unexpected note server response: {data}"
        mark_note_sync_failure(note_uuid, message)
        return False

    except SyncAuthenticationError as error:
        mark_note_sync_failure(note_uuid, str(error))
        return False
    except requests.RequestException as error:
        mark_note_sync_failure(note_uuid, str(error))
        return False
    except ValueError as error:
        mark_note_sync_failure(note_uuid, f"Invalid JSON response from server: {error}")
        return False


def push_pending_notes(user_id=None):
    notes = get_pending_notes(user_id)
    successful = failed = conflicts = 0

    for note in notes:
        result = synchronize_note(note)
        if result == "conflict":
            conflicts += 1
        elif result:
            successful += 1
        else:
            failed += 1

    return {
        "total": len(notes),
        "successful": successful,
        "failed": failed,
        "conflicts": conflicts,
    }


def pull_notes(user_id):
    ensure_local_note_schema()
    result = {
        "created": 0,
        "updated": 0,
        "deleted": 0,
        "unchanged": 0,
        "preserved_pending": 0,
        "preserved_conflicts": 0,
        "failed": False,
    }

    try:
        response = requests.get(NOTES_URL, headers=get_sync_auth_headers(user_id), timeout=10)
        response.raise_for_status()
        server_notes = response.json()
    except SyncAuthenticationError as error:
        result["failed"] = True
        result["error"] = str(error)
        return result
    except requests.RequestException as error:
        result["failed"] = True
        result["error"] = str(error)
        return result
    except ValueError as error:
        result["failed"] = True
        result["error"] = f"Invalid JSON response from server: {error}"
        return result

    connection = get_local_connection()
    connection.row_factory = None
    cursor = connection.cursor()

    for note in server_notes:
        try:
            note_uuid = note.get("note_uuid")
            if not note_uuid:
                result["unchanged"] += 1
                continue

            cursor.execute(
                """
                SELECT note_uuid, user_id, content, sync_status,
                       is_deleted, deleted_at, version, updated_at
                FROM project_notes
                WHERE note_uuid = ?
                """,
                (note_uuid,),
            )
            local = cursor.fetchone()

            server_version = int(note.get("version") or 1)
            server_deleted = int(note.get("is_deleted") or 0)
            server_updated_at = note.get("updated_at") or current_timestamp()

            if not local:
                cursor.execute(
                    """
                    INSERT INTO project_notes (
                        note_uuid, project_uuid, user_id, content,
                        sync_status, is_deleted, deleted_at,
                        created_at, updated_at, version,
                        last_synced_at, conflict_data
                    ) VALUES (?, ?, ?, ?, 'SYNCED', ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        note_uuid,
                        note.get("project_uuid"),
                        note.get("user_id") or user_id,
                        note.get("content") or "",
                        server_deleted,
                        note.get("deleted_at"),
                        note.get("created_at") or server_updated_at,
                        server_updated_at,
                        server_version,
                        current_timestamp(),
                    ),
                )
                if server_deleted:
                    result["deleted"] += 1
                else:
                    result["created"] += 1
                continue

            (
                _local_uuid,
                _local_user_id,
                local_content,
                local_status,
                local_deleted,
                local_deleted_at,
                local_version,
                local_updated_at,
            ) = local

            if local_status == "CONFLICT":
                result["preserved_conflicts"] += 1
                continue

            if local_status == "PENDING":
                result["preserved_pending"] += 1
                continue

            local_version = int(local_version or 0)
            should_update = server_version > local_version

            if not should_update:
                result["unchanged"] += 1
                continue

            cursor.execute(
                """
                UPDATE project_notes
                SET project_uuid = ?,
                    content = ?,
                    sync_status = 'SYNCED',
                    is_deleted = ?,
                    deleted_at = ?,
                    created_at = COALESCE(created_at, ?),
                    updated_at = ?,
                    version = ?,
                    last_sync_error = NULL,
                    last_synced_at = ?,
                    conflict_data = NULL
                WHERE note_uuid = ?
                """,
                (
                    note.get("project_uuid"),
                    note.get("content") or "",
                    server_deleted,
                    note.get("deleted_at"),
                    note.get("created_at") or server_updated_at,
                    server_updated_at,
                    server_version,
                    current_timestamp(),
                    note_uuid,
                ),
            )
            if server_deleted:
                result["deleted"] += 1
            else:
                result["updated"] += 1

        except Exception as error:
            result["failed"] = True
            result.setdefault("errors", []).append(str(error))

    connection.commit()
    connection.close()
    return result


# ============================================================
# ATTACHMENT SYNCHRONIZATION
# ============================================================

def ensure_local_attachment_schema():
    connection = get_local_connection()
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

    additions = [
        ("sync_attempts", "INTEGER DEFAULT 0"),
        ("last_sync_attempt", "TEXT"),
        ("last_sync_error", "TEXT"),
        ("last_synced_at", "TEXT"),
        ("version", "INTEGER DEFAULT 0"),
        ("conflict_data", "TEXT"),
    ]
    for name, definition in additions:
        if not column_exists(cursor, "project_attachments", name):
            cursor.execute(f"ALTER TABLE project_attachments ADD COLUMN {name} {definition}")

    cursor.execute("UPDATE project_attachments SET is_deleted = 1 WHERE sync_status = 'LOCAL_DELETED'")
    cursor.execute("UPDATE project_attachments SET sync_status = 'PENDING' WHERE sync_status IS NULL OR sync_status IN ('LOCAL', 'LOCAL_DELETED')")
    cursor.execute("UPDATE project_attachments SET is_deleted = 0 WHERE is_deleted IS NULL")
    cursor.execute("UPDATE project_attachments SET version = 0 WHERE version IS NULL")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_project_attachments_sync_user ON project_attachments (user_id, sync_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_project_attachments_uuid_user ON project_attachments (attachment_uuid, user_id)")
    connection.commit()
    connection.close()


def get_pending_attachments(user_id=None):
    ensure_local_attachment_schema()
    connection = get_local_connection()
    cursor = connection.cursor()
    query = """
        SELECT attachment_uuid, project_uuid, user_id,
               original_file_name, stored_file_name, file_path,
               file_type, file_size, is_deleted, deleted_at,
               created_at, updated_at, version
        FROM project_attachments
        WHERE sync_status = 'PENDING'
    """
    params = ()
    if user_id:
        query += " AND user_id = ?"
        params = (user_id,)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    connection.close()
    return rows


def mark_attachment_sync_attempt(attachment_uuid):
    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE project_attachments
        SET sync_attempts = COALESCE(sync_attempts, 0) + 1,
            last_sync_attempt = ?,
            last_sync_error = NULL
        WHERE attachment_uuid = ?
        """,
        (current_timestamp(), attachment_uuid),
    )
    connection.commit()
    connection.close()


def mark_attachment_sync_success(attachment_uuid, version=None, updated_at=None):
    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE project_attachments
        SET sync_status = 'SYNCED',
            last_sync_error = NULL,
            last_synced_at = ?,
            version = COALESCE(?, version),
            updated_at = COALESCE(?, updated_at),
            conflict_data = NULL
        WHERE attachment_uuid = ?
        """,
        (current_timestamp(), version, updated_at or current_timestamp(), attachment_uuid),
    )
    connection.commit()
    connection.close()


def mark_attachment_sync_failure(attachment_uuid, error_message):
    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE project_attachments
        SET sync_status = 'PENDING',
            last_sync_error = ?
        WHERE attachment_uuid = ?
        """,
        (error_message, attachment_uuid),
    )
    connection.commit()
    connection.close()


def mark_attachment_conflict(attachment_uuid, conflict_payload):
    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE project_attachments
        SET sync_status = 'CONFLICT',
            last_sync_error = 'Attachment conflict: server changed since last synchronization.',
            conflict_data = ?
        WHERE attachment_uuid = ?
        """,
        (json.dumps(conflict_payload), attachment_uuid),
    )
    connection.commit()
    connection.close()


def synchronize_attachment(attachment):
    (
        attachment_uuid,
        project_uuid,
        user_id,
        original_file_name,
        stored_file_name,
        file_path,
        file_type,
        file_size,
        is_deleted,
        deleted_at,
        created_at,
        updated_at,
        version,
    ) = attachment

    mark_attachment_sync_attempt(attachment_uuid)

    file_content = None
    if int(is_deleted or 0) == 0:
        file_content = encode_file_to_base64(file_path)
        if file_content is None:
            mark_attachment_sync_failure(
                attachment_uuid,
                "Attachment file is missing from local storage and cannot be uploaded.",
            )
            return False

    payload = {
        "attachment_uuid": attachment_uuid,
        "project_uuid": project_uuid,
        "user_id": user_id,
        "original_file_name": original_file_name,
        "file_type": file_type or "application/octet-stream",
        "file_size": int(file_size or 0),
        "file_content": file_content,
        "is_deleted": int(is_deleted or 0),
        "deleted_at": deleted_at,
        "created_at": created_at,
        "updated_at": updated_at,
        "version": int(version or 0),
    }

    try:
        response = requests.post(ATTACHMENTS_URL, json=payload, headers=get_sync_auth_headers(user_id), timeout=20)

        if response.status_code == 409:
            data = response.json()
            detail = data.get("detail", data)
            mark_attachment_conflict(attachment_uuid, detail)
            print(f"Attachment conflict detected: {original_file_name}")
            return "conflict"

        response.raise_for_status()
        data = response.json()
        status = data.get("status")

        if status in {"synced", "updated", "already_synced", "deleted", "already_deleted"}:
            mark_attachment_sync_success(
                attachment_uuid,
                data.get("version"),
                data.get("updated_at"),
            )
            return True

        message = f"Unexpected attachment server response: {data}"
        mark_attachment_sync_failure(attachment_uuid, message)
        return False

    except SyncAuthenticationError as error:
        mark_attachment_sync_failure(attachment_uuid, str(error))
        return False
    except requests.RequestException as error:
        mark_attachment_sync_failure(attachment_uuid, str(error))
        return False
    except ValueError as error:
        mark_attachment_sync_failure(attachment_uuid, f"Invalid JSON response from server: {error}")
        return False


def push_pending_attachments(user_id=None):
    attachments = get_pending_attachments(user_id)
    successful = failed = conflicts = 0

    for attachment in attachments:
        result = synchronize_attachment(attachment)
        if result == "conflict":
            conflicts += 1
        elif result:
            successful += 1
        else:
            failed += 1

    return {
        "total": len(attachments),
        "successful": successful,
        "failed": failed,
        "conflicts": conflicts,
    }


def pull_attachments(user_id):
    ensure_local_attachment_schema()
    result = {
        "created": 0,
        "updated": 0,
        "deleted": 0,
        "unchanged": 0,
        "preserved_pending": 0,
        "preserved_conflicts": 0,
        "failed": False,
    }

    try:
        response = requests.get(ATTACHMENTS_URL, headers=get_sync_auth_headers(user_id), timeout=20)
        response.raise_for_status()
        server_attachments = response.json()
    except SyncAuthenticationError as error:
        result["failed"] = True
        result["error"] = str(error)
        return result
    except requests.RequestException as error:
        result["failed"] = True
        result["error"] = str(error)
        return result
    except ValueError as error:
        result["failed"] = True
        result["error"] = f"Invalid JSON response from server: {error}"
        return result

    connection = get_local_connection()
    connection.row_factory = None
    cursor = connection.cursor()

    for item in server_attachments:
        try:
            attachment_uuid = item.get("attachment_uuid")
            if not attachment_uuid:
                result["unchanged"] += 1
                continue

            cursor.execute(
                """
                SELECT attachment_uuid, user_id, original_file_name,
                       file_path, sync_status, is_deleted,
                       version, updated_at
                FROM project_attachments
                WHERE attachment_uuid = ?
                """,
                (attachment_uuid,),
            )
            local = cursor.fetchone()

            server_version = int(item.get("version") or 1)
            server_deleted = int(item.get("is_deleted") or 0)
            server_updated_at = item.get("updated_at") or current_timestamp()
            original_file_name = clean_file_name(item.get("original_file_name") or "attachment")
            file_type = item.get("file_type") or "application/octet-stream"
            file_size = int(item.get("file_size") or 0)
            saved_path = ""
            stored_file_name = ""

            if not server_deleted:
                file_bytes = decode_base64_file(item.get("file_content") or "")
                if not file_bytes:
                    result["failed"] = True
                    result.setdefault("errors", []).append(
                        f"Attachment {attachment_uuid} was active on server but did not include file content."
                    )
                    continue
                stored_file_name = f"{attachment_uuid}_{original_file_name}"
                attachment_folder = get_attachment_folder(user_id, item.get("project_uuid"))
                saved_file = attachment_folder / stored_file_name
                saved_file.write_bytes(file_bytes)
                saved_path = str(saved_file)
                file_size = len(file_bytes)

            if not local:
                cursor.execute(
                    """
                    INSERT INTO project_attachments (
                        attachment_uuid, project_uuid, user_id,
                        original_file_name, stored_file_name, file_path,
                        file_type, file_size, sync_status,
                        is_deleted, deleted_at, created_at,
                        updated_at, version, last_synced_at,
                        conflict_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'SYNCED', ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        attachment_uuid,
                        item.get("project_uuid"),
                        item.get("user_id") or user_id,
                        original_file_name,
                        stored_file_name,
                        saved_path,
                        file_type,
                        file_size,
                        server_deleted,
                        item.get("deleted_at"),
                        item.get("created_at") or server_updated_at,
                        server_updated_at,
                        server_version,
                        current_timestamp(),
                    ),
                )
                if server_deleted:
                    result["deleted"] += 1
                else:
                    result["created"] += 1
                continue

            (
                _local_uuid,
                _local_user_id,
                _local_file_name,
                local_file_path,
                local_status,
                local_deleted,
                local_version,
                _local_updated_at,
            ) = local

            if local_status == "CONFLICT":
                result["preserved_conflicts"] += 1
                continue

            if local_status == "PENDING":
                result["preserved_pending"] += 1
                continue

            local_version = int(local_version or 0)
            if server_version <= local_version:
                result["unchanged"] += 1
                continue

            if server_deleted:
                try:
                    old_path = Path(local_file_path or "")
                    if old_path.is_file():
                        old_path.unlink()
                except OSError:
                    pass

            cursor.execute(
                """
                UPDATE project_attachments
                SET project_uuid = ?,
                    original_file_name = ?,
                    stored_file_name = ?,
                    file_path = ?,
                    file_type = ?,
                    file_size = ?,
                    sync_status = 'SYNCED',
                    is_deleted = ?,
                    deleted_at = ?,
                    created_at = COALESCE(created_at, ?),
                    updated_at = ?,
                    version = ?,
                    last_sync_error = NULL,
                    last_synced_at = ?,
                    conflict_data = NULL
                WHERE attachment_uuid = ?
                """,
                (
                    item.get("project_uuid"),
                    original_file_name,
                    stored_file_name,
                    saved_path,
                    file_type,
                    file_size,
                    server_deleted,
                    item.get("deleted_at"),
                    item.get("created_at") or server_updated_at,
                    server_updated_at,
                    server_version,
                    current_timestamp(),
                    attachment_uuid,
                ),
            )
            if server_deleted:
                result["deleted"] += 1
            else:
                result["updated"] += 1

        except Exception as error:
            result["failed"] = True
            result.setdefault("errors", []).append(str(error))

    connection.commit()
    connection.close()
    return result



# ============================================================
# TEAM MEMBER SYNCHRONIZATION
# ============================================================

def ensure_local_member_schema():
    connection = get_local_connection()
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
    connection.commit()
    connection.close()


def pull_members(user_id):
    ensure_local_member_schema()
    result = {"created": 0, "updated": 0, "deleted": 0, "unchanged": 0, "failed": False}
    try:
        response = requests.get(MEMBERS_URL, headers=get_sync_auth_headers(user_id), timeout=10)
        response.raise_for_status()
        members = response.json()
    except SyncAuthenticationError as error:
        result["failed"] = True
        result["error"] = str(error)
        return result
    except requests.RequestException as error:
        result["failed"] = True
        result["error"] = str(error)
        return result
    except ValueError as error:
        result["failed"] = True
        result["error"] = f"Invalid JSON response from server: {error}"
        return result

    connection = get_local_connection()
    connection.row_factory = None
    cursor = connection.cursor()
    for member in members:
        try:
            project_uuid = member.get("project_uuid")
            member_user_id = member.get("member_user_id")
            if not project_uuid or not member_user_id:
                result["unchanged"] += 1
                continue
            cursor.execute(
                """
                SELECT role, is_deleted, updated_at
                FROM project_members
                WHERE project_uuid = ? AND member_user_id = ?
                """,
                (project_uuid, member_user_id),
            )
            existing = cursor.fetchone()
            role = (member.get("role") or "VIEWER").upper()
            if role not in {"EDITOR", "VIEWER"}:
                role = "VIEWER"
            is_deleted = int(member.get("is_deleted") or 0)
            updated_at = member.get("updated_at") or current_timestamp()
            if not existing:
                cursor.execute(
                    """
                    INSERT INTO project_members (
                        project_uuid, owner_user_id, member_user_id,
                        member_username, role, is_deleted, invited_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_uuid,
                        member.get("owner_user_id"),
                        member_user_id,
                        member.get("member_username") or member_user_id,
                        role,
                        is_deleted,
                        member.get("invited_at") or updated_at,
                        updated_at,
                    ),
                )
                if is_deleted:
                    result["deleted"] += 1
                else:
                    result["created"] += 1
            else:
                old_role, old_deleted, old_updated = existing
                if old_role == role and int(old_deleted or 0) == is_deleted and (old_updated or "") == updated_at:
                    result["unchanged"] += 1
                else:
                    cursor.execute(
                        """
                        UPDATE project_members
                        SET owner_user_id = ?, member_username = ?, role = ?,
                            is_deleted = ?, invited_at = COALESCE(invited_at, ?), updated_at = ?
                        WHERE project_uuid = ? AND member_user_id = ?
                        """,
                        (
                            member.get("owner_user_id"),
                            member.get("member_username") or member_user_id,
                            role,
                            is_deleted,
                            member.get("invited_at") or updated_at,
                            updated_at,
                            project_uuid,
                            member_user_id,
                        ),
                    )
                    if is_deleted:
                        result["deleted"] += 1
                    else:
                        result["updated"] += 1
        except Exception as error:
            result["failed"] = True
            result.setdefault("errors", []).append(str(error))

    connection.commit()
    connection.close()
    return result


# ============================================================
# FULL BIDIRECTIONAL SYNCHRONIZATION
# ============================================================

def merge_counts(*results):
    summary = {
        "total": 0,
        "successful": 0,
        "failed": 0,
        "conflicts": 0,
    }
    for result in results:
        summary["total"] += int(result.get("total", 0) or 0)
        summary["successful"] += int(result.get("successful", 0) or 0)
        summary["failed"] += int(result.get("failed", 0) or 0)
        summary["conflicts"] += int(result.get("conflicts", 0) or 0)
    return summary


def empty_pull_error(message):
    return {
        "created": 0,
        "updated": 0,
        "deleted": 0,
        "unchanged": 0,
        "preserved_pending": 0,
        "preserved_conflicts": 0,
        "failed": True,
        "error": message,
    }


def synchronize_pending_projects(user_id=None):
    print("\n========================================")
    print("AFRISYNC PROJECT + NOTE + ATTACHMENT BIDIRECTIONAL SYNC")
    print("========================================")

    ensure_local_note_schema()
    ensure_local_attachment_schema()

    if user_id and not get_remote_sync_token(user_id):
        message = "Remote sync token is missing. Log in while the remote server is running."
        pending = count_pending_items(user_id)
        print(message)
        return {
            "total": pending,
            "successful": 0,
            "failed": pending or 1,
            "conflicts": 0,
            "error": message,
            "push": {"projects": {}, "notes": {}, "attachments": {}},
            "pull": {
                "projects": empty_pull_error(message),
                "notes": empty_pull_error(message),
                "attachments": empty_pull_error(message),
            },
            "pull_failed": True,
        }

    project_push = push_pending_projects(user_id)
    note_push = push_pending_notes(user_id)
    attachment_push = push_pending_attachments(user_id)

    if user_id:
        member_pull = pull_members(user_id)
        project_pull = pull_projects(user_id)
        note_pull = pull_notes(user_id)
        attachment_pull = pull_attachments(user_id)
    else:
        project_pull = empty_pull_error("User ID is required for project pull synchronization.")
        note_pull = empty_pull_error("User ID is required for note pull synchronization.")
        attachment_pull = empty_pull_error("User ID is required for attachment pull synchronization.")
        member_pull = empty_pull_error("User ID is required for member pull synchronization.")

    counts = merge_counts(project_push, note_push, attachment_push)

    print(f"Project push successful: {project_push['successful']}")
    print(f"Project push failed: {project_push['failed']}")
    print(f"Note push successful: {note_push['successful']}")
    print(f"Note push failed: {note_push['failed']}")
    print(f"Attachment push successful: {attachment_push['successful']}")
    print(f"Attachment push failed: {attachment_push['failed']}")
    print(f"Conflicts detected: {counts['conflicts']}")

    return {
        "total": counts["total"],
        "successful": counts["successful"],
        "failed": counts["failed"],
        "conflicts": counts["conflicts"],
        "push": {
            "projects": project_push,
            "notes": note_push,
            "attachments": attachment_push,
        },
        "pull": {
            "projects": project_pull,
            "notes": note_pull,
            "attachments": attachment_pull,
            "members": member_pull,
        },
        "pull_failed": (
            bool(project_pull.get("failed"))
            or bool(note_pull.get("failed"))
            or bool(attachment_pull.get("failed"))
            or bool(member_pull.get("failed"))
        ),
    }
