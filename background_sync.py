import json
import threading
from datetime import datetime

from app.database import get_local_connection
from app.sync_engine import synchronize_pending_projects
from network import is_server_available


# ============================================================
# CONFIGURATION
# ============================================================

ONLINE_SYNC_INTERVAL_SECONDS = 10
OFFLINE_CHECK_INTERVAL_SECONDS = 15


# ============================================================
# INTERNAL WORKER STATE
# ============================================================

_worker_thread = None
_worker_lock = threading.Lock()
_stop_event = threading.Event()
_last_remote_online = None


# ============================================================
# HELPERS
# ============================================================

def current_timestamp():
    return datetime.now().isoformat(timespec="seconds")


def safe_json_dumps(value):
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        return json.dumps({"value": str(value)}, ensure_ascii=False)


def ensure_monitoring_tables():
    """
    Creates monitoring tables if background_sync.py is executed before
    local_app.py finishes preparing the database.
    """
    connection = get_local_connection()
    cursor = connection.cursor()
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
        "CREATE INDEX IF NOT EXISTS idx_activity_logs_user_created ON activity_logs (user_id, created_at)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_sync_history_user_completed ON sync_history (user_id, completed_at)"
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
        "CREATE INDEX IF NOT EXISTS idx_notifications_user_read_created ON notifications (user_id, is_read, created_at)"
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
        "CREATE INDEX IF NOT EXISTS idx_project_attachments_sync_user ON project_attachments (user_id, sync_status)"
    )
    connection.commit()
    connection.close()


def create_notification(user_id, title, message, category="INFO", entity_type="sync"):
    if not user_id:
        return
    try:
        ensure_monitoring_tables()
        connection = get_local_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO notifications (
                notification_uuid, user_id, title, message, category,
                entity_type, entity_uuid, is_read, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, 0, ?)
            """,
            (
                __import__("uuid").uuid4().hex,
                user_id,
                title,
                message,
                str(category or "INFO").upper(),
                entity_type,
                current_timestamp(),
            ),
        )
        connection.commit()
        connection.close()
    except Exception as error:
        print(f"[{current_timestamp()}] Notification write failed: {error}")


def log_activity(user_id, action, message, entity_type="sync", details=None):
    try:
        ensure_monitoring_tables()
        connection = get_local_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO activity_logs (
                user_id, action, entity_type, entity_uuid,
                message, details, created_at
            )
            VALUES (?, ?, ?, NULL, ?, ?, ?)
            """,
            (
                user_id,
                action,
                entity_type,
                message,
                safe_json_dumps(details),
                current_timestamp(),
            ),
        )
        connection.commit()
        connection.close()
    except Exception as error:
        print(f"[{current_timestamp()}] Activity log write failed: {error}")


def record_sync_history(user_id, started_at, completed_at, status, result, message):
    try:
        ensure_monitoring_tables()
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
                int(result.get("total", 0) or 0),
                int(result.get("successful", 0) or 0),
                int(result.get("failed", 0) or 0),
                int(result.get("conflicts", 0) or 0),
                message,
                safe_json_dumps(result),
            ),
        )
        connection.commit()
        connection.close()
    except Exception as error:
        print(f"[{current_timestamp()}] Sync history write failed: {error}")


def get_users_to_sync():
    """
    Return every user that should be checked by the background sync worker.

    We include:
    1. users with pending local changes, because their work must be uploaded;
    2. users with an active local session, because they may need fresh server data pulled down.
    """
    connection = get_local_connection()
    cursor = connection.cursor()

    users = set()

    cursor.execute(
        """
        SELECT DISTINCT user_id
        FROM projects
        WHERE user_id IS NOT NULL
          AND user_id != ''
          AND sync_status = 'PENDING'
        """
    )
    for row in cursor.fetchall():
        users.add(row[0])

    cursor.execute(
        """
        SELECT DISTINCT user_id
        FROM project_notes
        WHERE user_id IS NOT NULL
          AND user_id != ''
          AND sync_status = 'PENDING'
        """
    )
    for row in cursor.fetchall():
        users.add(row[0])

    cursor.execute(
        """
        SELECT DISTINCT user_id
        FROM project_attachments
        WHERE user_id IS NOT NULL
          AND user_id != ''
          AND sync_status = 'PENDING'
        """
    )
    for row in cursor.fetchall():
        users.add(row[0])

    cursor.execute(
        """
        SELECT DISTINCT user_id
        FROM local_sessions
        WHERE user_id IS NOT NULL
          AND user_id != ''
          AND expires_at > ?
        """,
        (datetime.now().isoformat(),),
    )
    for row in cursor.fetchall():
        users.add(row[0])

    connection.close()
    return sorted(users)


def count_pending_projects():
    connection = get_local_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM projects
        WHERE sync_status = 'PENDING'
        """
    )
    pending_projects = cursor.fetchone()[0]
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM project_notes
        WHERE sync_status = 'PENDING'
        """
    )
    pending_notes = cursor.fetchone()[0]
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM project_attachments
        WHERE sync_status = 'PENDING'
        """
    )
    pending_attachments = cursor.fetchone()[0]
    count = pending_projects + pending_notes + pending_attachments
    connection.close()
    return count


def run_sync_cycle():
    users = get_users_to_sync()

    if not users:
        return {
            "users": 0,
            "total": 0,
            "successful": 0,
            "failed": 0,
            "conflicts": 0,
        }

    summary = {
        "users": len(users),
        "total": 0,
        "successful": 0,
        "failed": 0,
        "conflicts": 0,
    }

    for user_id in users:
        started_at = current_timestamp()
        try:
            result = synchronize_pending_projects(user_id)
            completed_at = current_timestamp()

            total = int(result.get("total", 0) or 0)
            successful = int(result.get("successful", 0) or 0)
            failed = int(result.get("failed", 0) or 0)
            conflicts = int(result.get("conflicts", 0) or 0)

            summary["total"] += total
            summary["successful"] += successful
            summary["failed"] += failed
            summary["conflicts"] += conflicts

            if total or failed or conflicts:
                status = "completed"
                if failed:
                    status = "partial_failure"
                if conflicts:
                    status = "conflict"

                message = (
                    "Background sync completed: "
                    f"{successful} successful, {failed} failed, {conflicts} conflict(s)."
                )
                record_sync_history(user_id, started_at, completed_at, status, result, message)
                log_activity(
                    user_id,
                    "SYNC_BACKGROUND",
                    message,
                    details=result,
                )
                if conflicts:
                    create_notification(
                        user_id,
                        "Sync conflict needs review",
                        f"Background sync found {conflicts} conflict(s). Open Sync Conflicts to resolve them.",
                        category="DANGER",
                    )
                elif failed:
                    create_notification(
                        user_id,
                        "Background sync had errors",
                        f"{failed} item(s) failed during background synchronization.",
                        category="DANGER",
                    )
                elif successful:
                    create_notification(
                        user_id,
                        "Background sync completed",
                        f"{successful} pending item(s) synchronized successfully.",
                        category="SUCCESS",
                    )

        except Exception as error:
            completed_at = current_timestamp()
            summary["failed"] += 1
            result = {"total": 0, "successful": 0, "failed": 1, "conflicts": 0, "error": str(error)}
            record_sync_history(
                user_id,
                started_at,
                completed_at,
                "failed",
                result,
                f"Background sync failed: {error}",
            )
            log_activity(
                user_id,
                "SYNC_BACKGROUND_FAILED",
                f"Background sync failed: {error}",
                details={"error": str(error)},
            )
            create_notification(
                user_id,
                "Background sync failed",
                f"AfriSync could not complete background synchronization: {error}",
                category="DANGER",
            )
            print(
                f"[{current_timestamp()}] Background sync failed for user {user_id}: {error}"
            )

    return summary


# ============================================================
# WORKER LOOP
# ============================================================

def background_worker():
    global _last_remote_online

    print(f"[{current_timestamp()}] AfriSync background sync started.")

    while not _stop_event.is_set():
        try:
            remote_online = is_server_available(timeout=2)

            if remote_online != _last_remote_online:
                if remote_online:
                    print(f"[{current_timestamp()}] Remote server online. Sync enabled.")
                else:
                    pending = count_pending_projects()
                    print(
                        f"[{current_timestamp()}] Remote server offline. "
                        f"Pending local changes: {pending}."
                    )
                _last_remote_online = remote_online

            if remote_online:
                summary = run_sync_cycle()
                if summary["total"] or summary["failed"] or summary["conflicts"]:
                    print(
                        f"[{current_timestamp()}] Background sync summary: "
                        f"users={summary['users']}, "
                        f"total={summary['total']}, "
                        f"successful={summary['successful']}, "
                        f"failed={summary['failed']}, "
                        f"conflicts={summary['conflicts']}"
                    )
                wait_seconds = ONLINE_SYNC_INTERVAL_SECONDS
            else:
                wait_seconds = OFFLINE_CHECK_INTERVAL_SECONDS

        except Exception as error:
            print(f"[{current_timestamp()}] Background sync worker error: {error}")
            wait_seconds = OFFLINE_CHECK_INTERVAL_SECONDS

        _stop_event.wait(wait_seconds)

    print(f"[{current_timestamp()}] AfriSync background sync stopped.")


# ============================================================
# PUBLIC CONTROL FUNCTIONS
# ============================================================

def start_background_sync():
    global _worker_thread

    with _worker_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return

        _stop_event.clear()
        _worker_thread = threading.Thread(
            target=background_worker,
            name="AfriSyncBackgroundSync",
            daemon=True,
        )
        _worker_thread.start()


def stop_background_sync():
    global _worker_thread

    with _worker_lock:
        if _worker_thread is None:
            return

        _stop_event.set()
        _worker_thread = None
