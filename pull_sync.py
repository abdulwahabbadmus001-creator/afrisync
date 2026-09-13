import os
import requests
from datetime import datetime
from app.database import get_local_connection

SERVER_BASE_URL = os.getenv("AFRISYNC_REMOTE_URL", "http://127.0.0.1:8000").rstrip("/")
SERVER_URL = f"{SERVER_BASE_URL}/sync/projects"


def current_timestamp():
    return datetime.now().isoformat()


class SyncAuthenticationError(Exception):
    pass


def column_exists(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return any(row[1] == column_name for row in cursor.fetchall())


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


def ensure_notification_schema(cursor):
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
        "CREATE INDEX IF NOT EXISTS idx_notifications_user_read_created ON notifications (user_id, is_read, created_at)"
    )


def create_local_notification(cursor, user_id, title, message, category="INFO", entity_type="project", entity_uuid=None):
    cursor.execute(
        """
        INSERT INTO notifications (
            notification_uuid, user_id, title, message, category,
            entity_type, entity_uuid, is_read, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
        """,
        (
            __import__("uuid").uuid4().hex,
            user_id,
            title,
            message,
            str(category or "INFO").upper(),
            entity_type,
            entity_uuid,
            current_timestamp(),
        ),
    )


def ensure_project_member_schema(cursor):
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


def get_remote_sync_token(user_id):
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


def get_local_project(cursor, project_uuid):
    cursor.execute(
        """
        SELECT project_uuid, user_id, name, location, progress, sync_status,
               is_deleted, deleted_at, version, updated_at, conflict_data
        FROM projects
        WHERE project_uuid = ?
        """,
        (project_uuid,),
    )
    return cursor.fetchone()


def cache_project_access(cursor, requesting_user_id, project):
    owner_user_id = project.get("user_id")
    access_role = (project.get("access_role") or "OWNER").upper()
    project_uuid = project.get("project_uuid")
    project_name = project.get("name") or "Shared project"

    if owner_user_id == requesting_user_id or access_role == "OWNER":
        return

    normalized_role = access_role if access_role in {"EDITOR", "VIEWER"} else "VIEWER"

    cursor.execute(
        """
        SELECT role, is_deleted
        FROM project_members
        WHERE project_uuid = ? AND member_user_id = ?
        """,
        (project_uuid, requesting_user_id),
    )
    existing_access = cursor.fetchone()

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
            requesting_user_id,
            "You",
            normalized_role,
            project.get("updated_at") or current_timestamp(),
            project.get("updated_at") or current_timestamp(),
        ),
    )

    if not existing_access or bool(existing_access[1]):
        create_local_notification(
            cursor,
            requesting_user_id,
            "New shared project",
            f"You now have {normalized_role.lower()} access to: {project_name}.",
            category="INFO",
            entity_type="project",
            entity_uuid=project_uuid,
        )
    elif str(existing_access[0] or "").upper() != normalized_role:
        create_local_notification(
            cursor,
            requesting_user_id,
            "Project role changed",
            f"Your role on {project_name} is now {normalized_role}.",
            category="INFO",
            entity_type="project",
            entity_uuid=project_uuid,
        )


def create_local_project(cursor, project):
    cursor.execute(
        """
        INSERT INTO projects (
            project_uuid, user_id, name, location, progress, sync_status,
            sync_attempts, last_sync_error, last_synced_at,
            is_deleted, deleted_at, version, updated_at, conflict_data
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project["project_uuid"], project["user_id"], project["name"],
            project["location"], project["progress"], "SYNCED", 0, None,
            current_timestamp(), int(project.get("is_deleted", 0)),
            project.get("deleted_at"), int(project.get("version", 1)),
            project.get("updated_at") or current_timestamp(), None,
        ),
    )


def update_local_from_server(cursor, project):
    cursor.execute(
        """
        UPDATE projects
        SET user_id = ?, name = ?, location = ?, progress = ?, sync_status = 'SYNCED',
            last_sync_error = NULL, last_synced_at = ?, is_deleted = ?,
            deleted_at = ?, version = ?, updated_at = ?, conflict_data = NULL
        WHERE project_uuid = ?
        """,
        (
            project["user_id"], project["name"], project["location"], project["progress"],
            current_timestamp(), int(project.get("is_deleted", 0)),
            project.get("deleted_at"), int(project.get("version", 1)),
            project.get("updated_at") or current_timestamp(), project["project_uuid"],
        ),
    )


def pull_projects(user_id):
    print("\n========================================")
    print("AFRISYNC PULL SYNCHRONIZATION")
    print("========================================")
    print(f"User: {user_id}")

    try:
        response = requests.get(SERVER_URL, headers=get_sync_auth_headers(user_id), timeout=10)
        response.raise_for_status()
        server_projects = response.json()
    except (SyncAuthenticationError, requests.RequestException, ValueError) as error:
        print("Unable to retrieve projects from server.")
        print(error)
        return {
            "created": 0, "updated": 0, "deleted": 0, "unchanged": 0,
            "preserved_pending": 0, "preserved_conflicts": 0,
            "failed": True, "error": str(error),
        }

    connection = get_local_connection()
    cursor = connection.cursor()
    ensure_project_member_schema(cursor)
    ensure_notification_schema(cursor)

    created = updated = deleted = unchanged = 0
    preserved_pending = preserved_conflicts = 0

    for project in server_projects:
        if not project.get("project_uuid"):
            continue

        cache_project_access(cursor, user_id, project)
        local = get_local_project(cursor, project["project_uuid"])
        server_deleted = bool(project.get("is_deleted", 0))

        if not local:
            create_local_project(cursor, project)
            deleted += 1 if server_deleted else 0
            created += 0 if server_deleted else 1
            continue

        (
            _uuid, _uid, local_name, local_location, local_progress,
            local_status, local_deleted, _local_deleted_at,
            local_version, local_updated_at, _conflict_data,
        ) = local

        if local_status == "CONFLICT":
            preserved_conflicts += 1
            continue

        if local_status == "PENDING":
            preserved_pending += 1
            continue

        server_version = int(project.get("version", 1))
        local_version = int(local_version or 1)

        changed = (
            local_name != project["name"]
            or local_location != project["location"]
            or local_progress != project["progress"]
            or bool(local_deleted) != server_deleted
            or local_version != server_version
            or (local_updated_at or "") != (project.get("updated_at") or "")
        )

        if changed:
            was_deleted = bool(local_deleted)
            update_local_from_server(cursor, project)
            if server_deleted and not was_deleted:
                deleted += 1
            else:
                updated += 1
        else:
            unchanged += 1

    connection.commit()
    connection.close()

    print(f"Server returned {len(server_projects)} project(s).")
    print(f"Created: {created}")
    print(f"Updated: {updated}")
    print(f"Deleted: {deleted}")
    print(f"Unchanged: {unchanged}")
    print(f"Pending preserved: {preserved_pending}")
    print(f"Conflicts preserved: {preserved_conflicts}")

    return {
        "created": created,
        "updated": updated,
        "deleted": deleted,
        "unchanged": unchanged,
        "preserved_pending": preserved_pending,
        "preserved_conflicts": preserved_conflicts,
        "failed": False,
    }


if __name__ == "__main__":
    user_id = input("Enter your AfriSync user ID: ").strip()
    if user_id:
        pull_projects(user_id)
    else:
        print("User ID is required.")
