"""AfriSync Developer Platform API v1.

This module is intentionally isolated from server.py. The installer appends one
registration call to server.py and passes the existing database/auth helpers in.
"""

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _read_bearer(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token is required.")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Bearer token is empty.")
    return token


class ApiKeyCreate(BaseModel):
    name: str = Field(default="Developer key", min_length=2, max_length=80)


class ProjectRegister(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    framework: Optional[str] = Field(default=None, max_length=80)
    runtime: Optional[str] = Field(default=None, max_length=80)
    language: Optional[str] = Field(default=None, max_length=80)
    repository_url: Optional[str] = Field(default=None, max_length=500)
    default_branch: Optional[str] = Field(default=None, max_length=120)
    client_project_id: Optional[str] = Field(default=None, max_length=120)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EventInput(BaseModel):
    event_id: Optional[str] = Field(default=None, max_length=120)
    project_id: str = Field(min_length=3, max_length=120)
    event: str = Field(min_length=2, max_length=160)
    timestamp: Optional[str] = Field(default=None, max_length=80)
    source: str = Field(default="cli", min_length=2, max_length=40)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EventBatch(BaseModel):
    events: List[EventInput] = Field(min_length=1, max_length=100)


def register_developer_api(app, get_connection, current_timestamp, require_sync_auth):
    """Attach AfriSync developer routes to the existing FastAPI app."""

    def init_tables():
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS developer_api_keys (
                key_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                key_prefix TEXT NOT NULL,
                key_hash TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                last_used_at TEXT,
                revoked_at TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS developer_projects (
                project_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                framework TEXT,
                runtime TEXT,
                language TEXT,
                repository_url TEXT,
                default_branch TEXT,
                client_project_id TEXT,
                metadata_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_event_at TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS developer_events (
                event_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                received_at TEXT NOT NULL,
                source TEXT NOT NULL,
                metadata_json TEXT
            )
            """
        )
        try:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_dev_keys_user ON developer_api_keys (user_id, revoked_at)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_dev_projects_user ON developer_projects (user_id, updated_at)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_dev_events_project ON developer_events (project_id, occurred_at)"
            )
        except Exception:
            # Some DB adapters can differ on IF NOT EXISTS for indexes. Tables are enough.
            pass
        connection.commit()
        connection.close()

    init_tables()

    def authenticate_api_key(request: Request):
        raw_key = _read_bearer(request)
        if not raw_key.startswith("afs_live_"):
            raise HTTPException(status_code=401, detail="Invalid AfriSync developer API key.")

        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT key_id, user_id, name, revoked_at
            FROM developer_api_keys
            WHERE key_hash = ?
            """,
            (_hash_key(raw_key),),
        )
        row = cursor.fetchone()
        if not row or row["revoked_at"]:
            connection.close()
            raise HTTPException(status_code=401, detail="AfriSync developer API key is invalid or revoked.")

        used_at = _now()
        cursor.execute(
            "UPDATE developer_api_keys SET last_used_at = ? WHERE key_id = ?",
            (used_at, row["key_id"]),
        )
        connection.commit()
        connection.close()
        return {"key_id": row["key_id"], "user_id": row["user_id"], "name": row["name"]}

    def require_project_owner(project_id: str, user_id: str):
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT project_id, user_id, name FROM developer_projects WHERE project_id = ?",
            (project_id,),
        )
        project = cursor.fetchone()
        connection.close()
        if not project:
            raise HTTPException(status_code=404, detail="Developer project not found.")
        if project["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Developer project does not belong to this API key.")
        return project

    def store_event(payload: EventInput, user_id: str):
        require_project_owner(payload.project_id, user_id)
        event_id = payload.event_id or f"evt_{uuid.uuid4().hex}"
        occurred_at = payload.timestamp or _now()
        received_at = _now()
        metadata_json = json.dumps(payload.metadata, separators=(",", ":"), ensure_ascii=False)

        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT event_id FROM developer_events WHERE event_id = ?", (event_id,))
        if cursor.fetchone():
            connection.close()
            return {"event_id": event_id, "duplicate": True, "stored": True}

        cursor.execute(
            """
            INSERT INTO developer_events (
                event_id, project_id, user_id, event_type, occurred_at,
                received_at, source, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                payload.project_id,
                user_id,
                payload.event,
                occurred_at,
                received_at,
                payload.source,
                metadata_json,
            ),
        )
        cursor.execute(
            "UPDATE developer_projects SET last_event_at = ?, updated_at = ? WHERE project_id = ?",
            (occurred_at, received_at, payload.project_id),
        )
        connection.commit()
        connection.close()
        return {"event_id": event_id, "duplicate": False, "stored": True}

    @app.get("/v1/developer/health")
    def developer_health():
        return {"status": "online", "service": "AfriSync Developer API", "version": "1"}

    @app.post("/v1/developer/api-keys")
    def create_developer_key(payload: ApiKeyCreate, request: Request):
        user = require_sync_auth(request)
        key_id = f"key_{uuid.uuid4().hex[:20]}"
        raw_key = "afs_live_" + secrets.token_urlsafe(36)
        now = _now()
        prefix = raw_key[:18]

        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO developer_api_keys (
                key_id, user_id, name, key_prefix, key_hash, created_at,
                last_used_at, revoked_at
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)
            """,
            (key_id, user["user_id"], payload.name.strip(), prefix, _hash_key(raw_key), now),
        )
        connection.commit()
        connection.close()
        return {
            "key_id": key_id,
            "name": payload.name.strip(),
            "api_key": raw_key,
            "prefix": prefix,
            "created_at": now,
            "message": "Copy this API key now. AfriSync stores only its hash and cannot show it again.",
        }

    @app.get("/v1/developer/api-keys")
    def list_developer_keys(request: Request):
        user = require_sync_auth(request)
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT key_id, name, key_prefix, created_at, last_used_at, revoked_at
            FROM developer_api_keys
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user["user_id"],),
        )
        rows = [dict(row) for row in cursor.fetchall()]
        connection.close()
        return rows

    @app.delete("/v1/developer/api-keys/{key_id}")
    def revoke_developer_key(key_id: str, request: Request):
        user = require_sync_auth(request)
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT key_id FROM developer_api_keys WHERE key_id = ? AND user_id = ?",
            (key_id, user["user_id"]),
        )
        if not cursor.fetchone():
            connection.close()
            raise HTTPException(status_code=404, detail="API key not found.")
        revoked_at = _now()
        cursor.execute(
            "UPDATE developer_api_keys SET revoked_at = ? WHERE key_id = ? AND user_id = ?",
            (revoked_at, key_id, user["user_id"]),
        )
        connection.commit()
        connection.close()
        return {"key_id": key_id, "revoked": True, "revoked_at": revoked_at}

    @app.post("/v1/projects/register")
    def register_project(payload: ProjectRegister, request: Request):
        auth = authenticate_api_key(request)
        user_id = auth["user_id"]
        connection = get_connection()
        cursor = connection.cursor()

        existing = None
        if payload.client_project_id:
            cursor.execute(
                """
                SELECT project_id FROM developer_projects
                WHERE user_id = ? AND client_project_id = ?
                """,
                (user_id, payload.client_project_id),
            )
            existing = cursor.fetchone()
        if not existing and payload.repository_url:
            cursor.execute(
                """
                SELECT project_id FROM developer_projects
                WHERE user_id = ? AND repository_url = ?
                """,
                (user_id, payload.repository_url),
            )
            existing = cursor.fetchone()

        now = _now()
        metadata_json = json.dumps(payload.metadata, separators=(",", ":"), ensure_ascii=False)
        if existing:
            project_id = existing["project_id"]
            cursor.execute(
                """
                UPDATE developer_projects
                SET name = ?, framework = ?, runtime = ?, language = ?,
                    repository_url = ?, default_branch = ?, client_project_id = ?,
                    metadata_json = ?, updated_at = ?
                WHERE project_id = ? AND user_id = ?
                """,
                (
                    payload.name.strip(), payload.framework, payload.runtime, payload.language,
                    payload.repository_url, payload.default_branch, payload.client_project_id,
                    metadata_json, now, project_id, user_id,
                ),
            )
            created = False
        else:
            project_id = f"prj_{uuid.uuid4().hex[:24]}"
            cursor.execute(
                """
                INSERT INTO developer_projects (
                    project_id, user_id, name, framework, runtime, language,
                    repository_url, default_branch, client_project_id, metadata_json,
                    created_at, updated_at, last_event_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    project_id, user_id, payload.name.strip(), payload.framework,
                    payload.runtime, payload.language, payload.repository_url,
                    payload.default_branch, payload.client_project_id, metadata_json,
                    now, now,
                ),
            )
            created = True

        connection.commit()
        connection.close()
        return {
            "project_id": project_id,
            "name": payload.name.strip(),
            "created": created,
            "registered_at": now,
        }

    @app.post("/v1/events")
    def ingest_event(payload: EventInput, request: Request):
        auth = authenticate_api_key(request)
        return store_event(payload, auth["user_id"])

    @app.post("/v1/events/batch")
    def ingest_event_batch(payload: EventBatch, request: Request):
        auth = authenticate_api_key(request)
        results = [store_event(item, auth["user_id"]) for item in payload.events]
        return {"stored": len(results), "results": results}

    @app.post("/v1/heartbeat")
    def heartbeat(payload: EventInput, request: Request):
        auth = authenticate_api_key(request)
        normalized = payload.model_copy(update={"event": "developer.heartbeat"})
        return store_event(normalized, auth["user_id"])

    @app.get("/v1/developer/projects")
    def list_developer_projects(request: Request):
        user = require_sync_auth(request)
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT project_id, name, framework, runtime, language, repository_url,
                   default_branch, created_at, updated_at, last_event_at
            FROM developer_projects
            WHERE user_id = ?
            ORDER BY COALESCE(last_event_at, updated_at) DESC
            """,
            (user["user_id"],),
        )
        rows = [dict(row) for row in cursor.fetchall()]
        connection.close()
        return rows

    @app.get("/v1/developer/projects/{project_id}/events")
    def list_project_events(project_id: str, request: Request, limit: int = 50):
        user = require_sync_auth(request)
        require_project_owner(project_id, user["user_id"])
        limit = max(1, min(int(limit), 200))
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT event_id, event_type, occurred_at, received_at, source, metadata_json
            FROM developer_events
            WHERE project_id = ? AND user_id = ?
            ORDER BY occurred_at DESC
            LIMIT ?
            """,
            (project_id, user["user_id"], limit),
        )
        result = []
        for row in cursor.fetchall():
            item = dict(row)
            try:
                item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
            except Exception:
                item["metadata"] = {}
                item.pop("metadata_json", None)
            result.append(item)
        connection.close()
        return result

    return app
