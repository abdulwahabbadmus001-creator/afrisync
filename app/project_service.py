from datetime import datetime

from app.database import get_local_connection


def get_project(project_uuid):
    """
    Retrieve one project by UUID.
    """

    connection = get_local_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            project_uuid,
            name,
            location,
            progress,
            sync_status,
            sync_attempts,
            last_sync_attempt,
            last_sync_error,
            last_synced_at
        FROM projects
        WHERE project_uuid = ?
    """, (project_uuid,))

    project = cursor.fetchone()

    connection.close()

    return project


def update_project(project_uuid, name=None, location=None, progress=None):
    """
    Update a project and mark it as PENDING
    so the changes can be synchronized with the server.
    """

    connection = get_local_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            name,
            location,
            progress
        FROM projects
        WHERE project_uuid = ?
    """, (project_uuid,))

    existing_project = cursor.fetchone()

    if not existing_project:
        connection.close()
        return False

    current_name, current_location, current_progress = existing_project

    new_name = name if name is not None else current_name
    new_location = location if location is not None else current_location
    new_progress = (
        progress
        if progress is not None
        else current_progress
    )

    cursor.execute("""
        UPDATE projects
        SET
            name = ?,
            location = ?,
            progress = ?,
            sync_status = 'PENDING',
            last_sync_error = NULL
        WHERE project_uuid = ?
    """, (
        new_name,
        new_location,
        new_progress,
        project_uuid
    ))

    connection.commit()
    connection.close()

    return True